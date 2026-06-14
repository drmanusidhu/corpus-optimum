#!/usr/bin/env python3
"""
Manu's Personal AI Coaching Agent
Reads Oura ring data, provides Claude-powered coaching via Telegram
Tracks goals: Sleep → Energy → HRV/Recovery → Physique
"""

import os
import json
import sqlite3
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
import schedule
import time
import threading
import logging

from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, ContextTypes, filters

from src.oura import OuraClient
from src.brain import CoachingBrain
from src.memory import MemoryStore
from src.calendar import CalendarClient
from src.notion import NotionClient

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()

OURA_PAT = os.getenv("OURA_PERSONAL_ACCESS_TOKEN")
ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))
NOTION_KEY = os.getenv("NOTION_API_KEY")
NOTION_TASKS_DB = os.getenv("NOTION_TASKS_DB_ID")
NOTION_MY_DAY = os.getenv("NOTION_MY_DAY_PAGE_ID")
GOOGLE_CREDS = os.getenv("GOOGLE_CREDENTIALS_PATH", "./credentials.json")

# Initialize clients
oura = OuraClient(OURA_PAT)
brain = CoachingBrain(ANTHROPIC_KEY)
memory = MemoryStore()
calendar = CalendarClient(GOOGLE_CREDS) if os.path.exists(GOOGLE_CREDS) else None
notion = NotionClient(NOTION_KEY, NOTION_TASKS_DB, NOTION_MY_DAY) if NOTION_KEY else None


async def send_message(bot, text):
    """Send a message via Telegram"""
    try:
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text)
        memory.log_agent_message(text)
    except Exception as e:
        logger.error(f"Failed to send message: {e}")


async def morning_checkpoint(bot):
    """05:30 - Morning routine checkpoint"""
    try:
        oura_data = oura.get_latest_readiness()
        readiness = oura_data.get("score", 0)
        
        context = {
            "readiness": readiness,
            "hour": "morning",
            "time": "05:30"
        }
        
        message = brain.generate_message(context)
        await send_message(bot, message)
    except Exception as e:
        logger.error(f"Morning checkpoint failed: {e}")


async def midday_energy_check(bot):
    """12:30 - Midday energy and caffeine check"""
    try:
        oura_data = oura.get_latest_activity()
        calendar_events = calendar.get_upcoming_events(hours=2) if calendar else []
        recent_messages = memory.get_recent_messages(hours=4)
        
        context = {
            "hour": "midday",
            "time": "12:30",
            "activity": oura_data,
            "calendar": calendar_events,
            "recent_context": recent_messages
        }
        
        message = brain.generate_message(context)
        await send_message(bot, message)
    except Exception as e:
        logger.error(f"Midday check failed: {e}")


async def afternoon_slump_check(bot):
    """16:00 - Afternoon energy dip prevention"""
    try:
        oura_data = oura.get_latest_activity()
        
        context = {
            "hour": "afternoon",
            "time": "16:00",
            "activity": oura_data
        }
        
        message = brain.generate_message(context)
        await send_message(bot, message)
    except Exception as e:
        logger.error(f"Afternoon check failed: {e}")


async def evening_winddown(bot):
    """20:00 - Evening wind-down initiation"""
    try:
        context = {
            "hour": "evening",
            "time": "20:00",
            "goal": "initiate_winddown"
        }
        
        message = brain.generate_message(context)
        await send_message(bot, message)
    except Exception as e:
        logger.error(f"Evening wind-down failed: {e}")


async def night_check_conditional(bot):
    """23:00 - Conditional night check (only if still awake)"""
    try:
        recent_messages = memory.get_recent_messages(hours=1)
        
        if recent_messages:  # User was active recently
            context = {
                "hour": "night",
                "time": "23:00",
                "user_active": True
            }
            
            message = brain.generate_message(context)
            await send_message(bot, message)
    except Exception as e:
        logger.error(f"Night check failed: {e}")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming Telegram messages"""
    user_message = update.message.text
    memory.log_user_message(user_message)
    
    if user_message.startswith("/"):
        await handle_command(update, context, user_message)
    else:
        # Generate conversational response
        context_data = {
            "user_message": user_message,
            "recent_history": memory.get_recent_messages(hours=6)
        }
        
        response = brain.generate_response(user_message, context_data)
        await send_message(context.bot, response)


async def handle_command(update: Update, context: ContextTypes.DEFAULT_TYPE, cmd: str):
    """Handle special commands"""
    if cmd == "/status":
        oura_data = oura.get_latest_readiness()
        sleep_data = oura.get_latest_sleep()
        
        status = f"""
📊 STATUS SNAPSHOT

Readiness: {oura_data.get('score', 'N/A')}/100
Sleep (last night): {sleep_data.get('total_sleep_duration', 0)/3600:.1f}h
Deep sleep: {sleep_data.get('deep_sleep_duration', 0)/3600:.1f}h
REM sleep: {sleep_data.get('rem_sleep_duration', 0)/3600:.1f}h
Efficiency: {sleep_data.get('sleep_efficiency', 0)*100:.0f}%
        """
        await send_message(context.bot, status)
    
    elif cmd == "/busy":
        memory.set_busy_until(datetime.now() + timedelta(hours=1))
        await send_message(context.bot, "Got it. Pausing messages for 1 hour. Use /available to resume.")
    
    elif cmd == "/available":
        memory.clear_busy()
        await send_message(context.bot, "Welcome back. Resuming coaching messages.")
    
    elif cmd == "/trends":
        trends = brain.analyze_trends(memory.get_recent_messages(days=7))
        await send_message(context.bot, trends)
    
    else:
        await send_message(context.bot, "Unknown command. Available: /status, /busy, /available, /trends")


def schedule_jobs(bot):
    """Set up the daily scheduling"""
    schedule.every().day.at("05:30").do(asyncio.run, morning_checkpoint(bot))
    schedule.every().day.at("12:30").do(asyncio.run, midday_energy_check(bot))
    schedule.every().day.at("16:00").do(asyncio.run, afternoon_slump_check(bot))
    schedule.every().day.at("20:00").do(asyncio.run, evening_winddown(bot))
    schedule.every().day.at("23:00").do(asyncio.run, night_check_conditional(bot))
    
    while True:
        schedule.run_pending()
        time.sleep(30)


async def main():
    """Main entry point"""
    # Build Telegram application
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Add handlers
    app.add_handler(CommandHandler("status", lambda u, c: handle_command(u, c, "/status")))
    app.add_handler(CommandHandler("busy", lambda u, c: handle_command(u, c, "/busy")))
    app.add_handler(CommandHandler("available", lambda u, c: handle_command(u, c, "/available")))
    app.add_handler(CommandHandler("trends", lambda u, c: handle_command(u, c, "/trends")))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Start scheduler in background thread
    scheduler_thread = threading.Thread(
        target=schedule_jobs,
        args=(app.bot,),
        daemon=True
    )
    scheduler_thread.start()
    
    logger.info("✓ Manu's AI Coaching Agent started")
    logger.info("✓ Listening for Telegram messages...")
    logger.info("✓ Daily coaching scheduled at: 05:30, 12:30, 16:00, 20:00, 23:00")
    
    # Start polling
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())

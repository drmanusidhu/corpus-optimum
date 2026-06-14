"""
telegram_bot.py — Two-way Telegram interface.
Sends proactive messages and listens for Shaun's replies.
"""
import os
import logging
import asyncio
from datetime import datetime

from telegram import Update, Bot
from telegram.ext import Application, MessageHandler, filters, ContextTypes

from . import memory, brain

logger = logging.getLogger(__name__)


def get_chat_id() -> int:
    return int(os.environ["TELEGRAM_CHAT_ID"])


async def send_message(text: str, touchpoint: str = "agent") -> None:
    """Send a message to Shaun's Telegram chat."""
    bot = Bot(token=os.environ["TELEGRAM_BOT_TOKEN"])
    async with bot:
        await bot.send_message(
            chat_id=get_chat_id(),
            text=text,
            parse_mode="Markdown",
        )
    memory.save_message("agent", text, touchpoint)
    logger.info(f"Sent [{touchpoint}]: {text[:60]}...")


def send_message_sync(text: str, touchpoint: str = "agent") -> None:
    """Synchronous wrapper for use in the scheduler."""
    asyncio.run(send_message(text, touchpoint))


async def handle_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle incoming messages from Shaun and reply intelligently."""
    msg = update.message

    # Security: only respond to Shaun's chat
    if msg.chat_id != get_chat_id():
        logger.warning(f"Message from unknown chat_id {msg.chat_id} — ignored.")
        return

    user_text = msg.text or ""
    logger.info(f"Received reply: {user_text[:80]}")

    # Save the incoming message
    memory.save_message("user", user_text, "reply")

    # Check for special commands
    lower = user_text.strip().lower()

    if lower in ("/status", "status"):
        await _send_status(context)
        return

    if lower in ("/help", "help", "?"):
        await msg.reply_text(
            "Commands:\n"
            "• Just talk to me naturally — I'll respond in context\n"
            "• `/status` — see today's biometric snapshot\n"
            "• `/busy` — tell me you're busy, I'll reduce messages today\n"
            "• `/notes` — see what I know about today so far\n"
            "• `/trends` — see your 7-day readiness/sleep trend"
        )
        return

    if lower in ("/busy", "busy", "i'm busy", "im busy"):
        memory.set_profile("today_busy", "true")
        await msg.reply_text("Got it — I'll keep messages brief today. Message me whenever you want to check in.")
        memory.save_message("agent", "Acknowledged busy day, reducing messages.", "reply")
        return

    if lower in ("/notes", "notes"):
        today_msgs = memory.get_today_messages()
        if today_msgs:
            summary = "\n".join(f"• [{m['touchpoint']}] {m['role']}: {m['content'][:80]}"
                                for m in today_msgs[-10:])
            await msg.reply_text(f"Today so far:\n\n{summary}")
        else:
            await msg.reply_text("No messages logged yet today.")
        return

    if lower in ("/trends", "trends"):
        from . import oura as oura_mod
        try:
            trend = oura_mod.fetch_7day_trend()
            lines = ["7-day trend:"]
            for t in trend:
                r = t.get("readiness", "–")
                s = t.get("sleep", "–")
                h = t.get("hrv_balance", "–")
                lines.append(f"• {t['date']}: Readiness {r} | Sleep {s} | HRV bal {h}")
            await msg.reply_text("\n".join(lines))
        except Exception as e:
            await msg.reply_text(f"Couldn't fetch trends: {e}")
        return

    # Default: generate a contextual reply via Claude
    try:
        reply = brain.generate_message("reply", user_message=user_text)
        await msg.reply_text(reply, parse_mode="Markdown")
        memory.save_message("agent", reply, "reply")
    except Exception as e:
        logger.error(f"Brain error: {e}")
        await msg.reply_text("Sorry, something went wrong on my end — try again in a moment.")


async def _send_status(context: ContextTypes.DEFAULT_TYPE):
    from . import oura as oura_mod
    from datetime import date
    try:
        snap = oura_mod.fetch_daily_snapshot()
        r = snap.get("readiness", {})
        s = snap.get("sleep_detail", {})
        a = snap.get("activity", {})
        text = (
            f"📊 *Today's snapshot* ({date.today().isoformat()})\n\n"
            f"🟢 Readiness: {r.get('score', '–')}\n"
            f"😴 Sleep score: {snap.get('sleep_summary', {}).get('score', '–')}\n"
            f"⏱ Total sleep: {s.get('total_minutes', '–')} min\n"
            f"💤 Deep: {s.get('deep_minutes', '–')} min | REM: {s.get('rem_minutes', '–')} min\n"
            f"💓 Avg HRV: {s.get('avg_hrv', '–')} | Lowest HR: {s.get('lowest_hr', '–')}\n"
            f"👟 Steps: {a.get('steps', '–')} | Active cal: {a.get('active_calories', '–')}\n"
        )
        await context.bot.send_message(chat_id=get_chat_id(), text=text, parse_mode="Markdown")
        memory.save_message("agent", text, "status")
    except Exception as e:
        await context.bot.send_message(chat_id=get_chat_id(), text=f"Status error: {e}")


def run_bot():
    """Start the Telegram bot listener (blocking — runs in its own thread)."""
    app = (
        Application.builder()
        .token(os.environ["TELEGRAM_BOT_TOKEN"])
        .build()
    )
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_reply))
    app.add_handler(MessageHandler(filters.COMMAND, handle_reply))

    logger.info("Telegram bot polling started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

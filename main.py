"""
main.py — Entry point for the Oura Agent.
Boots the SQLite store, starts the scheduler thread, then runs the Telegram bot.
"""
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# ── Load environment ──────────────────────────────────────────────────────────
load_dotenv()

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("./data/agent.log", mode="a"),
    ],
)
logger = logging.getLogger("oura_agent")

# ── Validate required env vars ────────────────────────────────────────────────
REQUIRED = [
    "OURA_PERSONAL_ACCESS_TOKEN",
    "ANTHROPIC_API_KEY",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "NOTION_API_KEY",
]

missing = [k for k in REQUIRED if not os.environ.get(k)]
if missing:
    logger.error(f"Missing required environment variables: {', '.join(missing)}")
    logger.error("Copy .env.template to .env and fill in your keys.")
    sys.exit(1)

# ── Bootstrap ─────────────────────────────────────────────────────────────────
from src import memory
from src.scheduler import start_scheduler_thread
from src.telegram_bot import run_bot

def main():
    logger.info("🤖 Oura Agent starting up...")

    # Initialise database
    Path("./data").mkdir(exist_ok=True)
    memory.init_db()
    logger.info("Database initialised.")

    # Seed the user profile with known facts
    memory.set_profile("name", "Shaun Sidhu")
    memory.set_profile("timezone", "Europe/London")
    memory.set_profile("gym_split", "Chest+Tris → Back+Bis → Legs+Core (rotating)")
    memory.set_profile("caffeine_target", "0-1 coffees/day, caffeine-free days weekly")
    memory.set_profile("ideal_bedtime", "21:00–21:30")
    memory.set_profile("ideal_waketime", "05:00")
    memory.set_profile("location", "King's Lynn, England")

    # Start the scheduler in background
    sched_thread = start_scheduler_thread()
    logger.info(f"Scheduler thread started: {sched_thread.name}")

    # Start the Telegram bot (blocking — keeps the process alive)
    logger.info("Starting Telegram bot...")
    run_bot()


if __name__ == "__main__":
    main()

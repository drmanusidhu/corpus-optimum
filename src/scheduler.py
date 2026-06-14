"""
scheduler.py — Fires all daily touchpoints at the right times.
Runs in its own thread alongside the Telegram bot listener.
"""
import logging
import threading
import time
from datetime import date, datetime

import schedule

from . import memory, brain
from .telegram_bot import send_message_sync

logger = logging.getLogger(__name__)


def _is_busy_today() -> bool:
    return memory.get_profile("today_busy") == "true"


def _reset_busy_flag():
    """Clear the busy flag at midnight each day."""
    memory.set_profile("today_busy", "false")


def _run_touchpoint(name: str, skip_if_busy: bool = False):
    """Generate and send a scheduled touchpoint message."""
    if skip_if_busy and _is_busy_today():
        logger.info(f"Skipping '{name}' touchpoint — busy day flag set.")
        return

    logger.info(f"Running touchpoint: {name}")
    try:
        msg = brain.generate_message(name)
        send_message_sync(msg, touchpoint=name)
    except Exception as e:
        logger.error(f"Touchpoint '{name}' failed: {e}")


def _run_evening_summary():
    """At end of day, build and store a summary of what was learned."""
    try:
        today_msgs = memory.get_today_messages()
        if not today_msgs:
            return
        notes = brain.generate_evening_notes(today_msgs)
        memory.update_daily_summary(date.today().isoformat(), agent_notes=notes)
        logger.info("Evening summary stored.")
    except Exception as e:
        logger.error(f"Evening summary failed: {e}")


def _check_night_touchpoint():
    """
    Night check (22:30) only fires if there's an evening calendar event today
    that suggests Shaun might still be up.
    """
    try:
        today_log = memory.get_today_log()
        if not today_log:
            return
        ctx = today_log.get("day_context", {})
        events = ctx.get("calendar_events", [])
        evening_events = [
            e for e in events
            if isinstance(e.get("end"), str) and e["end"] >= f"{date.today().isoformat()}T21:00"
        ]
        if evening_events:
            logger.info(f"Evening events detected — running night check touchpoint.")
            _run_touchpoint("night_check")
        else:
            logger.info("No late evening events — skipping night check.")
    except Exception as e:
        logger.error(f"Night check error: {e}")


def setup_schedule():
    """Register all daily jobs with the schedule library."""

    # Morning briefing — 05:30 (Shaun wakes at 05:00, post-gym message as he showers/meditates)
    schedule.every().day.at("05:30").do(_run_touchpoint, name="morning")

    # Midday energy check
    schedule.every().day.at("12:30").do(_run_touchpoint, name="midday", skip_if_busy=True)

    # Afternoon productivity + pre-wind-down awareness
    schedule.every().day.at("16:00").do(_run_touchpoint, name="afternoon", skip_if_busy=True)

    # Evening wind-down trigger (30 min before melatonin)
    schedule.every().day.at("20:00").do(_run_touchpoint, name="evening")

    # Conditional night check
    schedule.every().day.at("22:30").do(_check_night_touchpoint)

    # Evening summary (after last expected message is sent)
    schedule.every().day.at("23:00").do(_run_evening_summary)

    # Reset busy flag at midnight
    schedule.every().day.at("00:01").do(_reset_busy_flag)

    logger.info("Schedule configured.")


def run_scheduler():
    """Run the scheduler loop (blocking — call in a thread)."""
    setup_schedule()
    logger.info("Scheduler running.")
    while True:
        schedule.run_pending()
        time.sleep(30)  # check every 30 seconds


def start_scheduler_thread() -> threading.Thread:
    t = threading.Thread(target=run_scheduler, daemon=True, name="scheduler")
    t.start()
    return t

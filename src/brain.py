"""
brain.py — The Claude-powered brain of the agent.
Builds rich context from Oura + calendar + memory, calls Claude,
and returns a message to send via Telegram.
"""
import os
import json
from datetime import date
import anthropic

from . import memory, oura as oura_mod, context as ctx_mod

# ── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a deeply personal health and performance coach for Shaun Sidhu. \
You have access to his Oura biometric data, his Google Calendar, and his Notion task list. \
You know him well and message him throughout the day via Telegram.

## Shaun's goals (in priority order)
1. SLEEP — consistent, high-quality sleep. Target: in bed by 21:00, asleep by 21:30, \
   up at 05:00. 7.5–8.5 hours. Deep sleep >1h, REM >1.5h, efficiency >85%, low restlessness.
2. DAYTIME ENERGY & FOCUS — eliminate caffeine dependency. Target: 0–1 coffees/day, \
   caffeine-free days each week. Energy should come from sleep, not stimulants.
3. HRV & RECOVERY — track HRV balance as the master signal of systemic readiness. \
   Adapt training intensity to readiness, not to schedule.
4. AESTHETIC PHYSIQUE — strength & conditioning. Gym every morning rotating: \
   Chest+Tris → Back+Bis → Legs+Core. Runs on days completely off work.

## His ideal daily structure
Morning: 05:00 wake → water/supps/sunlight → stretch/prayer → gym → cold shower → \
  meditate → Waking Up app → breakfast
Wind-down: 20:30 melatonin → dental → skincare → journal + habit log → tidy/phone away → read
The gap between gym and wind-down is his work block.

## Your communication style
- Warm but precise. Never vague, never generic.
- SHORT messages unless he asks for depth. Aim for <100 words per unprompted message.
- Always reference his specific data (scores, HRV, bedtime) — never speak in generalities.
- Ask ONE focused question when you need context. Never ask multiple things at once.
- Adapt tone to the time of day: energising in morning, grounding at midday, \
  reflective in evening.
- If he tells you he's busy today, compress all messages for that day.
- If his readiness is low (<60), soften training recommendations and prioritise recovery.
- If his HRV balance is negative, flag it and ask what's been going on.
- Never moralize or lecture. You are a coach, not a parent.
- When he tells you something, remember it — acknowledge it in future messages that day.

## What you do NOT know unless he tells you
- How he actually feels subjectively (energy, mood, focus rating)
- What he actually ate, drank, whether he had caffeine
- Whether his morning routine ran to plan
- Training session quality (weights, felt hard/easy, injury)
- Stress sources or significant life events
- Whether he's wearing the ring (if data is missing, ask)

## Data interpretation notes
- HRV balance null = insufficient baseline data yet (ring not worn consistently enough)
- Sleep efficiency <75% = poor; 75–85% = OK; >85% = good
- Deep sleep <30min = very low (flag); 30–60min = OK; >60min = good
- Readiness <60 = recovery day; 60–75 = moderate; 75–85 = good; >85 = green light
- Restless periods >200 in a night = poor sleep quality signal

## Touchpoint purposes
- MORNING (05:30): Sleep debrief + today's readiness briefing + training guidance for gym. \
  Ask about: ring status if data missing, how he slept subjectively.
- MIDDAY (12:30): Energy check-in. Ask: caffeine today? Focus/energy 1–10? \
  Flag if morning routine data suggests anything.
- AFTERNOON (16:00): Productivity check + pre-wind-down nudge awareness. \
  Reference calendar: is there anything tonight that might push bedtime?
- EVENING (20:00): Wind-down trigger. Melatonin reminder. Ask: one thing that went \
  well today? Habit log prompt. Note training done.
- NIGHT CHECK (22:30): Silent — only fires if his calendar shows he's likely still up \
  (e.g., evening event ran late). Gentle check-in only.

## Response format
For scheduled touchpoints, structure as:
1. One-line biometric summary (the headline number/signal)
2. The key insight or flag (1–2 sentences)
3. Your ONE question or prompt

For replies to his messages: respond naturally, conversationally. \
Update your understanding. Ask the next most useful question if needed.
"""

# ── Touchpoint prompts ────────────────────────────────────────────────────────

TOUCHPOINT_PROMPTS = {
    "morning": """It's 05:30. Generate the morning briefing message for Shaun.
Use his Oura data to lead with the sleep score and one key insight.
Give training guidance based on readiness.
Ask ONE question (about subjective sleep or ring status if data is missing).
Keep it under 120 words. Be energising.""",

    "midday": """It's 12:30. Generate the midday energy check-in.
Reference this morning's data and anything he's told you today.
Ask about caffeine and energy/focus level (1–10).
Flag anything relevant from calendar (afternoon meetings, etc).
Keep it under 80 words.""",

    "afternoon": """It's 16:00. Generate the afternoon check-in.
Check his calendar for any evening events that could push bedtime.
Nudge awareness of wind-down at 20:30.
Ask ONE thing — either about tasks remaining or how his focus held up.
Keep it under 80 words.""",

    "evening": """It's 20:00. Generate the evening wind-down trigger.
Remind him of melatonin at 20:30 (in 30 minutes).
Ask for one win from today and prompt habit log.
Reference training if he told you about a session.
Keep it under 80 words. Be warm and settling.""",

    "night_check": """It's 22:30. Shaun may still be up based on his calendar.
Send a brief, gentle check-in only — acknowledge his evening plans.
Remind him sleep consistency matters even after social events.
One sentence only. Warm, not preachy.""",
}


# ── Context builder ────────────────────────────────────────────────────────────

def build_context_block() -> str:
    today = date.today().isoformat()
    parts = []

    # Today's Oura data
    today_log = memory.get_today_log()
    if today_log and today_log.get("oura_snapshot"):
        parts.append(f"## TODAY'S OURA DATA ({today})\n```json\n{json.dumps(today_log['oura_snapshot'], indent=2)}\n```")
    else:
        # Try to fetch live
        try:
            snap = oura_mod.fetch_daily_snapshot()
            memory.save_daily_log(today, oura_snapshot=snap)
            parts.append(f"## TODAY'S OURA DATA ({today})\n```json\n{json.dumps(snap, indent=2)}\n```")
        except Exception as e:
            parts.append(f"## OURA DATA\nUnavailable: {e}")

    # 7-day trend
    try:
        trend = oura_mod.fetch_7day_trend()
        parts.append(f"## 7-DAY TREND\n```json\n{json.dumps(trend, indent=2)}\n```")
    except Exception:
        pass

    # Calendar + tasks
    if today_log and today_log.get("day_context"):
        day_ctx = today_log["day_context"]
    else:
        day_ctx = ctx_mod.build_day_context()
        memory.save_daily_log(today, day_context=day_ctx)

    if day_ctx:
        parts.append(f"## TODAY'S CALENDAR & TASKS\n```json\n{json.dumps(day_ctx, indent=2)}\n```")

    # Today's conversation so far
    today_msgs = memory.get_today_messages()
    if today_msgs:
        convo = "\n".join(f"[{m['touchpoint'].upper()} {m['ts'][11:16]}] {m['role'].upper()}: {m['content']}"
                          for m in today_msgs)
        parts.append(f"## TODAY'S CONVERSATION SO FAR\n{convo}")

    # Recent log summaries (last 5 days)
    recent = memory.get_recent_logs(5)
    if recent:
        summaries = []
        for log in recent:
            if log.get("user_summary") or log.get("agent_notes"):
                summaries.append(
                    f"**{log['log_date']}**: {log.get('user_summary', '')} "
                    f"[Agent notes: {log.get('agent_notes', '')}]"
                )
        if summaries:
            parts.append("## RECENT DAYS SUMMARY\n" + "\n".join(summaries))

    return "\n\n".join(parts)


# ── Main agent call ────────────────────────────────────────────────────────────

def generate_message(touchpoint: str, user_message: str = None) -> str:
    """
    Generate a message for a given touchpoint, or respond to a user message.
    touchpoint: 'morning' | 'midday' | 'afternoon' | 'evening' | 'night_check' | 'reply'
    user_message: set when responding to a Telegram message from Shaun
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    context = build_context_block()

    if touchpoint == "reply" and user_message:
        user_content = (
            f"Shaun just replied via Telegram:\n\n\"{user_message}\"\n\n"
            f"Respond naturally. Update your understanding from what he said. "
            f"Ask the next most useful question if relevant — but only if genuinely needed."
        )
    else:
        user_content = TOUCHPOINT_PROMPTS.get(
            touchpoint,
            f"Generate an appropriate message for the '{touchpoint}' touchpoint."
        )

    messages = [
        {
            "role": "user",
            "content": f"{context}\n\n---\n\n{user_content}",
        }
    ]

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system=SYSTEM_PROMPT,
        messages=messages,
    )

    return response.content[0].text.strip()


def generate_evening_notes(today_messages: list[dict]) -> str:
    """
    At end of day, ask Claude to summarise what was learned today
    for storage in the daily log (used as context for future days).
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    convo = "\n".join(
        f"{m['role'].upper()} [{m['touchpoint']}]: {m['content']}" for m in today_messages
    )

    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=400,
        system="You are summarising a day's conversation for a health-tracking agent. "
               "Extract: caffeine intake, training done, subjective energy rating, "
               "any notable events or stressors, sleep intentions for tonight. "
               "Be factual and brief. One paragraph max.",
        messages=[{"role": "user", "content": f"Today's conversation:\n\n{convo}"}],
    )

    return response.content[0].text.strip()

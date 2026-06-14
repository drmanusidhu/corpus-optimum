"""
memory.py — Lightweight SQLite store for conversation history, daily logs,
and rolling context summaries. Keeps the agent stateful across sessions.
"""
import sqlite3
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path


DB_PATH = Path(os.environ.get("AGENT_DB_PATH", "./data/agent.db"))


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with _conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS messages (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          TEXT    NOT NULL,
                role        TEXT    NOT NULL,   -- 'agent' | 'user'
                touchpoint  TEXT,               -- 'morning' | 'midday' | 'afternoon' | 'evening' | 'reply'
                content     TEXT    NOT NULL
            );

            CREATE TABLE IF NOT EXISTS daily_logs (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                log_date        TEXT    NOT NULL,
                oura_snapshot   TEXT,   -- JSON
                day_context     TEXT,   -- JSON (calendar + tasks)
                user_summary    TEXT,   -- free-text summary built from replies during the day
                agent_notes     TEXT    -- agent's own notes for tomorrow
            );

            CREATE TABLE IF NOT EXISTS user_profile (
                key     TEXT PRIMARY KEY,
                value   TEXT NOT NULL,
                updated TEXT NOT NULL
            );
        """)


# ── Messages ──────────────────────────────────────────────────────────────────

def save_message(role: str, content: str, touchpoint: str = "reply"):
    with _conn() as conn:
        conn.execute(
            "INSERT INTO messages (ts, role, touchpoint, content) VALUES (?, ?, ?, ?)",
            (datetime.utcnow().isoformat(), role, touchpoint, content),
        )


def get_recent_messages(limit: int = 40) -> list[dict]:
    with _conn() as conn:
        rows = conn.execute(
            "SELECT ts, role, touchpoint, content FROM messages ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(r) for r in reversed(rows)]


def get_today_messages() -> list[dict]:
    today = date.today().isoformat()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT ts, role, touchpoint, content FROM messages WHERE ts LIKE ? ORDER BY id",
            (f"{today}%",),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Daily logs ────────────────────────────────────────────────────────────────

def save_daily_log(log_date: str, oura_snapshot: dict = None, day_context: dict = None):
    with _conn() as conn:
        existing = conn.execute(
            "SELECT id FROM daily_logs WHERE log_date = ?", (log_date,)
        ).fetchone()
        if existing:
            conn.execute(
                """UPDATE daily_logs
                   SET oura_snapshot = COALESCE(?, oura_snapshot),
                       day_context   = COALESCE(?, day_context)
                   WHERE log_date = ?""",
                (
                    json.dumps(oura_snapshot) if oura_snapshot else None,
                    json.dumps(day_context) if day_context else None,
                    log_date,
                ),
            )
        else:
            conn.execute(
                "INSERT INTO daily_logs (log_date, oura_snapshot, day_context) VALUES (?, ?, ?)",
                (
                    log_date,
                    json.dumps(oura_snapshot) if oura_snapshot else None,
                    json.dumps(day_context) if day_context else None,
                ),
            )


def update_daily_summary(log_date: str, user_summary: str = None, agent_notes: str = None):
    with _conn() as conn:
        conn.execute(
            """UPDATE daily_logs
               SET user_summary = COALESCE(?, user_summary),
                   agent_notes  = COALESCE(?, agent_notes)
               WHERE log_date = ?""",
            (user_summary, agent_notes, log_date),
        )


def get_recent_logs(days: int = 7) -> list[dict]:
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    with _conn() as conn:
        rows = conn.execute(
            "SELECT * FROM daily_logs WHERE log_date >= ? ORDER BY log_date",
            (cutoff,),
        ).fetchall()
    result = []
    for r in rows:
        row = dict(r)
        for field in ("oura_snapshot", "day_context"):
            if row.get(field):
                try:
                    row[field] = json.loads(row[field])
                except Exception:
                    pass
        result.append(row)
    return result


def get_today_log() -> dict | None:
    today = date.today().isoformat()
    with _conn() as conn:
        row = conn.execute(
            "SELECT * FROM daily_logs WHERE log_date = ?", (today,)
        ).fetchone()
    if not row:
        return None
    result = dict(row)
    for field in ("oura_snapshot", "day_context"):
        if result.get(field):
            try:
                result[field] = json.loads(result[field])
            except Exception:
                pass
    return result


# ── User profile (persistent facts about the user) ────────────────────────────

def set_profile(key: str, value: str):
    with _conn() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO user_profile (key, value, updated) VALUES (?, ?, ?)",
            (key, value, datetime.utcnow().isoformat()),
        )


def get_profile(key: str) -> str | None:
    with _conn() as conn:
        row = conn.execute(
            "SELECT value FROM user_profile WHERE key = ?", (key,)
        ).fetchone()
    return row["value"] if row else None


def get_all_profile() -> dict:
    with _conn() as conn:
        rows = conn.execute("SELECT key, value FROM user_profile").fetchall()
    return {r["key"]: r["value"] for r in rows}

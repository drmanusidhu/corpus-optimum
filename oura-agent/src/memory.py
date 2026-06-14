"""
Memory store - SQLite database for tracking messages, patterns, and learnings
"""

import sqlite3
from datetime import datetime, timedelta
import json


class MemoryStore:
    """SQLite-based memory for agent and user interactions"""
    
    def __init__(self, db_path="agent.db"):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        """Initialize database tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Messages table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                direction TEXT,
                content TEXT,
                metadata TEXT
            )
        """)
        
        # Daily logs table (for aggregated learnings)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_logs (
                date TEXT PRIMARY KEY,
                readiness_score REAL,
                sleep_hours REAL,
                deep_sleep REAL,
                rem_sleep REAL,
                sleep_efficiency REAL,
                notes TEXT
            )
        """)
        
        # Status table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS status (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        conn.close()
    
    def log_user_message(self, content, metadata=None):
        """Log a user message"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (direction, content, metadata) VALUES (?, ?, ?)",
            ("user", content, json.dumps(metadata or {}))
        )
        conn.commit()
        conn.close()
    
    def log_agent_message(self, content, metadata=None):
        """Log an agent message"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (direction, content, metadata) VALUES (?, ?, ?)",
            ("agent", content, json.dumps(metadata or {}))
        )
        conn.commit()
        conn.close()
    
    def get_recent_messages(self, hours=None, days=None):
        """Get recent messages for context"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        if hours:
            cutoff = datetime.now() - timedelta(hours=hours)
        elif days:
            cutoff = datetime.now() - timedelta(days=days)
        else:
            cutoff = datetime.now() - timedelta(hours=1)
        
        cursor.execute(
            "SELECT timestamp, direction, content FROM messages WHERE timestamp > ? ORDER BY timestamp DESC LIMIT 20",
            (cutoff,)
        )
        
        messages = cursor.fetchall()
        conn.close()
        
        return "\n".join([f"[{m[0]}] {m[1].upper()}: {m[2]}" for m in messages])
    
    def log_daily_data(self, date, readiness, sleep_data):
        """Log daily Oura snapshot"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT OR REPLACE INTO daily_logs 
            (date, readiness_score, sleep_hours, deep_sleep, rem_sleep, sleep_efficiency)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            date,
            readiness,
            sleep_data.get("total_sleep_duration", 0) / 3600,
            sleep_data.get("deep_sleep_duration", 0) / 3600,
            sleep_data.get("rem_sleep_duration", 0) / 3600,
            sleep_data.get("sleep_efficiency", 0)
        ))
        
        conn.commit()
        conn.close()
    
    def set_busy_until(self, until_time):
        """Mark user as busy until a certain time"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO status (key, value) VALUES (?, ?)",
            ("busy_until", until_time.isoformat())
        )
        conn.commit()
        conn.close()
    
    def clear_busy(self):
        """Clear busy status"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM status WHERE key = ?", ("busy_until",))
        conn.commit()
        conn.close()
    
    def is_busy(self):
        """Check if user is currently busy"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM status WHERE key = ?", ("busy_until",))
        result = cursor.fetchone()
        conn.close()
        
        if result:
            busy_until = datetime.fromisoformat(result[0])
            return datetime.now() < busy_until
        return False

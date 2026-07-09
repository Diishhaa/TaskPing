import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from loguru import logger
import sys

# Add src to system path to import config
sys.path.append(str(Path(__file__).resolve().parents[2]))
import config

def get_db_connection() -> sqlite3.Connection:
    """Establishes and returns a connection to the SQLite database."""
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Initializes the database, creating the necessary tables if they do not exist."""
    logger.info("Initializing SQLite database...")
    config.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        # Table to store hackathons
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hackathons (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                url TEXT NOT NULL UNIQUE,
                platform TEXT NOT NULL,
                hash TEXT NOT NULL,
                first_seen TEXT NOT NULL,
                last_seen TEXT NOT NULL,
                notification_sent INTEGER DEFAULT 0,
                priority_score REAL DEFAULT 0.0,
                deadline TEXT,
                registration_open_date TEXT,
                image_url TEXT,
                prize_pool TEXT,
                location TEXT,
                is_online INTEGER DEFAULT 0,
                country TEXT,
                theme TEXT,
                organizer TEXT,
                participants_count INTEGER,
                difficulty TEXT,
                description TEXT,
                tags TEXT,
                team_required INTEGER DEFAULT 0,
                reminder_7d_sent INTEGER DEFAULT 0,
                reminder_3d_sent INTEGER DEFAULT 0,
                reminder_24h_sent INTEGER DEFAULT 0,
                reminder_3h_sent INTEGER DEFAULT 0,
                keyword_match_sent INTEGER DEFAULT 0
            )
        """)
        
        # Table to store system settings/metadata (e.g. last daily summary run)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        conn.commit()
    logger.info(f"Database initialized at: {config.DB_PATH}")

def save_hackathons(hackathons: List[Dict[str, Any]]) -> int:
    """
    Saves a list of parsed hackathons to the database.
    Returns the number of brand new hackathons added.
    """
    if not hackathons:
        return 0
    
    new_count = 0
    now_str = datetime.now(timezone.utc).isoformat()
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        for h in hackathons:
            # Check if hackathon already exists by URL
            cursor.execute("SELECT id, notification_sent FROM hackathons WHERE url = ?", (h["url"],))
            row = cursor.fetchone()
            
            if row:
                # Update last_seen and any fields that might have changed
                cursor.execute("""
                    UPDATE hackathons 
                    SET last_seen = ?,
                        title = ?,
                        priority_score = ?,
                        deadline = ?,
                        prize_pool = ?,
                        participants_count = ?,
                        description = ?,
                        tags = ?,
                        image_url = ?
                    WHERE url = ?
                """, (
                    now_str,
                    h["title"],
                    h.get("priority_score", 0.0),
                    h.get("deadline"),
                    h.get("prize_pool"),
                    h.get("participants_count"),
                    h.get("description"),
                    json.dumps(h.get("tags", [])),
                    h.get("image_url"),
                    h["url"]
                ))
            else:
                # Insert as a brand new hackathon
                cursor.execute("""
                    INSERT INTO hackathons (
                        id, title, url, platform, hash, first_seen, last_seen, 
                        notification_sent, priority_score, deadline, registration_open_date, 
                        image_url, prize_pool, location, is_online, country, theme, 
                        organizer, participants_count, difficulty, description, tags, team_required
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    h["id"],
                    h["title"],
                    h["url"],
                    h["platform"],
                    h["hash"],
                    now_str,
                    now_str,
                    h.get("priority_score", 0.0),
                    h.get("deadline"),
                    h.get("registration_open_date"),
                    h.get("image_url"),
                    h.get("prize_pool"),
                    h.get("location"),
                    1 if h.get("is_online") else 0,
                    h.get("country"),
                    h.get("theme"),
                    h.get("organizer"),
                    h.get("participants_count"),
                    h.get("difficulty"),
                    h.get("description"),
                    json.dumps(h.get("tags", [])),
                    1 if h.get("team_required") else 0
                ))
                new_count += 1
        conn.commit()
        
    logger.info(f"Database sync complete. New: {new_count}, Total Processed: {len(hackathons)}")
    return new_count

def get_unnotified_hackathons() -> List[Dict[str, Any]]:
    """Returns a list of hackathons that haven't been notified yet."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hackathons WHERE notification_sent = 0")
        rows = cursor.fetchall()
        return [dict(r) for r in rows]

def mark_as_notified(url: str):
    """Marks a hackathon's initial notification as sent."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE hackathons SET notification_sent = 1 WHERE url = ?", (url,))
        conn.commit()

def mark_keyword_match_as_notified(url: str):
    """Marks a hackathon's keyword notification as sent."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE hackathons SET keyword_match_sent = 1 WHERE url = ?", (url,))
        conn.commit()

def get_upcoming_reminders() -> List[Tuple[Dict[str, Any], str]]:
    """
    Checks active hackathons and returns a list of tuples containing:
    (hackathon_dict, reminder_level)
    reminder_level can be '7d', '3d', '24h', '3h'.
    """
    reminders = []
    now = datetime.now(timezone.utc)
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Only select events with a valid deadline that are in the future
        cursor.execute("""
            SELECT * FROM hackathons 
            WHERE deadline IS NOT NULL 
              AND deadline != ''
        """)
        rows = cursor.fetchall()
        
        for row in rows:
            h = dict(row)
            try:
                deadline = datetime.fromisoformat(h["deadline"])
                # Handle naive vs aware datetime objects (assume UTC if naive)
                if deadline.tzinfo is None:
                    deadline = deadline.replace(tzinfo=timezone.utc)
                
                time_left = deadline - now
                hours_left = time_left.total_seconds() / 3600.0
                
                # Check for reminders in order of priority (most urgent first)
                if 0 < hours_left <= 3:
                    if not h["reminder_3h_sent"]:
                        reminders.append((h, "3h"))
                elif hours_left <= 24:
                    if not h["reminder_24h_sent"]:
                        reminders.append((h, "24h"))
                elif hours_left <= 72:
                    if not h["reminder_3d_sent"]:
                        reminders.append((h, "3d"))
                elif hours_left <= 168:
                    if not h["reminder_7d_sent"]:
                        reminders.append((h, "7d"))
            except Exception as e:
                logger.debug(f"Failed to parse deadline '{h['deadline']}' for reminders: {e}")
                continue
                
    return reminders

def mark_reminder_as_sent(url: str, level: str):
    """Marks a specific reminder level as sent for a hackathon."""
    column_name = f"reminder_{level}_sent"
    valid_columns = ["reminder_7d_sent", "reminder_3d_sent", "reminder_24h_sent", "reminder_3h_sent"]
    if column_name not in valid_columns:
        logger.error(f"Invalid reminder column: {column_name}")
        return
        
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"UPDATE hackathons SET {column_name} = 1 WHERE url = ?", (url,))
        conn.commit()

def get_stats() -> Dict[str, Any]:
    """Retrieves basic counts and statistics from the database."""
    stats = {}
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM hackathons")
        stats["total_count"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM hackathons WHERE notification_sent = 1")
        stats["notified_count"] = cursor.fetchone()[0]
        
        # Counts by priority
        cursor.execute("SELECT COUNT(*) FROM hackathons WHERE priority_score >= 70")
        stats["high_priority_count"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM hackathons WHERE priority_score >= 40 AND priority_score < 70")
        stats["medium_priority_count"] = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM hackathons WHERE priority_score < 40")
        stats["low_priority_count"] = cursor.fetchone()[0]
        
        # Counts by platform
        cursor.execute("SELECT platform, COUNT(*) FROM hackathons GROUP BY platform")
        stats["by_platform"] = {row[0]: row[1] for row in cursor.fetchall()}
        
    return stats

def get_recommendations(limit: int = 5) -> List[Dict[str, Any]]:
    """Returns top N hackathons sorted by priority score (high to low)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM hackathons 
            ORDER BY priority_score DESC 
            LIMIT ?
        """, (limit,))
        return [dict(r) for r in cursor.fetchall()]

def get_upcoming_deadlines(limit: int = 5) -> List[Dict[str, Any]]:
    """Returns upcoming active hackathons closest to their deadline."""
    now_str = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM hackathons 
            WHERE deadline IS NOT NULL 
              AND deadline > ?
            ORDER BY deadline ASC 
            LIMIT ?
        """, (now_str, limit))
        return [dict(r) for r in cursor.fetchall()]

def get_setting(key: str, default: Optional[str] = None) -> Optional[str]:
    """Fetches a setting value from the settings table."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        row = cursor.fetchone()
        return row[0] if row else default

def set_setting(key: str, value: str):
    """Sets a setting value in the settings table."""
    now_str = datetime.now(timezone.utc).isoformat()
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO settings (key, value, updated_at) 
            VALUES (?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at
        """, (key, value, now_str))
        conn.commit()

def export_all_hackathons() -> List[Dict[str, Any]]:
    """Retrieves all hackathons in the database."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM hackathons ORDER BY first_seen DESC")
        return [dict(r) for r in cursor.fetchall()]

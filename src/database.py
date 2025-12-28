import sqlite3
import hashlib
from datetime import datetime, timedelta
import logging

DB_NAME = "news_bot.db"
logger = logging.getLogger(__name__)

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    """Initialize the database schema."""
    conn = get_connection()
    c = conn.cursor()
    
    # Users table
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            selected_unit TEXT DEFAULT 'global',
            last_active DATETIME
        )
    ''')
    
    # Seen news table (to prevent duplicates)
    c.execute('''
        CREATE TABLE IF NOT EXISTS seen_news (
            url_hash TEXT PRIMARY KEY,
            url TEXT,
            seen_at DATETIME
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Database initialized.")

def add_user(user_id, username=None):
    """Add a new user or update existing."""
    conn = get_connection()
    c = conn.cursor()
    try:
        c.execute('''
            INSERT OR IGNORE INTO users (user_id, username, selected_unit, last_active)
            VALUES (?, ?, 'none', ?)
        ''', (user_id, username, datetime.now()))
        conn.commit()
    except Exception as e:
        logger.error(f"Error adding user {user_id}: {e}")
    finally:
        conn.close()

def update_user_unit(user_id, unit):
    """Update the selected news unit for a user."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('UPDATE users SET selected_unit = ?, last_active = ? WHERE user_id = ?', 
              (unit, datetime.now(), user_id))
    conn.commit()
    conn.close()

def get_user_unit(user_id):
    """Get the selected unit for a user. Returns 'global' if user not found."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT selected_unit FROM users WHERE user_id = ?', (user_id,))
    row = c.fetchone()
    conn.close()
    return row[0] if row else 'global'

def get_all_users():
    """Return all users as a list of dicts."""
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT user_id, selected_unit FROM users')
    rows = c.fetchall()
    conn.close()
    return [{'user_id': r[0], 'unit': r[1]} for r in rows]

def _hash_url(url):
    return hashlib.md5(url.encode('utf-8')).hexdigest()

def is_news_seen(url):
    """Check if a news URL has already been processed."""
    url_hash = _hash_url(url)
    conn = get_connection()
    c = conn.cursor()
    c.execute('SELECT 1 FROM seen_news WHERE url_hash = ?', (url_hash,))
    exists = c.fetchone() is not None
    conn.close()
    return exists

def mark_news_as_seen(url):
    """Mark a news URL as seen."""
    url_hash = _hash_url(url)
    conn = get_connection()
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO seen_news (url_hash, url, seen_at) VALUES (?, ?, ?)',
              (url_hash, url, datetime.now()))
    conn.commit()
    conn.close()

def cleanup_seen_news(days=3):
    """Remove seen news older than X days to keep DB small."""
    cutoff = datetime.now() - timedelta(days=days)
    conn = get_connection()
    c = conn.cursor()
    c.execute('DELETE FROM seen_news WHERE seen_at < ?', (cutoff,))
    deleted = c.rowcount
    conn.commit()
    conn.close()
    logger.info(f"Cleaned up {deleted} old news items.")

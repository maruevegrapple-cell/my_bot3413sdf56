import sqlite3
import time

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        referrer INTEGER,
        balance INTEGER DEFAULT 0,
        last_bonus INTEGER DEFAULT 0,
        invited INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_videos (
        user_id INTEGER,
        video_id INTEGER,
        UNIQUE(user_id, video_id)
    )
    """)

    conn.commit()

def add_user(user_id, referrer=None):
    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, referrer) VALUES (?, ?)",
        (user_id, referrer)
    )
    conn.commit()

def add_balance(user_id, amount):
    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id=?",
        (amount, user_id)
    )
    conn.commit()

def get_balance(user_id):
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    row = cursor.fetchone()
    return row[0] if row else 0

def get_random_video():
    cursor.execute("SELECT id, file_id FROM videos ORDER BY RANDOM() LIMIT 1")
    return cursor.fetchone()

def video_sent(user_id, video_id):
    cursor.execute(
        "SELECT 1 FROM user_videos WHERE user_id=? AND video_id=?",
        (user_id, video_id)
    )
    return cursor.fetchone() is not None

def mark_video(user_id, video_id):
    cursor.execute(
        "INSERT OR IGNORE INTO user_videos VALUES (?, ?)",
        (user_id, video_id)
    )
    conn.commit()

def save_video(file_id):
    cursor.execute("INSERT INTO videos (file_id) VALUES (?)", (file_id,))
    conn.commit()

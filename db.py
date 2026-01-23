import sqlite3
import time

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0,
        ref_used INTEGER DEFAULT 0,
        last_bonus_ts INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT UNIQUE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_videos (
        user_id INTEGER,
        video_id INTEGER,
        UNIQUE(user_id, video_id)
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promo_codes (
        code TEXT PRIMARY KEY,
        amount INTEGER,
        active INTEGER DEFAULT 1
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS used_promos (
        user_id INTEGER,
        code TEXT,
        UNIQUE(user_id, code)
    )
    """)

    conn.commit()

def get_user(user_id):
    cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return get_user(user_id)
    return user

def update_balance(user_id, amount):
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    conn.commit()

def set_ref_used(user_id):
    cursor.execute("UPDATE users SET ref_used=1 WHERE user_id=?", (user_id,))
    conn.commit()

def can_take_bonus(user_id):
    cursor.execute("SELECT last_bonus_ts FROM users WHERE user_id=?", (user_id,))
    last = cursor.fetchone()[0]
    return time.time() - last >= 3600

def take_bonus(user_id):
    cursor.execute("UPDATE users SET last_bonus_ts=?, balance=balance+3 WHERE user_id=?", (int(time.time()), user_id))
    conn.commit()

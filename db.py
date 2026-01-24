import sqlite3
import time

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0,
        ref_used INTEGER DEFAULT 0,
        last_bonus INTEGER DEFAULT 0
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promo_codes (
        code TEXT PRIMARY KEY,
        amount INTEGER,
        active INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS used_promos (
        user_id INTEGER,
        code TEXT,
        PRIMARY KEY (user_id, code)
    )
    """)

    # ✅ ТАБЛИЦА ДЛЯ ВИДЕО (ЗАЩИТА ОТ ПОВТОРОВ)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS watched_videos (
        user_id INTEGER,
        video_id TEXT,
        PRIMARY KEY (user_id, video_id)
    )
    """)

    conn.commit()


def get_user(user_id):
    cursor.execute(
        "SELECT user_id, balance, ref_used, last_bonus FROM users WHERE user_id=?",
        (user_id,)
    )
    user = cursor.fetchone()

    if not user:
        cursor.execute(
            "INSERT INTO users (user_id) VALUES (?)",
            (user_id,)
        )
        conn.commit()
        return (user_id, 0, 0, 0)

    return user


def update_balance(user_id, amount):
    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id=?",
        (amount, user_id)
    )
    conn.commit()


def set_ref_used(user_id):
    cursor.execute(
        "UPDATE users SET ref_used = 1 WHERE user_id=?",
        (user_id,)
    )
    conn.commit()


def can_take_bonus(user_id):
    cursor.execute(
        "SELECT last_bonus FROM users WHERE user_id=?",
        (user_id,)
    )
    last = cursor.fetchone()[0]
    return time.time() - last >= 3600


def take_bonus(user_id):
    cursor.execute(
        "UPDATE users SET balance = balance + 5, last_bonus=? WHERE user_id=?",
        (int(time.time()), user_id)
    )
    conn.commit()

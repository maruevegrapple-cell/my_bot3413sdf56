import sqlite3
import time

conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()


def init_db():
    # USERS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        balance INTEGER DEFAULT 0,
        ref_used INTEGER DEFAULT 0,
        last_bonus INTEGER DEFAULT 0
    )
    """)

    # VIDEOS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT UNIQUE
    )
    """)

    # WATCHED VIDEOS (ANTI-REPEAT)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS watched_videos (
        user_id INTEGER,
        video_id INTEGER,
        PRIMARY KEY (user_id, video_id)
    )
    """)

    # PROMO
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
        PRIMARY KEY (user_id, code)
    )
    """)

    conn.commit()


# ================= USERS =================

def get_user(user_id: int):
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


def update_balance(user_id: int, amount: int):
    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id=?",
        (amount, user_id)
    )
    conn.commit()


def set_ref_used(user_id: int):
    cursor.execute(
        "UPDATE users SET ref_used = 1 WHERE user_id=?",
        (user_id,)
    )
    conn.commit()


# ================= BONUS =================

def can_take_bonus(user_id: int):
    cursor.execute(
        "SELECT last_bonus FROM users WHERE user_id=?",
        (user_id,)
    )
    last = cursor.fetchone()[0]
    return time.time() - last >= 3600


def take_bonus(user_id: int):
    cursor.execute(
        "UPDATE users SET balance = balance + 3, last_bonus=? WHERE user_id=?",
        (int(time.time()), user_id)
    )
    conn.commit()


# ================= VIDEO =================

def add_video(file_id: str):
    cursor.execute(
        "INSERT OR IGNORE INTO videos (file_id) VALUES (?)",
        (file_id,)
    )
    conn.commit()


def get_unwatched_video(user_id: int):
    cursor.execute("""
    SELECT v.file_id, v.id FROM videos v
    WHERE v.id NOT IN (
        SELECT video_id FROM watched_videos WHERE user_id=?
    )
    ORDER BY RANDOM()
    LIMIT 1
    """, (user_id,))
    return cursor.fetchone()


def mark_video_watched(user_id: int, video_id: int):
    cursor.execute(
        "INSERT OR IGNORE INTO watched_videos (user_id, video_id) VALUES (?, ?)",
        (user_id, video_id)
    )
    conn.commit()


# ================= PROMO =================

def create_promo(code: str, amount: int):
    cursor.execute(
        "INSERT OR REPLACE INTO promo_codes (code, amount, active) VALUES (?, ?, 1)",
        (code.upper(), amount)
    )
    conn.commit()


def delete_promo(code: str):
    cursor.execute(
        "DELETE FROM promo_codes WHERE code=?",
        (code.upper(),)
    )
    conn.commit()


def get_promo(code: str):
    cursor.execute(
        "SELECT amount FROM promo_codes WHERE code=? AND active=1",
        (code.upper(),)
    )
    row = cursor.fetchone()
    return row[0] if row else None


def is_promo_used(user_id: int, code: str):
    cursor.execute(
        "SELECT 1 FROM used_promos WHERE user_id=? AND code=?",
        (user_id, code.upper())
    )
    return cursor.fetchone() is not None


def use_promo(user_id: int, code: str, amount: int):
    update_balance(user_id, amount)
    cursor.execute(
        "INSERT INTO used_promos (user_id, code) VALUES (?, ?)",
        (user_id, code.upper())
    )
    conn.commit()

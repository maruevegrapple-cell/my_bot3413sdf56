import os
import sqlite3

DB_PATH = "/data/database.db"
os.makedirs("/data", exist_ok=True)

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()


def init_db():
    # USERS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance INTEGER DEFAULT 0,
        referrer INTEGER,
        last_bonus INTEGER DEFAULT 0,
        is_verified INTEGER DEFAULT 0
    )
    """)

    # VIDEOS
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT UNIQUE
    )
    """)

    # USER → VIDEO
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_videos (
        user_id INTEGER,
        video_id INTEGER,
        UNIQUE(user_id, video_id)
    )
    """)

    # PROMOCODES
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promocodes (
        code TEXT PRIMARY KEY,
        reward INTEGER,
        activations_left INTEGER
    )
    """)

    # USED PROMOCODES (1 КОД = 1 РАЗ НА ЮЗЕРА)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS used_promocodes (
        user_id INTEGER,
        code TEXT,
        UNIQUE(user_id, code)
    )
    """)

    conn.commit()

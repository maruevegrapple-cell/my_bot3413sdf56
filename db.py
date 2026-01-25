import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

def init_db():
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
    CREATE TABLE IF NOT EXISTS promocodes (
        code TEXT PRIMARY KEY,
        reward INTEGER,
        activations_left INTEGER
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promo_uses (
        user_id INTEGER,
        code TEXT,
        UNIQUE(user_id, code)
    )
    """)

    conn.commit()

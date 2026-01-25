import sqlite3

conn = sqlite3.connect("database.db")
cursor = conn.cursor()


def init_db():
    # ================= USERS =================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance INTEGER DEFAULT 0,
        referrer INTEGER,
        is_verified INTEGER DEFAULT 0,
        last_bonus INTEGER DEFAULT 0,
        waiting_promo INTEGER DEFAULT 0
    )
    """)

    # ================= VIDEOS =================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT UNIQUE
    )
    """)

    # ================= USER VIDEOS =================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_videos (
        user_id INTEGER,
        video_id INTEGER,
        UNIQUE(user_id, video_id)
    )
    """)

    # ================= PROMOCODES =================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promocodes (
        code TEXT PRIMARY KEY,
        reward INTEGER NOT NULL,
        activations_left INTEGER NOT NULL
    )
    """)

    # ================= PROMO USES =================
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promo_uses (
        user_id INTEGER,
        code TEXT,
        UNIQUE(user_id, code)
    )
    """)

    conn.commit()


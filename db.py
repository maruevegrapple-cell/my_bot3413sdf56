import sqlite3
import random
import string
import os

if os.environ.get('RAILWAY_ENVIRONMENT'):
    DB_PATH = "/data/database.db"
    os.makedirs('/data', exist_ok=True)
    print(f"✅ Railway mode: БД будет в {DB_PATH}")
else:
    DB_PATH = "database.db"
    print(f"✅ Local mode: БД будет в {DB_PATH}")

conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=30)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

cursor.execute("PRAGMA journal_mode=WAL")
cursor.execute("PRAGMA synchronous=FULL")

def generate_ref_code(length=6):
    """Генерация уникального реферального кода"""
    chars = string.ascii_uppercase + string.digits
    chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
    
    while True:
        code = ''.join(random.choices(chars, k=length))
        cursor.execute("SELECT user_id FROM users WHERE ref_code = ?", (code,))
        if not cursor.fetchone():
            return code

def get_main_admin_id():
    """Получение ID главного админа из базы"""
    try:
        cursor.execute("SELECT user_id FROM admins WHERE is_main_admin = 1 LIMIT 1")
        row = cursor.fetchone()
        if row:
            return row["user_id"]
    except:
        pass
    return None

def set_main_admin(user_id: int, username: str = ""):
    """Установка главного админа (при первом запуске)"""
    try:
        current_main = get_main_admin_id()
        if current_main:
            return current_main
        
        cursor.execute("""
            INSERT OR REPLACE INTO users (user_id, username, is_verified, is_admin)
            VALUES (?, ?, 1, 1)
        """, (user_id, username))
        
        cursor.execute("""
            INSERT OR REPLACE INTO admins (user_id, username, added_by, added_at, is_main_admin, can_add_admins)
            VALUES (?, ?, ?, datetime('now'), 1, 1)
        """, (user_id, username, user_id))
        
        conn.commit()
        return user_id
    except Exception as e:
        print(f"❌ Ошибка установки главного админа: {e}")
        return None

def init_db():
    """Инициализация базы данных"""
    # Таблица пользователей
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        balance INTEGER DEFAULT 0,
        referrer INTEGER,
        last_bonus INTEGER DEFAULT 0,
        is_verified INTEGER DEFAULT 0,
        ref_code TEXT UNIQUE,
        subscribe_bonus_received INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0,
        pending_referrer_bonus INTEGER DEFAULT NULL
    )
    """)
    
    # Проверяем колонку pending_referrer_bonus
    try:
        cursor.execute("SELECT pending_referrer_bonus FROM users LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN pending_referrer_bonus INTEGER DEFAULT NULL")
            print("✅ Добавлена колонка pending_referrer_bonus")
        except:
            pass

    # Таблица админов
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS admins (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        added_by INTEGER,
        added_at TEXT,
        is_main_admin INTEGER DEFAULT 0,
        can_add_admins INTEGER DEFAULT 0,
        FOREIGN KEY (added_by) REFERENCES users (user_id)
    )
    """)

    # Таблица обязательных каналов
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mandatory_channels (
        channel_id TEXT PRIMARY KEY,
        channel_name TEXT,
        channel_link TEXT
    )
    """)

    # Таблица видео с колонкой is_private
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT UNIQUE,
        is_private INTEGER DEFAULT 0
    )
    """)

    # Таблица просмотренных видео
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_videos (
        user_id INTEGER,
        video_id INTEGER,
        UNIQUE(user_id, video_id)
    )
    """)

    # Таблица промокодов
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promocodes (
        code TEXT PRIMARY KEY,
        reward INTEGER,
        activations_left INTEGER
    )
    """)

    # Таблица использованных промокодов
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS used_promocodes (
        user_id INTEGER,
        code TEXT,
        UNIQUE(user_id, code)
    )
    """)

    # Таблица платежей
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        invoice_id TEXT PRIMARY KEY,
        user_id INTEGER,
        amount INTEGER,
        paid INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Проверяем колонку paid
    try:
        cursor.execute("SELECT paid FROM payments LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE payments ADD COLUMN paid INTEGER DEFAULT 0")
            print("✅ Добавлена колонка paid")
        except:
            pass
    
    conn.commit()
    print("✅ База данных инициализирована")

# ========== ФУНКЦИИ ДЛЯ КАНАЛОВ ОП ==========
def get_mandatory_channels():
    try:
        cursor.execute("SELECT channel_id, channel_name, channel_link FROM mandatory_channels")
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []

def add_mandatory_channel(channel_id, channel_name, channel_link):
    try:
        cursor.execute(
            "INSERT OR REPLACE INTO mandatory_channels (channel_id, channel_name, channel_link) VALUES (?, ?, ?)",
            (channel_id, channel_name, channel_link)
        )
        conn.commit()
        return True
    except:
        return False

def remove_mandatory_channel(channel_id):
    try:
        cursor.execute("DELETE FROM mandatory_channels WHERE channel_id = ?", (channel_id,))
        conn.commit()
        return True
    except:
        return False

# ========== ФУНКЦИИ ДЛЯ АДМИНОВ ==========
def is_admin(user_id: int) -> bool:
    try:
        cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row and row["is_admin"] == 1
    except:
        return False

def is_main_admin(user_id: int) -> bool:
    try:
        cursor.execute("SELECT is_main_admin FROM admins WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row and row["is_main_admin"] == 1
    except:
        return False

def can_manage_admins(user_id: int) -> bool:
    try:
        if is_main_admin(user_id):
            return True
        cursor.execute("SELECT can_add_admins FROM admins WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row and row["can_add_admins"] == 1
    except:
        return False

def get_all_admins():
    try:
        cursor.execute("""
            SELECT a.user_id, a.username, a.added_at, a.is_main_admin, a.can_add_admins, u.username as current_username
            FROM admins a
            LEFT JOIN users u ON a.user_id = u.user_id
            ORDER BY a.is_main_admin DESC, a.added_at
        """)
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []

def add_admin(admin_id: int, username: str, added_by: int, can_add: bool = False):
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO users (user_id, username, is_verified, is_admin)
            VALUES (?, ?, 1, 1)
        """, (admin_id, username))
        cursor.execute("""
            INSERT OR REPLACE INTO admins (user_id, username, added_by, added_at, is_main_admin, can_add_admins)
            VALUES (?, ?, ?, datetime('now'), 0, ?)
        """, (admin_id, username, added_by, 1 if can_add else 0))
        conn.commit()
        return True
    except:
        return False

def remove_admin(admin_id: int):
    try:
        cursor.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (admin_id,))
        cursor.execute("DELETE FROM admins WHERE user_id = ?", (admin_id,))
        conn.commit()
        return True
    except:
        return False

# ========== ФУНКЦИИ ДЛЯ БОНУСОВ ==========
def has_received_subscribe_bonus(user_id: int) -> bool:
    try:
        cursor.execute("SELECT subscribe_bonus_received FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row and row["subscribe_bonus_received"] == 1
    except:
        return False

def mark_subscribe_bonus_received(user_id: int):
    try:
        cursor.execute("UPDATE users SET subscribe_bonus_received = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except:
        return False

def update_last_bonus(user_id: int, timestamp: int):
    try:
        cursor.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (timestamp, user_id))
        conn.commit()
        return True
    except:
        return False

def get_bonus_stats():
    try:
        cursor.execute("SELECT COUNT(*) as users_took_bonus FROM users WHERE last_bonus > 0")
        row = cursor.fetchone()
        return {"users_took_bonus": row["users_took_bonus"] if row else 0}
    except:
        return {"users_took_bonus": 0}

# ========== ФУНКЦИИ ДЛЯ ПОЛЬЗОВАТЕЛЕЙ ==========
def get_user(user_id: int):
    try:
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None

def update_user_balance(user_id: int, amount: int):
    try:
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        return True
    except:
        return False

def get_referrals_count(user_id: int) -> int:
    try:
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE referrer = ?", (user_id,))
        row = cursor.fetchone()
        return row["count"] if row else 0
    except:
        return 0

def get_user_by_ref_code(ref_code: str):
    try:
        cursor.execute("SELECT user_id FROM users WHERE ref_code = ?", (ref_code,))
        row = cursor.fetchone()
        return row["user_id"] if row else None
    except:
        return None

def get_top_referrers(limit: int = 10):
    try:
        cursor.execute("""
            SELECT u.user_id, u.username, u.balance, COUNT(r.user_id) as referrals_count
            FROM users u
            LEFT JOIN users r ON r.referrer = u.user_id
            GROUP BY u.user_id
            HAVING referrals_count > 0
            ORDER BY referrals_count DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []

# ========== ФУНКЦИИ ДЛЯ ПЛАТЕЖЕЙ ==========
def add_payment(invoice_id: str, user_id: int, amount: int):
    try:
        cursor.execute("INSERT INTO payments (invoice_id, user_id, amount) VALUES (?, ?, ?)", (invoice_id, user_id, amount))
        conn.commit()
        return True
    except:
        return False

def mark_payment_paid(invoice_id: str):
    try:
        cursor.execute("UPDATE payments SET paid = 1 WHERE invoice_id = ?", (invoice_id,))
        conn.commit()
        return True
    except:
        return False

def get_payment(invoice_id: str):
    try:
        cursor.execute("SELECT * FROM payments WHERE invoice_id = ?", (invoice_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None

def get_user_payments(user_id: int, limit: int = 10):
    """Получение платежей пользователя"""
    try:
        cursor.execute("""
            SELECT * FROM payments 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (user_id, limit))
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []

def get_payments_stats():
    try:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_attempts,
                SUM(CASE WHEN paid = 1 THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN paid = 0 THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN paid = 1 THEN amount ELSE 0 END) as total_candies
            FROM payments
        """)
        return dict(cursor.fetchone())
    except:
        return {"total_attempts": 0, "successful": 0, "pending": 0, "total_candies": 0}

# ========== ФУНКЦИИ ДЛЯ ВИДЕО ==========
def get_all_videos():
    try:
        cursor.execute("SELECT id, file_id, is_private FROM videos ORDER BY id")
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []

def get_video_count() -> int:
    try:
        cursor.execute("SELECT COUNT(*) as count FROM videos")
        row = cursor.fetchone()
        return row["count"] if row else 0
    except:
        return 0

def add_video(file_id: str):
    try:
        cursor.execute("INSERT INTO videos (file_id) VALUES (?)", (file_id,))
        conn.commit()
        return True
    except:
        return False

def get_user_watched_videos(user_id: int):
    """Получение просмотренных пользователем видео"""
    try:
        cursor.execute("SELECT video_id FROM user_videos WHERE user_id = ?", (user_id,))
        return [row["video_id"] for row in cursor.fetchall()]
    except:
        return []

def mark_video_watched(user_id: int, video_id: int):
    try:
        cursor.execute("INSERT OR IGNORE INTO user_videos (user_id, video_id) VALUES (?, ?)", (user_id, video_id))
        conn.commit()
        return True
    except:
        return False

def get_watched_stats():
    try:
        cursor.execute("SELECT COUNT(DISTINCT user_id) as unique_viewers, COUNT(*) as total_views FROM user_videos")
        return dict(cursor.fetchone())
    except:
        return {"unique_viewers": 0, "total_views": 0}

# ========== ФУНКЦИИ ДЛЯ ПРОМОКОДОВ ==========
def add_promo_code(code: str, reward: int, activations: int):
    try:
        cursor.execute("INSERT INTO promocodes (code, reward, activations_left) VALUES (?, ?, ?)", (code, reward, activations))
        conn.commit()
        return True
    except:
        return False

def get_promo_code(code: str):
    try:
        cursor.execute("SELECT * FROM promocodes WHERE code = ?", (code,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None

def use_promo_code(code: str, user_id: int):
    try:
        cursor.execute("UPDATE promocodes SET activations_left = activations_left - 1 WHERE code = ?", (code,))
        cursor.execute("INSERT INTO used_promocodes (user_id, code) VALUES (?, ?)", (user_id, code))
        conn.commit()
        return True
    except:
        return False

def check_promo_used(user_id: int, code: str) -> bool:
    try:
        cursor.execute("SELECT 1 FROM used_promocodes WHERE user_id = ? AND code = ?", (user_id, code))
        return cursor.fetchone() is not None
    except:
        return False

def get_promo_stats():
    try:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_codes,
                SUM(activations_left) as total_left,
                (SELECT COUNT(*) FROM used_promocodes) as total_used
            FROM promocodes
        """)
        return dict(cursor.fetchone())
    except:
        return {"total_codes": 0, "total_left": 0, "total_used": 0}

# ========== СТАТИСТИКА ==========
def get_total_users() -> int:
    try:
        cursor.execute("SELECT COUNT(*) as count FROM users")
        row = cursor.fetchone()
        return row["count"] if row else 0
    except:
        return 0

def get_verified_users() -> int:
    try:
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_verified = 1")
        row = cursor.fetchone()
        return row["count"] if row else 0
    except:
        return 0

def get_users_with_balance() -> int:
    try:
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE balance > 0")
        row = cursor.fetchone()
        return row["count"] if row else 0
    except:
        return 0

def get_total_balance() -> int:
    try:
        cursor.execute("SELECT SUM(balance) as total FROM users")
        row = cursor.fetchone()
        return row["total"] if row and row["total"] else 0
    except:
        return 0

def get_max_balance() -> int:
    try:
        cursor.execute("SELECT MAX(balance) as max FROM users")
        row = cursor.fetchone()
        return row["max"] if row and row["max"] else 0
    except:
        return 0

def get_avg_balance() -> float:
    try:
        cursor.execute("SELECT AVG(balance) as avg FROM users")
        row = cursor.fetchone()
        return row["avg"] if row and row["avg"] else 0
    except:
        return 0

def get_referral_stats():
    try:
        cursor.execute("SELECT COUNT(*) as total_refs FROM users WHERE referrer IS NOT NULL")
        row = cursor.fetchone()
        return {"total_refs": row["total_refs"] if row else 0}
    except:
        return {"total_refs": 0}

# ========== ФУНКЦИИ ДЛЯ ЗАДАНИЙ ==========

def init_tasks_tables():
    try:
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            reward INTEGER NOT NULL,
            type TEXT DEFAULT 'text',
            content TEXT,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS completed_tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            task_id INTEGER,
            status TEXT DEFAULT 'pending',
            submission TEXT,
            submission_type TEXT,
            approved_by INTEGER,
            completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, task_id)
        )
        """)
        
        conn.commit()
        print("✅ Таблицы заданий созданы")
    except Exception as e:
        print(f"⚠️ Ошибка создания таблиц заданий: {e}")

def get_all_tasks():
    try:
        cursor.execute("SELECT * FROM tasks WHERE is_active = 1 ORDER BY id")
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []

def get_task(task_id: int):
    try:
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None

def add_task(title: str, reward: int, description: str = "", task_type: str = "text", content: str = ""):
    try:
        cursor.execute("""
            INSERT INTO tasks (title, description, reward, type, content, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
        """, (title, description, reward, task_type, content))
        conn.commit()
        return cursor.lastrowid
    except:
        return None

def delete_task(task_id: int):
    try:
        cursor.execute("UPDATE tasks SET is_active = 0 WHERE id = ?", (task_id,))
        conn.commit()
        return True
    except:
        return False

def get_user_task_status(user_id: int, task_id: int):
    try:
        cursor.execute("SELECT status, submission, completed_at, id FROM completed_tasks WHERE user_id = ? AND task_id = ?", (user_id, task_id))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None

def submit_task(user_id: int, task_id: int, submission: str, submission_type: str):
    try:
        existing = get_user_task_status(user_id, task_id)
        if existing:
            if existing["status"] == "pending":
                return False, "already_pending"
            elif existing["status"] == "approved":
                return False, "already_approved"
        
        cursor.execute("""
            INSERT OR REPLACE INTO completed_tasks (user_id, task_id, status, submission, submission_type)
            VALUES (?, ?, 'pending', ?, ?)
        """, (user_id, task_id, submission, submission_type))
        conn.commit()
        return True, "ok"
    except:
        return False, "error"

def approve_task(submission_id: int, admin_id: int):
    try:
        cursor.execute("SELECT user_id, task_id FROM completed_tasks WHERE id = ? AND status = 'pending'", (submission_id,))
        submission = cursor.fetchone()
        if not submission:
            return False, 0
        
        user_id = submission["user_id"]
        task_id = submission["task_id"]
        task = get_task(task_id)
        if not task:
            return False, 0
        
        cursor.execute("UPDATE completed_tasks SET status = 'approved', approved_by = ? WHERE id = ?", (admin_id, submission_id))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (task["reward"], user_id))
        conn.commit()
        return True, task["reward"]
    except:
        conn.rollback()
        return False, 0

def reject_task(submission_id: int, admin_id: int):
    try:
        cursor.execute("UPDATE completed_tasks SET status = 'rejected', approved_by = ? WHERE id = ? AND status = 'pending'", (admin_id, submission_id))
        conn.commit()
        return cursor.rowcount > 0
    except:
        return False

def get_user_completed_tasks(user_id: int):
    try:
        cursor.execute("""
            SELECT t.*, ct.status, ct.completed_at, ct.id as submission_id
            FROM tasks t
            LEFT JOIN completed_tasks ct ON t.id = ct.task_id AND ct.user_id = ?
            WHERE t.is_active = 1
            ORDER BY t.id
        """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []

def get_pending_submissions():
    try:
        cursor.execute("""
            SELECT ct.id, ct.user_id, ct.task_id, ct.submission, ct.submission_type, 
                   ct.completed_at, u.username, t.title, t.reward
            FROM completed_tasks ct
            JOIN users u ON ct.user_id = u.user_id
            JOIN tasks t ON ct.task_id = t.id
            WHERE ct.status = 'pending'
            ORDER BY ct.completed_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []

def get_tasks_stats():
    try:
        cursor.execute("SELECT COUNT(*) as total FROM tasks WHERE is_active = 1")
        total = cursor.fetchone()["total"]
        cursor.execute("SELECT COUNT(*) as pending FROM completed_tasks WHERE status = 'pending'")
        pending = cursor.fetchone()["pending"]
        cursor.execute("SELECT COUNT(*) as approved FROM completed_tasks WHERE status = 'approved'")
        approved = cursor.fetchone()["approved"]
        cursor.execute("SELECT COALESCE(SUM(reward), 0) as total_reward FROM completed_tasks ct JOIN tasks t ON ct.task_id = t.id WHERE ct.status = 'approved'")
        total_reward = cursor.fetchone()["total_reward"]
        return {"total": total, "pending": pending, "approved": approved, "total_reward": total_reward}
    except:
        return {"total": 0, "pending": 0, "approved": 0, "total_reward": 0}

# ========== ФУНКЦИИ ДЛЯ ПРИВАТКИ ==========

def has_private_access(user_id: int) -> bool:
    try:
        cursor.execute("SELECT 1 FROM private_access WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is not None
    except:
        return False

def grant_private_access(user_id: int):
    try:
        cursor.execute("INSERT OR REPLACE INTO private_access (user_id) VALUES (?)", (user_id,))
        conn.commit()
        return True
    except:
        return False

# ========== ИНИЦИАЛИЗАЦИЯ ==========

init_db()
init_tasks_tables()

# Создаём таблицу private_access
cursor.execute("""
CREATE TABLE IF NOT EXISTS private_access (
    user_id INTEGER PRIMARY KEY,
    purchased_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")

# Добавляем колонку is_private если её нет
try:
    cursor.execute("SELECT is_private FROM videos LIMIT 1")
except:
    try:
        cursor.execute("ALTER TABLE videos ADD COLUMN is_private INTEGER DEFAULT 0")
        print("✅ Добавлена колонка is_private")
    except:
        pass

conn.commit()
print("✅ База данных полностью готова!")
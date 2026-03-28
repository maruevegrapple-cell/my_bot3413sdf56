import sqlite3
import random
import string
import os
from datetime import datetime, timedelta
from config import SUBSCRIPTIONS

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

# ========== ФУНКЦИЯ ОБНОВЛЕНИЯ СХЕМЫ ==========
def update_db_schema():
    """Обновление схемы базы данных"""
    try:
        # Проверяем наличие колонок в таблице tasks
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'task_type' not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN task_type TEXT DEFAULT 'text'")
            print("✅ Добавлена колонка task_type")
        
        if 'task_data' not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN task_data TEXT")
            print("✅ Добавлена колонка task_data")
        
        if 'max_completions' not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN max_completions INTEGER DEFAULT 1")
            print("✅ Добавлена колонка max_completions")
        
        if 'is_active' not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN is_active INTEGER DEFAULT 1")
            print("✅ Добавлена колонка is_active")
        
        if 'created_at' not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            print("✅ Добавлена колонка created_at")
        
        # Проверяем таблицу user_tasks
        cursor.execute("PRAGMA table_info(user_tasks)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'proof' not in columns:
            cursor.execute("ALTER TABLE user_tasks ADD COLUMN proof TEXT")
            print("✅ Добавлена колонка proof в user_tasks")
        
        conn.commit()
        print("✅ Схема базы данных обновлена")
    except Exception as e:
        print(f"❌ Ошибка обновления схемы: {e}")

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
        pending_referrer_bonus INTEGER DEFAULT NULL,
        private_access INTEGER DEFAULT 0
    )
    """)
    
    # Проверяем, есть ли колонка pending_referrer_bonus
    try:
        cursor.execute("SELECT pending_referrer_bonus FROM users LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN pending_referrer_bonus INTEGER DEFAULT NULL")
            print("✅ Добавлена колонка pending_referrer_bonus")
        except:
            pass
    
    # Проверяем, есть ли колонка private_access
    try:
        cursor.execute("SELECT private_access FROM users LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN private_access INTEGER DEFAULT 0")
            print("✅ Добавлена колонка private_access")
        except:
            pass

    # Таблица для управления админами
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

    # Таблица обязательных каналов (ОП)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mandatory_channels (
        channel_id TEXT PRIMARY KEY,
        channel_name TEXT,
        channel_link TEXT
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
    
    # Проверяем, есть ли колонка paid
    try:
        cursor.execute("SELECT paid FROM payments LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE payments ADD COLUMN paid INTEGER DEFAULT 0")
            print("✅ Добавлена колонка paid в таблицу payments")
        except:
            pass
    
    # Таблица заданий
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        reward INTEGER
    )
    """)
    
    # Таблица выполненных заданий
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_tasks (
        user_id INTEGER,
        task_id INTEGER,
        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'pending',
        UNIQUE(user_id, task_id)
    )
    """)
    
    # Таблица покупок приватки
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS private_purchases (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        invoice_id TEXT,
        amount REAL,
        paid INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # ========== НОВЫЕ ТАБЛИЦЫ ==========
    
    # Таблица подписок пользователей
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_subscriptions (
        user_id INTEGER PRIMARY KEY,
        subscription_type TEXT,
        expires_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_daily_bonus TIMESTAMP
    )
    """)
    
    # Таблица рейтинга видео
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS video_ratings (
        video_id INTEGER,
        user_id INTEGER,
        rating INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (video_id, user_id)
    )
    """)
    
    # Таблица общей статистики видео
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS video_stats (
        video_id INTEGER PRIMARY KEY,
        likes INTEGER DEFAULT 0,
        dislikes INTEGER DEFAULT 0,
        rating REAL DEFAULT 0,
        total_ratings INTEGER DEFAULT 0
    )
    """)
    
    conn.commit()
    print("✅ База данных инициализирована")
    
    # Обновляем схему
    update_db_schema()

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ЗАДАНИЯМИ ==========
def get_active_tasks():
    """Получение активных заданий"""
    try:
        cursor.execute("SELECT * FROM tasks WHERE is_active = 1 ORDER BY id")
        return [dict(row) for row in cursor.fetchall()]
    except:
        try:
            cursor.execute("SELECT * FROM tasks ORDER BY id")
            return [dict(row) for row in cursor.fetchall()]
        except:
            return []

def get_task(task_id: int):
    """Получение задания по ID"""
    try:
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None

def add_task(title: str, description: str, reward: int, task_type: str = "photo", task_data: str = None, max_completions: int = 1):
    """Добавление нового задания"""
    try:
        cursor.execute("""
            INSERT INTO tasks (title, description, reward, task_type, task_data, max_completions, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, 1, datetime('now'))
        """, (title, description, reward, task_type, task_data, max_completions))
        conn.commit()
        task_id = cursor.lastrowid
        print(f"✅ Задание добавлено: ID={task_id}, title={title}")
        return task_id
    except Exception as e:
        print(f"❌ Ошибка добавления задания: {e}")
        return None

def remove_task(task_id: int):
    """Удаление задания"""
    try:
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        cursor.execute("DELETE FROM user_tasks WHERE task_id = ?", (task_id,))
        conn.commit()
        return True
    except:
        return False

def get_user_task_status(user_id: int, task_id: int):
    """Получение статуса выполнения задания пользователем"""
    try:
        cursor.execute("SELECT status, completed_at FROM user_tasks WHERE user_id = ? AND task_id = ?", (user_id, task_id))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None

def submit_task(user_id: int, task_id: int, proof: str = None):
    """Отправка задания на проверку"""
    try:
        cursor.execute("SELECT status FROM user_tasks WHERE user_id = ? AND task_id = ?", (user_id, task_id))
        existing = cursor.fetchone()
        
        if existing:
            status = existing["status"]
            
            if status == "pending":
                return False
            elif status == "approved":
                return False
            elif status == "rejected":
                cursor.execute("""
                    UPDATE user_tasks 
                    SET status = 'pending', proof = ?, completed_at = CURRENT_TIMESTAMP
                    WHERE user_id = ? AND task_id = ?
                """, (proof, user_id, task_id))
                conn.commit()
                return True
        
        cursor.execute("""
            INSERT INTO user_tasks (user_id, task_id, status, proof)
            VALUES (?, ?, 'pending', ?)
        """, (user_id, task_id, proof))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка submit_task: {e}")
        return False

def approve_task(user_id: int, task_id: int, reward: int):
    """Одобрение задания и начисление награды"""
    try:
        cursor.execute("SELECT status FROM user_tasks WHERE user_id = ? AND task_id = ?", (user_id, task_id))
        existing = cursor.fetchone()
        if existing and existing["status"] == "approved":
            return False
        
        cursor.execute("""
            UPDATE user_tasks SET status = 'approved' 
            WHERE user_id = ? AND task_id = ?
        """, (user_id, task_id))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка approve_task: {e}")
        return False

def reject_task(user_id: int, task_id: int):
    """Отклонение задания"""
    try:
        cursor.execute("""
            UPDATE user_tasks SET status = 'rejected' 
            WHERE user_id = ? AND task_id = ?
        """, (user_id, task_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка reject_task: {e}")
        return False

def get_pending_tasks():
    """Получение заданий на проверке"""
    try:
        cursor.execute("""
            SELECT ut.*, u.username, t.title, t.reward 
            FROM user_tasks ut
            JOIN users u ON ut.user_id = u.user_id
            JOIN tasks t ON ut.task_id = t.id
            WHERE ut.status = 'pending'
            ORDER BY ut.completed_at
        """)
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []

def get_user_completed_tasks(user_id: int):
    """Получение выполненных пользователем заданий"""
    try:
        cursor.execute("""
            SELECT t.*, ut.status, ut.completed_at 
            FROM user_tasks ut
            JOIN tasks t ON ut.task_id = t.id
            WHERE ut.user_id = ? AND ut.status = 'approved'
        """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []

def can_complete_task(user_id: int, task_id: int, max_completions: int) -> bool:
    """Проверка, может ли пользователь выполнить задание"""
    try:
        cursor.execute("SELECT COUNT(*) as count FROM user_tasks WHERE user_id = ? AND task_id = ? AND status = 'approved'", (user_id, task_id))
        completed = cursor.fetchone()["count"]
        return completed < max_completions
    except:
        return False

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С КАНАЛАМИ ОП ==========
def get_mandatory_channels():
    """Получение списка обязательных каналов"""
    try:
        cursor.execute("SELECT channel_id, channel_name, channel_link FROM mandatory_channels")
        channels = [dict(row) for row in cursor.fetchall()]
        return channels
    except:
        return []

def add_mandatory_channel(channel_id, channel_name, channel_link):
    """Добавление канала в ОП"""
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
    """Удаление канала из ОП"""
    try:
        cursor.execute("DELETE FROM mandatory_channels WHERE channel_id = ?", (channel_id,))
        conn.commit()
        return True
    except:
        return False

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С АДМИНАМИ ==========
def is_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь админом"""
    try:
        cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row and row["is_admin"] == 1
    except:
        return False

def is_main_admin(user_id: int) -> bool:
    """Проверка, является ли пользователь главным админом"""
    try:
        cursor.execute("SELECT is_main_admin FROM admins WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row and row["is_main_admin"] == 1
    except:
        return False

def can_manage_admins(user_id: int) -> bool:
    """Проверка, может ли админ управлять другими админами"""
    try:
        if is_main_admin(user_id):
            return True
        cursor.execute("SELECT can_add_admins FROM admins WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row and row["can_add_admins"] == 1
    except:
        return False

def get_all_admins():
    """Получение списка всех админов"""
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
    """Добавление нового админа"""
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
    """Удаление админа"""
    try:
        cursor.execute("UPDATE users SET is_admin = 0 WHERE user_id = ?", (admin_id,))
        cursor.execute("DELETE FROM admins WHERE user_id = ?", (admin_id,))
        conn.commit()
        return True
    except:
        return False

def update_admin_permissions(admin_id: int, can_add: bool):
    """Обновление прав админа"""
    try:
        cursor.execute("UPDATE admins SET can_add_admins = ? WHERE user_id = ?", (1 if can_add else 0, admin_id))
        conn.commit()
        return True
    except:
        return False

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С БОНУСАМИ ==========
def has_received_subscribe_bonus(user_id: int) -> bool:
    """Проверка, получал ли пользователь бонус за подписку"""
    try:
        cursor.execute("SELECT subscribe_bonus_received FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row and row["subscribe_bonus_received"] == 1
    except:
        return False

def mark_subscribe_bonus_received(user_id: int):
    """Отметить, что пользователь получил бонус за подписку"""
    try:
        cursor.execute("UPDATE users SET subscribe_bonus_received = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except:
        return False

def update_last_bonus(user_id: int, timestamp: int):
    """Обновление времени последнего бонуса"""
    try:
        cursor.execute("UPDATE users SET last_bonus = ? WHERE user_id = ?", (timestamp, user_id))
        conn.commit()
        return True
    except:
        return False

def get_bonus_stats():
    """Получение статистики по бонусам"""
    try:
        cursor.execute("SELECT COUNT(*) as users_took_bonus FROM users WHERE last_bonus > 0")
        row = cursor.fetchone()
        return {"users_took_bonus": row["users_took_bonus"] if row else 0}
    except:
        return {"users_took_bonus": 0}

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ ==========
def get_user(user_id: int):
    """Получение информации о пользователе"""
    try:
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None

def update_user_balance(user_id: int, amount: int):
    """Обновление баланса пользователя"""
    try:
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        return True
    except:
        return False

def get_user_by_ref_code(ref_code: str):
    """Получение пользователя по реферальному коду"""
    try:
        cursor.execute("SELECT user_id FROM users WHERE ref_code = ?", (ref_code,))
        row = cursor.fetchone()
        return row["user_id"] if row else None
    except:
        return None

def get_referrals_count(user_id: int) -> int:
    """Получение количества рефералов пользователя"""
    try:
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE referrer = ?", (user_id,))
        row = cursor.fetchone()
        return row["count"] if row else 0
    except:
        return 0

def get_top_referrers(limit: int = 10):
    """Получение топ рефереров"""
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

def get_pending_referrer_bonus(user_id: int):
    """Получение отложенного реферального бонуса"""
    try:
        cursor.execute("SELECT pending_referrer_bonus FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row["pending_referrer_bonus"] if row else None
    except:
        return None

def clear_pending_referrer_bonus(user_id: int):
    """Очистка отложенного реферального бонуса"""
    try:
        cursor.execute("UPDATE users SET pending_referrer_bonus = NULL WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except:
        return False

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ПЛАТЕЖАМИ ==========
def add_payment(invoice_id: str, user_id: int, amount: int):
    """Добавление записи о платеже"""
    try:
        cursor.execute(
            "INSERT INTO payments (invoice_id, user_id, amount) VALUES (?, ?, ?)",
            (invoice_id, user_id, amount)
        )
        conn.commit()
        return True
    except:
        return False

def mark_payment_paid(invoice_id: str):
    """Отметка платежа как оплаченного"""
    try:
        cursor.execute("UPDATE payments SET paid = 1 WHERE invoice_id = ?", (invoice_id,))
        conn.commit()
        return True
    except:
        return False

def get_payment(invoice_id: str):
    """Получение информации о платеже"""
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
    """Получение статистики по платежам"""
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
        return {
            "total_attempts": 0,
            "successful": 0,
            "pending": 0,
            "total_candies": 0
        }

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ВИДЕО ==========
def get_all_videos():
    """Получение всех видео"""
    try:
        cursor.execute("SELECT id, file_id FROM videos ORDER BY id")
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []

def get_video_count() -> int:
    """Получение количества видео"""
    try:
        cursor.execute("SELECT COUNT(*) as count FROM videos")
        row = cursor.fetchone()
        return row["count"] if row else 0
    except:
        return 0

def add_video(file_id: str):
    """Добавление видео"""
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
    """Отметка видео как просмотренного"""
    try:
        cursor.execute(
            "INSERT OR IGNORE INTO user_videos (user_id, video_id) VALUES (?, ?)",
            (user_id, video_id)
        )
        conn.commit()
        return True
    except:
        return False

def get_watched_stats():
    """Получение статистики просмотров"""
    try:
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT user_id) as unique_viewers,
                COUNT(*) as total_views
            FROM user_videos
        """)
        return dict(cursor.fetchone())
    except:
        return {"unique_viewers": 0, "total_views": 0}

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ПРОМОКОДАМИ ==========
def add_promo_code(code: str, reward: int, activations: int):
    """Добавление промокода"""
    try:
        cursor.execute(
            "INSERT INTO promocodes (code, reward, activations_left) VALUES (?, ?, ?)",
            (code, reward, activations)
        )
        conn.commit()
        return True
    except:
        return False

def get_promo_code(code: str):
    """Получение информации о промокоде"""
    try:
        cursor.execute("SELECT * FROM promocodes WHERE code = ?", (code,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None

def use_promo_code(code: str, user_id: int):
    """Использование промокода"""
    try:
        cursor.execute("UPDATE promocodes SET activations_left = activations_left - 1 WHERE code = ?", (code,))
        cursor.execute("INSERT INTO used_promocodes (user_id, code) VALUES (?, ?)", (user_id, code))
        conn.commit()
        return True
    except:
        return False

def check_promo_used(user_id: int, code: str) -> bool:
    """Проверка, использовал ли пользователь промокод"""
    try:
        cursor.execute(
            "SELECT 1 FROM used_promocodes WHERE user_id = ? AND code = ?",
            (user_id, code)
        )
        return cursor.fetchone() is not None
    except:
        return False

def get_promo_stats():
    """Получение статистики по промокодам"""
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

# ========== ФУНКЦИИ ДЛЯ ПОЛУЧЕНИЯ ОБЩЕЙ СТАТИСТИКИ ==========
def get_total_users() -> int:
    """Получение общего количества пользователей"""
    try:
        cursor.execute("SELECT COUNT(*) as count FROM users")
        row = cursor.fetchone()
        return row["count"] if row else 0
    except:
        return 0

def get_verified_users() -> int:
    """Получение количества верифицированных пользователей"""
    try:
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_verified = 1")
        row = cursor.fetchone()
        return row["count"] if row else 0
    except:
        return 0

def get_users_with_balance() -> int:
    """Получение количества пользователей с балансом > 0"""
    try:
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE balance > 0")
        row = cursor.fetchone()
        return row["count"] if row else 0
    except:
        return 0

def get_total_balance() -> int:
    """Получение общего баланса всех пользователей"""
    try:
        cursor.execute("SELECT SUM(balance) as total FROM users")
        row = cursor.fetchone()
        return row["total"] if row and row["total"] else 0
    except:
        return 0

def get_max_balance() -> int:
    """Получение максимального баланса"""
    try:
        cursor.execute("SELECT MAX(balance) as max FROM users")
        row = cursor.fetchone()
        return row["max"] if row and row["max"] else 0
    except:
        return 0

def get_avg_balance() -> float:
    """Получение среднего баланса"""
    try:
        cursor.execute("SELECT AVG(balance) as avg FROM users")
        row = cursor.fetchone()
        return row["avg"] if row and row["avg"] else 0
    except:
        return 0

def get_referral_stats():
    """Получение статистики по рефералам"""
    try:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_refs,
                COUNT(DISTINCT referrer) as unique_referrers
            FROM users 
            WHERE referrer IS NOT NULL
        """)
        return dict(cursor.fetchone())
    except:
        return {"total_refs": 0, "unique_referrers": 0}

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ПРИВАТКОЙ ==========
def add_private_purchase(user_id: int, invoice_id: str, amount: float):
    """Добавление покупки приватки"""
    try:
        cursor.execute("""
            INSERT INTO private_purchases (user_id, invoice_id, amount)
            VALUES (?, ?, ?)
        """, (user_id, invoice_id, amount))
        conn.commit()
        return True
    except:
        return False

def mark_private_paid(invoice_id: str):
    """Отметка оплаты приватки"""
    try:
        cursor.execute("UPDATE private_purchases SET paid = 1 WHERE invoice_id = ?", (invoice_id,))
        cursor.execute("""
            UPDATE users SET private_access = 1 
            WHERE user_id = (SELECT user_id FROM private_purchases WHERE invoice_id = ?)
        """, (invoice_id,))
        conn.commit()
        return True
    except:
        return False

def get_private_purchase(invoice_id: str):
    """Получение информации о покупке приватки"""
    try:
        cursor.execute("SELECT * FROM private_purchases WHERE invoice_id = ?", (invoice_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None

def has_private_access(user_id: int) -> bool:
    """Проверка наличия доступа к приватке"""
    try:
        cursor.execute("SELECT private_access FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row and row["private_access"] == 1
    except:
        return False

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ПОДПИСКАМИ ==========
def get_user_subscription(user_id: int):
    """Получение активной подписки пользователя"""
    try:
        cursor.execute("""
            SELECT subscription_type, expires_at, last_daily_bonus 
            FROM user_subscriptions 
            WHERE user_id = ? AND expires_at > datetime('now')
        """, (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None

def add_subscription(user_id: int, sub_type: str, days: int):
    """Добавление подписки пользователю"""
    try:
        cursor.execute("""
            INSERT OR REPLACE INTO user_subscriptions (user_id, subscription_type, expires_at)
            VALUES (?, ?, datetime('now', '+' || ? || ' days'))
        """, (user_id, sub_type, days))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка добавления подписки: {e}")
        return False

def remove_subscription(user_id: int):
    """Удаление подписки пользователя"""
    try:
        cursor.execute("DELETE FROM user_subscriptions WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except:
        return False

def get_all_subscribed_users():
    """Получение всех пользователей с активной подпиской"""
    try:
        cursor.execute("""
            SELECT user_id, subscription_type, expires_at 
            FROM user_subscriptions 
            WHERE expires_at > datetime('now')
        """)
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []

def check_and_give_daily_bonus(user_id: int):
    """Проверка и выдача ежедневного бонуса за подписку"""
    try:
        cursor.execute("""
            SELECT subscription_type, last_daily_bonus 
            FROM user_subscriptions 
            WHERE user_id = ? AND expires_at > datetime('now')
        """, (user_id,))
        sub = cursor.fetchone()
        
        if not sub:
            return False
        
        last_bonus = sub["last_daily_bonus"]
        today = datetime.now().date()
        
        if last_bonus:
            last_date = datetime.fromisoformat(last_bonus).date()
            if last_date == today:
                return False
        
        sub_type = sub["subscription_type"]
        from config import SUBSCRIPTIONS
        bonus_amount = SUBSCRIPTIONS.get(sub_type, {}).get("candies_daily", 0)
        
        if bonus_amount > 0:
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (bonus_amount, user_id))
            cursor.execute("UPDATE user_subscriptions SET last_daily_bonus = datetime('now') WHERE user_id = ?", (user_id,))
            conn.commit()
            return bonus_amount
        
        return False
    except Exception as e:
        print(f"❌ Ошибка check_and_give_daily_bonus: {e}")
        return False

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С РЕЙТИНГОМ ВИДЕО ==========
def rate_video(video_id: int, user_id: int, rating: int):
    """Оценка видео (1 = like, -1 = dislike)"""
    try:
        # Проверяем, есть ли уже оценка
        cursor.execute("SELECT rating FROM video_ratings WHERE video_id = ? AND user_id = ?", (video_id, user_id))
        existing = cursor.fetchone()
        
        if existing:
            old_rating = existing["rating"]
            if old_rating == rating:
                # Если нажали ту же кнопку - отменяем оценку
                cursor.execute("DELETE FROM video_ratings WHERE video_id = ? AND user_id = ?", (video_id, user_id))
                # Обновляем статистику
                if old_rating == 1:
                    cursor.execute("UPDATE video_stats SET likes = likes - 1 WHERE video_id = ?", (video_id,))
                else:
                    cursor.execute("UPDATE video_stats SET dislikes = dislikes - 1 WHERE video_id = ?", (video_id,))
            else:
                # Меняем оценку
                cursor.execute("UPDATE video_ratings SET rating = ? WHERE video_id = ? AND user_id = ?", (rating, video_id, user_id))
                if old_rating == 1:
                    cursor.execute("UPDATE video_stats SET likes = likes - 1, dislikes = dislikes + 1 WHERE video_id = ?", (video_id,))
                else:
                    cursor.execute("UPDATE video_stats SET dislikes = dislikes - 1, likes = likes + 1 WHERE video_id = ?", (video_id,))
        else:
            # Новая оценка
            cursor.execute("INSERT INTO video_ratings (video_id, user_id, rating) VALUES (?, ?, ?)", (video_id, user_id, rating))
            if rating == 1:
                cursor.execute("UPDATE video_stats SET likes = likes + 1 WHERE video_id = ?", (video_id,))
            else:
                cursor.execute("UPDATE video_stats SET dislikes = dislikes + 1 WHERE video_id = ?", (video_id,))
        
        # Обновляем общий рейтинг
        cursor.execute("""
            UPDATE video_stats 
            SET total_ratings = likes + dislikes,
                rating = CASE 
                    WHEN (likes + dislikes) > 0 THEN CAST(likes AS REAL) / (likes + dislikes) * 100
                    ELSE 0
                END
            WHERE video_id = ?
        """, (video_id,))
        
        conn.commit()
        
        # Возвращаем актуальную статистику
        cursor.execute("SELECT likes, dislikes, rating FROM video_stats WHERE video_id = ?", (video_id,))
        return dict(cursor.fetchone())
    except Exception as e:
        print(f"❌ Ошибка rate_video: {e}")
        return None

def get_video_rating(video_id: int):
    """Получение рейтинга видео"""
    try:
        cursor.execute("SELECT likes, dislikes, rating FROM video_stats WHERE video_id = ?", (video_id,))
        row = cursor.fetchone()
        return dict(row) if row else {"likes": 0, "dislikes": 0, "rating": 0}
    except:
        return {"likes": 0, "dislikes": 0, "rating": 0}

def get_user_video_rating(video_id: int, user_id: int):
    """Получение оценки пользователя для видео"""
    try:
        cursor.execute("SELECT rating FROM video_ratings WHERE video_id = ? AND user_id = ?", (video_id, user_id))
        row = cursor.fetchone()
        return row["rating"] if row else 0
    except:
        return 0

def get_videos_sorted_by_rating(user_id: int, limit: int = 1):
    """Получение видео, отсортированных по рейтингу (с учетом подписки)"""
    try:
        # Проверяем наличие подписки
        subscription = get_user_subscription(user_id)
        has_sub = subscription is not None
        
        if has_sub:
            # С подпиской - показываем по рейтингу (хорошие в начало)
            cursor.execute("""
                SELECT v.id, v.file_id, 
                       COALESCE(vs.rating, 0) as rating,
                       COALESCE(vs.likes, 0) as likes,
                       COALESCE(vs.dislikes, 0) as dislikes
                FROM videos v
                LEFT JOIN video_stats vs ON v.id = vs.video_id
                WHERE v.id NOT IN (
                    SELECT video_id FROM user_videos WHERE user_id = ?
                )
                ORDER BY COALESCE(vs.rating, 0) DESC, v.id ASC
                LIMIT ?
            """, (user_id, limit))
        else:
            # Без подписки - обычный порядок
            cursor.execute("""
                SELECT v.id, v.file_id, 
                       COALESCE(vs.rating, 0) as rating,
                       COALESCE(vs.likes, 0) as likes,
                       COALESCE(vs.dislikes, 0) as dislikes
                FROM videos v
                LEFT JOIN video_stats vs ON v.id = vs.video_id
                WHERE v.id NOT IN (
                    SELECT video_id FROM user_videos WHERE user_id = ?
                )
                ORDER BY v.id ASC
                LIMIT ?
            """, (user_id, limit))
        
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"❌ Ошибка get_videos_sorted_by_rating: {e}")
        return []

def get_video_count_for_user(user_id: int):
    """Получение количества непросмотренных видео для пользователя (с учетом подписки)"""
    try:
        subscription = get_user_subscription(user_id)
        
        if subscription and subscription["subscription_type"] == "op":
            # OP статус - безлимит
            cursor.execute("SELECT COUNT(*) as count FROM videos WHERE id NOT IN (SELECT video_id FROM user_videos WHERE user_id = ?)", (user_id,))
        else:
            # Обычные пользователи и другие подписки
            cursor.execute("SELECT COUNT(*) as count FROM videos WHERE id NOT IN (SELECT video_id FROM user_videos WHERE user_id = ?)", (user_id,))
        
        row = cursor.fetchone()
        return row["count"] if row else 0
    except:
        return 0

# Инициализация при импорте
init_db()
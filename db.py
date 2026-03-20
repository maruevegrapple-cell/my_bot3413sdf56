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
    # Таблица пользователей (с добавленной колонкой pending_referrer_bonus)
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
    
    # Проверяем, есть ли колонка pending_referrer_bonus (для старых БД)
    try:
        cursor.execute("SELECT pending_referrer_bonus FROM users LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN pending_referrer_bonus INTEGER DEFAULT NULL")
            print("✅ Добавлена колонка pending_referrer_bonus в таблицу users")
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

    # Таблица платежей с колонкой paid
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        invoice_id TEXT PRIMARY KEY,
        user_id INTEGER,
        amount INTEGER,
        paid INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Проверяем, есть ли колонка paid (для старых БД)
    try:
        cursor.execute("SELECT paid FROM payments LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE payments ADD COLUMN paid INTEGER DEFAULT 0")
            print("✅ Добавлена колонка paid в таблицу payments")
        except:
            pass
    
    conn.commit()
    print("✅ База данных инициализирована")

# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С КАНАЛАМИ ОП ==========
def get_mandatory_channels():
    """Получение списка обязательных каналов"""
    try:
        cursor.execute("SELECT channel_id, channel_name, channel_link FROM mandatory_channels")
        channels = [dict(row) for row in cursor.fetchall()]
        return channels
    except Exception as e:
        print(f"❌ Ошибка получения каналов ОП: {e}")
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
    except Exception as e:
        print(f"❌ Ошибка добавления канала ОП: {e}")
        return False

def remove_mandatory_channel(channel_id):
    """Удаление канала из ОП"""
    try:
        cursor.execute("DELETE FROM mandatory_channels WHERE channel_id = ?", (channel_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка удаления канала ОП: {e}")
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
    except Exception as e:
        print(f"❌ Ошибка добавления админа: {e}")
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
    except Exception as e:
        print(f"❌ Ошибка проверки бонуса: {e}")
        return False

def mark_subscribe_bonus_received(user_id: int):
    """Отметить, что пользователь получил бонус за подписку"""
    try:
        cursor.execute("UPDATE users SET subscribe_bonus_received = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка отметки бонуса: {e}")
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

# Инициализация при импорте
init_db()
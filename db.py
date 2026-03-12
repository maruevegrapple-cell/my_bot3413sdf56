import sqlite3
import random
import string
import os

# Определяем путь к БД (для Railway используем /data)
if os.environ.get('RAILWAY_ENVIRONMENT'):
    DB_PATH = "/data/database.db"
    # Создаем директорию если её нет
    os.makedirs('/data', exist_ok=True)
    print(f"✅ Railway mode: БД будет в {DB_PATH}")
else:
    DB_PATH = "database.db"
    print(f"✅ Local mode: БД будет в {DB_PATH}")

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

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
        # Проверяем, есть ли уже главный админ
        current_main = get_main_admin_id()
        if current_main:
            return current_main
        
        # Добавляем как главного админа
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
        is_admin INTEGER DEFAULT 0
    )
    """)

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

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        invoice_id TEXT PRIMARY KEY,
        user_id INTEGER,
        amount INTEGER
    )
    """)
    
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
        # Главный админ всегда может
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

# Инициализация при импорте
init_db()
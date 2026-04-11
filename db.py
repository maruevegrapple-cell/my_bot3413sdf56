import sqlite3
import random
import string
import os
import traceback
from datetime import datetime

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

# ========== КАТЕГОРИИ ЗАДАНИЙ ==========
TASK_CATEGORIES = {
    'easy': {'name': '🥉 ЛЕГКИЕ ЗАДАЧИ', 'emoji': '🥉', 'order': 1},
    'medium': {'name': '🥈 СРЕДНИЕ ЗАДАЧИ', 'emoji': '🥈', 'order': 2},
    'hard': {'name': '🥇 ЛУЧШИЕ ЗАДАЧИ', 'emoji': '🥇', 'order': 3}
}


def fix_user_tasks_table():
    try:
        cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='user_tasks'")
        row = cursor.fetchone()
        
        if row:
            sql = row["sql"]
            if "UNIQUE" in sql.upper():
                print("⚠️ Обнаружено UNIQUE ограничение в user_tasks, исправляем...")
                
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS user_tasks_new (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER,
                        task_id INTEGER,
                        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        status TEXT DEFAULT 'pending',
                        proof TEXT
                    )
                """)
                
                cursor.execute("SELECT user_id, task_id, completed_at, status, proof FROM user_tasks")
                rows = cursor.fetchall()
                for r in rows:
                    cursor.execute("""
                        INSERT INTO user_tasks_new (user_id, task_id, completed_at, status, proof)
                        VALUES (?, ?, ?, ?, ?)
                    """, (r["user_id"], r["task_id"], r["completed_at"], r["status"], r["proof"]))
                
                cursor.execute("DROP TABLE user_tasks")
                cursor.execute("ALTER TABLE user_tasks_new RENAME TO user_tasks")
                
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_tasks_user_task ON user_tasks(user_id, task_id)")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_user_tasks_status ON user_tasks(status)")
                
                conn.commit()
                print("✅ UNIQUE ограничение удалено!")
            else:
                print("✅ Таблица user_tasks уже без UNIQUE")
    except Exception as e:
        print(f"❌ Ошибка исправления user_tasks: {e}")


def generate_ref_code(length=6):
    chars = string.ascii_uppercase + string.digits
    chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
    while True:
        code = ''.join(random.choices(chars, k=length))
        cursor.execute("SELECT user_id FROM users WHERE ref_code = ?", (code,))
        if not cursor.fetchone():
            return code


def get_main_admin_id():
    try:
        cursor.execute("SELECT user_id FROM admins WHERE is_main_admin = 1 LIMIT 1")
        row = cursor.fetchone()
        if row:
            return row["user_id"]
    except:
        pass
    return None


def set_main_admin(user_id: int, username: str = ""):
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
    # ========== ТАБЛИЦА ПОЛЬЗОВАТЕЛЕЙ ==========
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
        private_access INTEGER DEFAULT 0,
        language TEXT DEFAULT 'ru',
        last_mirror_used TEXT DEFAULT NULL
    )
    """)
    
    # Добавляем недостающие колонки
    try:
        cursor.execute("SELECT pending_referrer_bonus FROM users LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN pending_referrer_bonus INTEGER DEFAULT NULL")
            print("✅ Добавлена колонка pending_referrer_bonus")
        except:
            pass
    
    try:
        cursor.execute("SELECT private_access FROM users LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN private_access INTEGER DEFAULT 0")
            print("✅ Добавлена колонка private_access")
        except:
            pass
    
    try:
        cursor.execute("SELECT language FROM users LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN language TEXT DEFAULT 'ru'")
            print("✅ Добавлена колонка language в таблицу users")
        except:
            pass
    
    try:
        cursor.execute("SELECT last_mirror_used FROM users LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN last_mirror_used TEXT DEFAULT NULL")
            print("✅ Добавлена колонка last_mirror_used")
        except:
            pass

    # ========== ТАБЛИЦА АДМИНОВ ==========
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

    # ========== ТАБЛИЦА КАНАЛОВ ОП ==========
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mandatory_channels (
        channel_id TEXT PRIMARY KEY,
        channel_name TEXT,
        channel_link TEXT
    )
    """)

    # ========== ТАБЛИЦА ВИДЕО ==========
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS videos (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_id TEXT UNIQUE
    )
    """)

    # ========== ТАБЛИЦА ПРОСМОТРОВ ВИДЕО ==========
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_videos (
        user_id INTEGER,
        video_id INTEGER,
        UNIQUE(user_id, video_id)
    )
    """)

    # ========== ТАБЛИЦА ПРОМОКОДОВ ==========
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS promocodes (
        code TEXT PRIMARY KEY,
        reward INTEGER,
        activations_left INTEGER
    )
    """)

    # ========== ТАБЛИЦА ИСПОЛЬЗОВАННЫХ ПРОМОКОДОВ ==========
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS used_promocodes (
        user_id INTEGER,
        code TEXT,
        UNIQUE(user_id, code)
    )
    """)

    # ========== ТАБЛИЦА ПЛАТЕЖЕЙ ==========
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS payments (
        invoice_id TEXT PRIMARY KEY,
        user_id INTEGER,
        amount INTEGER,
        paid INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        payment_method TEXT DEFAULT 'cryptobot'
    )
    """)
    
    try:
        cursor.execute("SELECT paid FROM payments LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE payments ADD COLUMN paid INTEGER DEFAULT 0")
            print("✅ Добавлена колонка paid в таблицу payments")
        except:
            pass
    
    try:
        cursor.execute("SELECT payment_method FROM payments LIMIT 1")
    except:
        try:
            cursor.execute("ALTER TABLE payments ADD COLUMN payment_method TEXT DEFAULT 'cryptobot'")
            print("✅ Добавлена колонка payment_method в таблицу payments")
        except:
            pass
    
    # ========== ТАБЛИЦА ЗАДАНИЙ ==========
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        reward INTEGER,
        task_type TEXT DEFAULT 'text',
        task_data TEXT,
        max_completions INTEGER DEFAULT 1,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        category TEXT DEFAULT 'easy'
    )
    """)
    
    # ========== ТАБЛИЦА ВЫПОЛНЕНИЙ ЗАДАНИЙ ==========
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task_id INTEGER,
        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'pending',
        proof TEXT
    )
    """)
    
    # ========== ТАБЛИЦА АВТО-ЗАДАНИЙ (ВЫДАЮТ НАГРАДУ АВТОМАТИЧЕСКИ) ==========
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS auto_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT,
        description TEXT,
        reward INTEGER,
        task_type TEXT DEFAULT 'text',
        task_data TEXT,
        max_completions INTEGER DEFAULT 1,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        category TEXT DEFAULT 'easy',
        auto_verify INTEGER DEFAULT 1
    )
    """)
    
    # ========== ТАБЛИЦА ВЫПОЛНЕНИЙ АВТО-ЗАДАНИЙ ==========
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_auto_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task_id INTEGER,
        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'pending',
        proof TEXT,
        reward_claimed INTEGER DEFAULT 0
    )
    """)
    
    # ========== ТАБЛИЦА ЗЕРКАЛ ==========
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS mirror_bots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        bot_token TEXT NOT NULL UNIQUE,
        bot_username TEXT,
        is_active INTEGER DEFAULT 1,
        added_by INTEGER,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_health_check TIMESTAMP,
        is_main INTEGER DEFAULT 0,
        notes TEXT,
        mirror_code TEXT UNIQUE
    )
    """)
    
    # ========== ТАБЛИЦА ПОКУПОК ПРИВАТКИ ==========
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
    
    # ========== ТАБЛИЦА ПОДПИСОК ==========
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_subscriptions (
        user_id INTEGER PRIMARY KEY,
        subscription_type TEXT,
        expires_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_daily_bonus TIMESTAMP
    )
    """)
    
    # ========== ТАБЛИЦА РЕЙТИНГОВ ВИДЕО ==========
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS video_ratings (
        video_id INTEGER,
        user_id INTEGER,
        rating INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (video_id, user_id)
    )
    """)
    
    # ========== ТАБЛИЦА СТАТИСТИКИ ВИДЕО ==========
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS video_stats (
        video_id INTEGER PRIMARY KEY,
        likes INTEGER DEFAULT 0,
        dislikes INTEGER DEFAULT 0,
        rating REAL DEFAULT 0,
        total_ratings INTEGER DEFAULT 0
    )
    """)
    
    # ========== ТАБЛИЦА ЗАЯВОК НА ОПЛАТУ ЗВЕЗДАМИ ==========
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS stars_payment_requests (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        pack_amount INTEGER,
        stars_amount INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        processed_at TIMESTAMP,
        message_id INTEGER
    )
    """)
    
    # ========== ТАБЛИЦА ДЛЯ LOLZ ПЛАТЕЖЕЙ (СБП) ==========
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS lolz_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        invoice_id TEXT UNIQUE,
        order_id TEXT,
        user_id INTEGER,
        amount_rub REAL,
        pack_amount INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        paid_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    """)
    
    # ========== ТАБЛИЦА БОЕВОГО ПРОПУСКА ==========
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS battlepass (
        user_id INTEGER PRIMARY KEY,
        level INTEGER DEFAULT 1,
        exp INTEGER DEFAULT 0,
        daily_exp INTEGER DEFAULT 0,
        last_daily_reset TIMESTAMP,
        claimed_rewards TEXT DEFAULT '[]',
        premium INTEGER DEFAULT 0,
        premium_purchased INTEGER DEFAULT 0,
        last_hourly_claim TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    )
    """)
    
    # ========== ТАБЛИЦА ЗАДАНИЙ БОЕВОГО ПРОПУСКА ==========
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS battlepass_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        reward_xp INTEGER DEFAULT 10,
        is_active INTEGER DEFAULT 1,
        max_completions INTEGER DEFAULT 1,
        task_type TEXT DEFAULT 'default',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # ========== ТАБЛИЦА ВЫПОЛНЕННЫХ ЗАДАНИЙ БОЕВОГО ПРОПУСКА ==========
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_battlepass_tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task_id INTEGER,
        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, task_id)
    )
    """)
    
    conn.commit()
    print("✅ База данных инициализирована")
    
    # Обновляем схему tasks
    try:
        cursor.execute("PRAGMA table_info(tasks)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'category' not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN category TEXT DEFAULT 'easy'")
            print("✅ Добавлена колонка category в таблицу tasks")
        
        if 'task_type' not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN task_type TEXT DEFAULT 'text'")
        if 'task_data' not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN task_data TEXT")
        if 'max_completions' not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN max_completions INTEGER DEFAULT 1")
        if 'is_active' not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN is_active INTEGER DEFAULT 1")
        if 'created_at' not in columns:
            cursor.execute("ALTER TABLE tasks ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
        
        conn.commit()
        print("✅ Схема обновлена")
    except Exception as e:
        print(f"❌ Ошибка обновления схемы: {e}")
    
    # Обновляем схему auto_tasks
    try:
        cursor.execute("PRAGMA table_info(auto_tasks)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'auto_verify' not in columns:
            cursor.execute("ALTER TABLE auto_tasks ADD COLUMN auto_verify INTEGER DEFAULT 1")
            print("✅ Добавлена колонка auto_verify в таблицу auto_tasks")
        
        if 'category' not in columns:
            cursor.execute("ALTER TABLE auto_tasks ADD COLUMN category TEXT DEFAULT 'easy'")
            print("✅ Добавлена колонка category в таблицу auto_tasks")
        
        conn.commit()
    except Exception as e:
        print(f"❌ Ошибка обновления схемы auto_tasks: {e}")
    
    # Обновляем схему mirror_bots
    try:
        cursor.execute("PRAGMA table_info(mirror_bots)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'is_main' not in columns:
            cursor.execute("ALTER TABLE mirror_bots ADD COLUMN is_main INTEGER DEFAULT 0")
            print("✅ Добавлена колонка is_main в таблицу mirror_bots")
        
        if 'notes' not in columns:
            cursor.execute("ALTER TABLE mirror_bots ADD COLUMN notes TEXT")
            print("✅ Добавлена колонка notes в таблицу mirror_bots")
        
        if 'mirror_code' not in columns:
            cursor.execute("ALTER TABLE mirror_bots ADD COLUMN mirror_code TEXT UNIQUE")
            print("✅ Добавлена колонка mirror_code в таблицу mirror_bots")
        
        conn.commit()
    except Exception as e:
        print(f"❌ Ошибка обновления схемы mirror_bots: {e}")
    
    fix_user_tasks_table()


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ЯЗЫКОМ ==========
def get_user_language_db(user_id: int) -> str:
    """Получить язык пользователя из БД"""
    try:
        cursor.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row["language"] if row and row["language"] else "ru"
    except:
        return "ru"


def set_user_language_db(user_id: int, language: str) -> bool:
    """Сохранить язык пользователя в БД"""
    try:
        cursor.execute("UPDATE users SET language = ? WHERE user_id = ?", (language, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка set_user_language_db: {e}")
        return False


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С БОЕВЫМ ПРОПУСКОМ ==========
def get_battlepass(user_id: int):
    """Получить данные боевого пропуска пользователя"""
    try:
        cursor.execute("SELECT * FROM battlepass WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except Exception as e:
        print(f"❌ Ошибка get_battlepass: {e}")
        return None


def update_battlepass(user_id: int, level: int = None, exp: int = None, daily_exp: int = None, 
                     claimed_rewards: str = None, premium: int = None, last_hourly_claim: str = None,
                     last_daily_reset: str = None):
    """Обновить данные боевого пропуска"""
    try:
        updates = []
        values = []
        
        if level is not None:
            updates.append("level = ?")
            values.append(level)
        if exp is not None:
            updates.append("exp = ?")
            values.append(exp)
        if daily_exp is not None:
            updates.append("daily_exp = ?")
            values.append(daily_exp)
        if claimed_rewards is not None:
            updates.append("claimed_rewards = ?")
            values.append(claimed_rewards)
        if premium is not None:
            updates.append("premium = ?")
            values.append(premium)
        if last_hourly_claim is not None:
            updates.append("last_hourly_claim = ?")
            values.append(last_hourly_claim)
        if last_daily_reset is not None:
            updates.append("last_daily_reset = ?")
            values.append(last_daily_reset)
        
        if not updates:
            return False
        
        values.append(user_id)
        query = f"UPDATE battlepass SET {', '.join(updates)} WHERE user_id = ?"
        cursor.execute(query, values)
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка update_battlepass: {e}")
        return False


def create_battlepass(user_id: int):
    """Создать новый боевой пропуск для пользователя"""
    try:
        cursor.execute("""
            INSERT INTO battlepass (user_id, level, exp, daily_exp, last_daily_reset, claimed_rewards, last_hourly_claim)
            VALUES (?, 1, 0, 0, ?, '[]', ?)
        """, (user_id, datetime.now(), datetime.now()))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка create_battlepass: {e}")
        return False


def add_battlepass_exp_db(user_id: int, exp: int):
    """Добавить опыт в боевой пропуск"""
    try:
        bp = get_battlepass(user_id)
        if not bp:
            if not create_battlepass(user_id):
                return {"status": "error", "exp_gained": 0}
            bp = get_battlepass(user_id)
        
        # Проверка дневного лимита
        daily_exp = bp["daily_exp"]
        if daily_exp + exp > 200:
            exp = 200 - daily_exp
            if exp <= 0:
                return {"status": "limit_reached", "exp_gained": 0}
        
        new_daily_exp = daily_exp + exp
        new_exp = bp["exp"] + exp
        new_level = bp["level"]
        
        # Повышение уровня
        from battlepass import BATTLEPASS_LEVELS, MAX_LEVEL
        leveled_up = False
        while new_level < MAX_LEVEL and new_exp >= BATTLEPASS_LEVELS[new_level + 1]["exp"]:
            new_level += 1
            leveled_up = True
        
        update_battlepass(user_id, exp=new_exp, level=new_level, daily_exp=new_daily_exp)
        
        return {"status": "success", "exp_gained": exp, "leveled_up": leveled_up, "new_level": new_level}
    except Exception as e:
        print(f"❌ Ошибка add_battlepass_exp_db: {e}")
        return {"status": "error", "exp_gained": 0}


def claim_hourly_exp_db(user_id: int):
    """Забрать ежечасный опыт"""
    try:
        bp = get_battlepass(user_id)
        if not bp:
            if not create_battlepass(user_id):
                return {"status": "error", "message": "Не удалось создать пропуск"}
            bp = get_battlepass(user_id)
        
        last_claim = bp.get("last_hourly_claim")
        if last_claim:
            last_time = datetime.fromisoformat(last_claim)
            now = datetime.now()
            hours_passed = (now - last_time).total_seconds() / 3600
            
            if hours_passed < 1:
                minutes_left = int(60 - (now - last_time).total_seconds() / 60)
                return {"status": "cooldown", "minutes_left": minutes_left}
        
        # Добавляем 5 XP
        result = add_battlepass_exp_db(user_id, 5)
        
        if result["status"] == "success":
            update_battlepass(user_id, last_hourly_claim=datetime.now())
            return {"status": "success", "exp_gained": 5, "leveled_up": result.get("leveled_up", False), "new_level": result.get("new_level")}
        
        return {"status": "error", "message": "Ошибка при начислении опыта"}
    except Exception as e:
        print(f"❌ Ошибка claim_hourly_exp_db: {e}")
        return {"status": "error", "message": str(e)}


def claim_battlepass_reward_db(user_id: int, level: int, is_premium: bool = False):
    """Забрать награду уровня"""
    try:
        bp = get_battlepass(user_id)
        if not bp:
            return False
        
        if bp["level"] < level:
            return False
        
        import json
        claimed = json.loads(bp["claimed_rewards"])
        
        reward_key = f"level_{level}"
        if is_premium:
            if not bp.get("premium", 0):
                return False
            reward_key = f"premium_{level}"
        
        if reward_key in claimed:
            return False
        
        from battlepass import BATTLEPASS_LEVELS
        
        if is_premium:
            reward_amount = BATTLEPASS_LEVELS[level]["premium_reward"]
        else:
            reward_amount = BATTLEPASS_LEVELS[level]["reward"]
        
        # Начисляем награду
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward_amount, user_id))
        
        claimed.append(reward_key)
        update_battlepass(user_id, claimed_rewards=json.dumps(claimed))
        conn.commit()
        
        return {"reward": reward_amount, "level": level, "is_premium": is_premium}
    except Exception as e:
        print(f"❌ Ошибка claim_battlepass_reward_db: {e}")
        return False


def activate_premium_battlepass_db(user_id: int):
    """Активировать премиум пропуск"""
    try:
        bp = get_battlepass(user_id)
        if not bp:
            if not create_battlepass(user_id):
                return False
        
        update_battlepass(user_id, premium=1, premium_purchased=1)
        return True
    except Exception as e:
        print(f"❌ Ошибка activate_premium_battlepass_db: {e}")
        return False


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ИГРАМИ ==========
def add_game_record(user_id: int, game_type: str, bet_amount: int, win_amount: int, is_win: int, result_data: str = None):
    """Добавить запись об игре в БД"""
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS casino_games (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                game_type TEXT,
                bet_amount INTEGER,
                win_amount INTEGER,
                is_win INTEGER,
                result_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            INSERT INTO casino_games (user_id, game_type, bet_amount, win_amount, is_win, result_data)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, game_type, bet_amount, win_amount, is_win, result_data))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"❌ Ошибка add_game_record: {e}")
        return None


def get_user_game_stats(user_id: int):
    """Получить статистику игр пользователя"""
    try:
        cursor.execute("""
            SELECT 
                COUNT(*) as total_games,
                SUM(CASE WHEN is_win = 1 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN is_win = 0 THEN 1 ELSE 0 END) as losses,
                SUM(bet_amount) as total_bet,
                SUM(win_amount) as total_win
            FROM casino_games 
            WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else {"total_games": 0, "wins": 0, "losses": 0, "total_bet": 0, "total_win": 0}
    except:
        return {"total_games": 0, "wins": 0, "losses": 0, "total_bet": 0, "total_win": 0}


# ========== ФУНКЦИИ ДЛЯ ЗАДАНИЙ (С КАТЕГОРИЯМИ) ==========
def get_active_tasks():
    try:
        cursor.execute("SELECT * FROM tasks WHERE is_active = 1 ORDER BY id")
        return [dict(row) for row in cursor.fetchall()]
    except:
        try:
            cursor.execute("SELECT * FROM tasks ORDER BY id")
            return [dict(row) for row in cursor.fetchall()]
        except:
            return []


def get_active_tasks_by_category(category: str = None):
    """Получить активные задания по категории"""
    try:
        if category:
            cursor.execute("SELECT * FROM tasks WHERE is_active = 1 AND category = ? ORDER BY id", (category,))
        else:
            cursor.execute("SELECT * FROM tasks WHERE is_active = 1 ORDER BY id")
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def get_all_tasks_by_category():
    """Получить все задания сгруппированные по категориям"""
    result = {}
    for cat_key in TASK_CATEGORIES.keys():
        result[cat_key] = get_active_tasks_by_category(cat_key)
    return result


def get_task(task_id: int):
    try:
        cursor.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None


def add_task(title: str, description: str, reward: int, category: str = 'easy', task_type: str = "photo", task_data: str = None, max_completions: int = 1):
    try:
        cursor.execute("""
            INSERT INTO tasks (title, description, reward, task_type, task_data, max_completions, category, is_active, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, datetime('now'))
        """, (title, description, reward, task_type, task_data, max_completions, category))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"❌ Ошибка добавления задания: {e}")
        return None


def update_task(task_id: int, title: str = None, description: str = None, reward: int = None, max_completions: int = None, category: str = None):
    try:
        updates = []
        values = []
        
        if title is not None:
            updates.append("title = ?")
            values.append(title)
        if description is not None:
            updates.append("description = ?")
            values.append(description)
        if reward is not None:
            updates.append("reward = ?")
            values.append(reward)
        if max_completions is not None:
            updates.append("max_completions = ?")
            values.append(max_completions)
        if category is not None:
            updates.append("category = ?")
            values.append(category)
        
        if not updates:
            return False
        
        values.append(task_id)
        query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, values)
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка обновления задания: {e}")
        return False


def remove_task(task_id: int):
    try:
        cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
        cursor.execute("DELETE FROM user_tasks WHERE task_id = ?", (task_id,))
        conn.commit()
        return True
    except:
        return False


def get_user_task_status(user_id: int, task_id: int):
    try:
        cursor.execute("SELECT status, completed_at FROM user_tasks WHERE user_id = ? AND task_id = ? ORDER BY id DESC LIMIT 1", (user_id, task_id))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None


def get_user_task_records(user_id: int, task_id: int):
    try:
        cursor.execute("SELECT * FROM user_tasks WHERE user_id = ? AND task_id = ? ORDER BY id DESC", (user_id, task_id))
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def delete_user_task_record(record_id: int):
    try:
        cursor.execute("DELETE FROM user_tasks WHERE id = ?", (record_id,))
        conn.commit()
        return True
    except:
        return False


def submit_task(user_id: int, task_id: int, proof: str = None):
    try:
        cursor.execute("SELECT max_completions FROM tasks WHERE id = ?", (task_id,))
        task = cursor.fetchone()
        if not task:
            return False
        
        max_completions = task["max_completions"]
        
        cursor.execute("SELECT COUNT(*) as count FROM user_tasks WHERE user_id = ? AND task_id = ? AND status = 'approved'", (user_id, task_id))
        completed = cursor.fetchone()["count"]
        
        if completed >= max_completions:
            return False
        
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
    try:
        cursor.execute("SELECT id FROM user_tasks WHERE user_id = ? AND task_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1", (user_id, task_id))
        task_record = cursor.fetchone()
        
        if not task_record:
            return False
        
        cursor.execute("UPDATE user_tasks SET status = 'approved' WHERE id = ?", (task_record["id"],))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, user_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка approve_task: {e}")
        return False


def reject_task(user_id: int, task_id: int):
    try:
        cursor.execute("SELECT id FROM user_tasks WHERE user_id = ? AND task_id = ? AND status = 'pending' ORDER BY id DESC LIMIT 1", (user_id, task_id))
        task_record = cursor.fetchone()
        
        if not task_record:
            return False
        
        cursor.execute("UPDATE user_tasks SET status = 'rejected' WHERE id = ?", (task_record["id"],))
        conn.commit()
        return True
    except:
        return False


def get_pending_tasks():
    try:
        cursor.execute("""
            SELECT ut.*, u.username, t.title, t.reward, t.max_completions
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
    try:
        cursor.execute("""
            SELECT t.*, ut.status, ut.completed_at, ut.id as record_id
            FROM user_tasks ut
            JOIN tasks t ON ut.task_id = t.id
            WHERE ut.user_id = ? AND ut.status = 'approved'
            ORDER BY ut.completed_at DESC
        """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def can_complete_task(user_id: int, task_id: int, max_completions: int) -> bool:
    try:
        cursor.execute("SELECT COUNT(*) as count FROM user_tasks WHERE user_id = ? AND task_id = ? AND status = 'approved'", (user_id, task_id))
        completed = cursor.fetchone()["count"]
        return completed < max_completions
    except:
        return False


def get_user_completed_count(user_id: int, task_id: int) -> int:
    try:
        cursor.execute("SELECT COUNT(*) as count FROM user_tasks WHERE user_id = ? AND task_id = ? AND status = 'approved'", (user_id, task_id))
        row = cursor.fetchone()
        return row["count"] if row else 0
    except:
        return 0


def get_task_record_by_id(record_id: int):
    """Получить запись по ID"""
    try:
        cursor.execute("""
            SELECT ut.*, u.username, t.title, t.reward, t.max_completions
            FROM user_tasks ut
            JOIN users u ON ut.user_id = u.user_id
            JOIN tasks t ON ut.task_id = t.id
            WHERE ut.id = ?
        """, (record_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None


def delete_task_record_by_id(record_id: int):
    """Удалить запись по ID"""
    try:
        cursor.execute("DELETE FROM user_tasks WHERE id = ?", (record_id,))
        conn.commit()
        return True
    except:
        return False


# ========== АВТО-ЗАДАНИЯ (ВЫДАЮТ НАГРАДУ АВТОМАТИЧЕСКИ) ==========
def get_auto_tasks():
    """Получить все авто-задания"""
    try:
        cursor.execute("SELECT * FROM auto_tasks WHERE is_active = 1 ORDER BY category, id")
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def get_auto_task(task_id: int):
    """Получить авто-задание по ID"""
    try:
        cursor.execute("SELECT * FROM auto_tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None


def add_auto_task(title: str, description: str, reward: int, category: str = 'easy', 
                  task_type: str = "text", task_data: str = None, 
                  max_completions: int = 1, auto_verify: bool = True):
    """Добавить авто-задание (выдаёт награду автоматически)"""
    try:
        cursor.execute("""
            INSERT INTO auto_tasks (title, description, reward, task_type, task_data, 
                                   max_completions, category, is_active, created_at, auto_verify)
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, datetime('now'), ?)
        """, (title, description, reward, task_type, task_data, max_completions, category, 1 if auto_verify else 0))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"❌ Ошибка add_auto_task: {e}")
        return None


def update_auto_task(task_id: int, **kwargs):
    """Обновить авто-задание"""
    try:
        updates = []
        values = []
        for key, value in kwargs.items():
            if value is not None:
                updates.append(f"{key} = ?")
                values.append(value)
        
        if not updates:
            return False
        
        values.append(task_id)
        query = f"UPDATE auto_tasks SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, values)
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка update_auto_task: {e}")
        return False


def remove_auto_task(task_id: int):
    """Удалить авто-задание"""
    try:
        cursor.execute("DELETE FROM auto_tasks WHERE id = ?", (task_id,))
        cursor.execute("DELETE FROM user_auto_tasks WHERE task_id = ?", (task_id,))
        conn.commit()
        return True
    except:
        return False


def get_user_auto_task_status(user_id: int, task_id: int):
    """Получить статус выполнения авто-задания"""
    try:
        cursor.execute("SELECT status, completed_at, reward_claimed FROM user_auto_tasks WHERE user_id = ? AND task_id = ? ORDER BY id DESC LIMIT 1", 
                       (user_id, task_id))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None


def get_user_auto_task_records(user_id: int, task_id: int):
    """Получить записи выполнения авто-задания"""
    try:
        cursor.execute("SELECT * FROM user_auto_tasks WHERE user_id = ? AND task_id = ? ORDER BY id DESC", 
                       (user_id, task_id))
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def submit_auto_task(user_id: int, task_id: int, proof: str = None) -> tuple:
    """Отправить авто-задание и автоматически выдать награду"""
    try:
        task = get_auto_task(task_id)
        if not task or not task.get("is_active", 0):
            return False, "Задание не найдено или неактивно"
        
        max_completions = task.get("max_completions", 1)
        
        # Проверяем, сколько раз уже выполнено
        cursor.execute("SELECT COUNT(*) as count FROM user_auto_tasks WHERE user_id = ? AND task_id = ? AND status = 'completed'", 
                       (user_id, task_id))
        completed = cursor.fetchone()["count"]
        
        if completed >= max_completions:
            return False, f"Вы уже выполнили это задание {completed} раз из {max_completions}"
        
        # Проверяем, есть ли ожидающая заявка
        cursor.execute("SELECT id FROM user_auto_tasks WHERE user_id = ? AND task_id = ? AND status = 'pending'", 
                       (user_id, task_id))
        if cursor.fetchone():
            return False, "У вас уже есть задание на проверке"
        
        # Создаём запись
        cursor.execute("""
            INSERT INTO user_auto_tasks (user_id, task_id, status, proof, completed_at, reward_claimed)
            VALUES (?, ?, 'pending', ?, datetime('now'), 0)
        """, (user_id, task_id, proof))
        
        record_id = cursor.lastrowid
        
        # Если задание авто-верифицируемое, сразу выдаём награду
        if task.get("auto_verify", 1):
            cursor.execute("UPDATE user_auto_tasks SET status = 'completed', reward_claimed = 1 WHERE id = ?", (record_id,))
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (task["reward"], user_id))
            conn.commit()
            return True, f"✅ Задание выполнено! Начислено +{task['reward']} 🍬"
        
        conn.commit()
        return True, "Задание отправлено на проверку"
        
    except Exception as e:
        print(f"❌ Ошибка submit_auto_task: {e}")
        return False, f"Ошибка: {e}"


def get_pending_auto_tasks():
    """Получить ожидающие проверки авто-задания"""
    try:
        cursor.execute("""
            SELECT ut.*, u.username, t.title, t.reward, t.max_completions, t.auto_verify
            FROM user_auto_tasks ut
            JOIN users u ON ut.user_id = u.user_id
            JOIN auto_tasks t ON ut.task_id = t.id
            WHERE ut.status = 'pending'
            ORDER BY ut.completed_at
        """)
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def approve_auto_task(record_id: int, reward: int) -> bool:
    """Одобрить авто-задание и выдать награду"""
    try:
        cursor.execute("SELECT user_id, task_id, reward_claimed FROM user_auto_tasks WHERE id = ?", (record_id,))
        record = cursor.fetchone()
        
        if not record or record["reward_claimed"]:
            return False
        
        cursor.execute("UPDATE user_auto_tasks SET status = 'completed', reward_claimed = 1 WHERE id = ?", (record_id,))
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward, record["user_id"]))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка approve_auto_task: {e}")
        return False


def reject_auto_task(record_id: int) -> bool:
    """Отклонить авто-задание"""
    try:
        cursor.execute("UPDATE user_auto_tasks SET status = 'rejected' WHERE id = ?", (record_id,))
        conn.commit()
        return True
    except:
        return False


def get_auto_tasks_by_category(category: str = None):
    """Получить авто-задания по категории"""
    try:
        if category:
            cursor.execute("SELECT * FROM auto_tasks WHERE is_active = 1 AND category = ? ORDER BY id", (category,))
        else:
            cursor.execute("SELECT * FROM auto_tasks WHERE is_active = 1 ORDER BY id")
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def get_all_auto_tasks_by_category():
    """Получить все авто-задания сгруппированные по категориям"""
    result = {}
    for cat_key in TASK_CATEGORIES.keys():
        result[cat_key] = get_auto_tasks_by_category(cat_key)
    return result


def get_auto_task_record_by_id(record_id: int):
    """Получить запись авто-задания по ID"""
    try:
        cursor.execute("""
            SELECT ut.*, u.username, t.title, t.reward, t.max_completions, t.auto_verify
            FROM user_auto_tasks ut
            JOIN users u ON ut.user_id = u.user_id
            JOIN auto_tasks t ON ut.task_id = t.id
            WHERE ut.id = ?
        """, (record_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None


def delete_auto_task_record_by_id(record_id: int):
    """Удалить запись авто-задания по ID"""
    try:
        cursor.execute("DELETE FROM user_auto_tasks WHERE id = ?", (record_id,))
        conn.commit()
        return True
    except:
        return False


# ========== ФУНКЦИИ ДЛЯ ЗАЯВОК НА ОПЛАТУ ЗВЕЗДАМИ ==========
def add_stars_payment_request_db(user_id: int, username: str, pack_amount: int, stars_amount: int, message_id: int = None):
    """Добавить заявку на оплату звездами в БД"""
    try:
        cursor.execute("""
            INSERT INTO stars_payment_requests (user_id, username, pack_amount, stars_amount, status, message_id)
            VALUES (?, ?, ?, ?, 'pending', ?)
        """, (user_id, username, pack_amount, stars_amount, message_id))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"❌ Ошибка add_stars_payment_request_db: {e}")
        return None


def get_stars_payment_request_db(request_id: int):
    """Получить заявку из БД по ID"""
    try:
        cursor.execute("SELECT * FROM stars_payment_requests WHERE id = ?", (request_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None


def get_all_stars_payment_requests_db(status: str = None):
    """Получить все заявки из БД"""
    try:
        if status:
            cursor.execute("SELECT * FROM stars_payment_requests WHERE status = ? ORDER BY created_at DESC", (status,))
        else:
            cursor.execute("SELECT * FROM stars_payment_requests ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def approve_stars_payment_db(request_id: int):
    """Одобрить заявку в БД"""
    try:
        cursor.execute("UPDATE stars_payment_requests SET status = 'approved', processed_at = datetime('now') WHERE id = ?", (request_id,))
        conn.commit()
        return True
    except:
        return False


def reject_stars_payment_db(request_id: int):
    """Отклонить заявку в БД"""
    try:
        cursor.execute("UPDATE stars_payment_requests SET status = 'rejected', processed_at = datetime('now') WHERE id = ?", (request_id,))
        conn.commit()
        return True
    except:
        return False


# ========== ФУНКЦИИ ДЛЯ LOLZ ПЛАТЕЖЕЙ (СБП) ==========
def add_lolz_payment(invoice_id: str, order_id: str, user_id: int, amount_rub: float, pack_amount: int):
    """Добавить запись о Lolz платеже"""
    try:
        cursor.execute("""
            INSERT INTO lolz_payments (invoice_id, order_id, user_id, amount_rub, pack_amount, status)
            VALUES (?, ?, ?, ?, ?, 'pending')
        """, (invoice_id, order_id, user_id, amount_rub, pack_amount))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка add_lolz_payment: {e}")
        return False


def mark_lolz_payment_paid(invoice_id: str):
    """Отметить Lolz платеж как оплаченный"""
    try:
        cursor.execute("""
            UPDATE lolz_payments 
            SET status = 'paid', paid_at = datetime('now') 
            WHERE invoice_id = ?
        """, (invoice_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка mark_lolz_payment_paid: {e}")
        return False


def get_lolz_payment(invoice_id: str):
    """Получить Lolz платеж по invoice_id"""
    try:
        cursor.execute("SELECT * FROM lolz_payments WHERE invoice_id = ?", (invoice_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None


def get_lolz_payment_by_order(order_id: str):
    """Получить Lolz платеж по order_id"""
    try:
        cursor.execute("SELECT * FROM lolz_payments WHERE order_id = ?", (order_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None


def get_pending_lolz_payments():
    """Получить все ожидающие Lolz платежи"""
    try:
        cursor.execute("SELECT * FROM lolz_payments WHERE status = 'pending' ORDER BY created_at DESC")
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С КАНАЛАМИ ОП ==========
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


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С АДМИНАМИ ==========
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


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С БОНУСАМИ ==========
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


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ ==========
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


def get_user_by_ref_code(ref_code: str):
    try:
        cursor.execute("SELECT user_id FROM users WHERE ref_code = ?", (ref_code,))
        row = cursor.fetchone()
        return row["user_id"] if row else None
    except:
        return None


def get_referrals_count(user_id: int) -> int:
    try:
        cursor.execute("SELECT COUNT(*) as count FROM users WHERE referrer = ?", (user_id,))
        row = cursor.fetchone()
        return row["count"] if row else 0
    except:
        return 0


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


def get_top_balances(limit: int = 20):
    try:
        cursor.execute("""
            SELECT user_id, username, balance 
            FROM users 
            WHERE balance > 0
            ORDER BY balance DESC 
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def get_pending_referrer_bonus(user_id: int):
    try:
        cursor.execute("SELECT pending_referrer_bonus FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row["pending_referrer_bonus"] if row else None
    except:
        return None


def clear_pending_referrer_bonus(user_id: int):
    try:
        cursor.execute("UPDATE users SET pending_referrer_bonus = NULL WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except:
        return False


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ПЛАТЕЖАМИ ==========
def add_payment(invoice_id: str, user_id: int, amount: int, payment_method: str = "cryptobot"):
    try:
        cursor.execute(
            "INSERT INTO payments (invoice_id, user_id, amount, payment_method) VALUES (?, ?, ?, ?)",
            (invoice_id, user_id, amount, payment_method)
        )
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


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ВИДЕО ==========
def get_all_videos():
    try:
        cursor.execute("SELECT id, file_id FROM videos ORDER BY id")
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
    try:
        cursor.execute("SELECT video_id FROM user_videos WHERE user_id = ?", (user_id,))
        return [row["video_id"] for row in cursor.fetchall()]
    except:
        return []


def mark_video_watched(user_id: int, video_id: int):
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
        cursor.execute(
            "SELECT 1 FROM used_promocodes WHERE user_id = ? AND code = ?",
            (user_id, code)
        )
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


# ========== ФУНКЦИИ ДЛЯ ПОЛУЧЕНИЯ ОБЩЕЙ СТАТИСТИКИ ==========
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
    try:
        cursor.execute("SELECT * FROM private_purchases WHERE invoice_id = ?", (invoice_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None


def has_private_access(user_id: int) -> bool:
    try:
        cursor.execute("SELECT private_access FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row and row["private_access"] == 1
    except:
        return False


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ПОДПИСКАМИ ==========
def get_user_subscription(user_id: int):
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


def get_user_subscriptions(user_id: int):
    try:
        cursor.execute("""
            SELECT subscription_type, expires_at, created_at 
            FROM user_subscriptions 
            WHERE user_id = ?
            ORDER BY created_at DESC
        """, (user_id,))
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def add_subscription(user_id: int, sub_type: str, days: int):
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
    try:
        cursor.execute("DELETE FROM user_subscriptions WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except:
        return False


def get_all_active_subscriptions():
    try:
        cursor.execute("""
            SELECT user_id, subscription_type, expires_at 
            FROM user_subscriptions 
            WHERE expires_at > datetime('now')
            ORDER BY expires_at
        """)
        return [dict(row) for row in cursor.fetchall()]
    except Exception as e:
        print(f"❌ Ошибка get_all_active_subscriptions: {e}")
        return []


def check_and_give_daily_bonus(user_id: int):
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
        bonus_amount = 0
        if sub_type == "base":
            bonus_amount = 70
        elif sub_type == "newbie":
            bonus_amount = 50
        elif sub_type == "op":
            bonus_amount = 0
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
    try:
        cursor.execute("SELECT id FROM videos WHERE id = ?", (video_id,))
        if not cursor.fetchone():
            return None
        
        cursor.execute("SELECT rating FROM video_ratings WHERE video_id = ? AND user_id = ?", (video_id, user_id))
        existing = cursor.fetchone()
        
        if existing:
            old_rating = existing["rating"]
            if old_rating == rating:
                cursor.execute("DELETE FROM video_ratings WHERE video_id = ? AND user_id = ?", (video_id, user_id))
                if old_rating == 1:
                    cursor.execute("UPDATE video_stats SET likes = likes - 1 WHERE video_id = ?", (video_id,))
                else:
                    cursor.execute("UPDATE video_stats SET dislikes = dislikes - 1 WHERE video_id = ?", (video_id,))
            else:
                cursor.execute("UPDATE video_ratings SET rating = ? WHERE video_id = ? AND user_id = ?", (rating, video_id, user_id))
                if old_rating == 1:
                    cursor.execute("UPDATE video_stats SET likes = likes - 1, dislikes = dislikes + 1 WHERE video_id = ?", (video_id,))
                else:
                    cursor.execute("UPDATE video_stats SET dislikes = dislikes - 1, likes = likes + 1 WHERE video_id = ?", (video_id,))
        else:
            cursor.execute("INSERT INTO video_ratings (video_id, user_id, rating) VALUES (?, ?, ?)", (video_id, user_id, rating))
            if rating == 1:
                cursor.execute("UPDATE video_stats SET likes = likes + 1 WHERE video_id = ?", (video_id,))
            else:
                cursor.execute("UPDATE video_stats SET dislikes = dislikes + 1 WHERE video_id = ?", (video_id,))
        
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
        
        cursor.execute("SELECT likes, dislikes, rating FROM video_stats WHERE video_id = ?", (video_id,))
        row = cursor.fetchone()
        return dict(row) if row else {"likes": 0, "dislikes": 0, "rating": 0}
    except Exception as e:
        print(f"❌ Ошибка rate_video: {e}")
        traceback.print_exc()
        return None


def get_video_rating(video_id: int):
    try:
        cursor.execute("SELECT likes, dislikes, rating FROM video_stats WHERE video_id = ?", (video_id,))
        row = cursor.fetchone()
        return dict(row) if row else {"likes": 0, "dislikes": 0, "rating": 0}
    except:
        return {"likes": 0, "dislikes": 0, "rating": 0}


def get_user_video_rating(video_id: int, user_id: int):
    try:
        cursor.execute("SELECT rating FROM video_ratings WHERE video_id = ? AND user_id = ?", (video_id, user_id))
        row = cursor.fetchone()
        return row["rating"] if row else 0
    except:
        return 0


def get_videos_sorted_by_rating(user_id: int, limit: int = 1):
    try:
        subscription = get_user_subscription(user_id)
        has_sub = subscription is not None
        
        if has_sub:
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
    try:
        cursor.execute("SELECT COUNT(*) as count FROM videos WHERE id NOT IN (SELECT video_id FROM user_videos WHERE user_id = ?)", (user_id,))
        row = cursor.fetchone()
        return row["count"] if row else 0
    except:
        return 0


# ========== ФУНКЦИИ ДЛЯ ЗАДАНИЙ БОЕВОГО ПРОПУСКА ==========
def get_battlepass_tasks():
    """Получить все активные задания боевого пропуска"""
    try:
        cursor.execute("SELECT * FROM battlepass_tasks WHERE is_active = 1 ORDER BY id")
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def get_battlepass_task(task_id: int):
    """Получить задание боевого пропуска по ID"""
    try:
        cursor.execute("SELECT * FROM battlepass_tasks WHERE id = ?", (task_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None


def add_battlepass_task(title: str, description: str, reward_xp: int, max_completions: int = 1, task_type: str = 'default'):
    """Добавить новое задание боевого пропуска"""
    try:
        cursor.execute("""
            INSERT INTO battlepass_tasks (title, description, reward_xp, max_completions, task_type)
            VALUES (?, ?, ?, ?, ?)
        """, (title, description, reward_xp, max_completions, task_type))
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        print(f"❌ Ошибка add_battlepass_task: {e}")
        return None


def update_battlepass_task(task_id: int, **kwargs):
    """Обновить задание боевого пропуска"""
    try:
        updates = []
        values = []
        for key, value in kwargs.items():
            if value is not None:
                updates.append(f"{key} = ?")
                values.append(value)
        
        if not updates:
            return False
        
        values.append(task_id)
        query = f"UPDATE battlepass_tasks SET {', '.join(updates)} WHERE id = ?"
        cursor.execute(query, values)
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка update_battlepass_task: {e}")
        return False


def remove_battlepass_task(task_id: int):
    """Удалить задание боевого пропуска"""
    try:
        cursor.execute("DELETE FROM battlepass_tasks WHERE id = ?", (task_id,))
        cursor.execute("DELETE FROM user_battlepass_tasks WHERE task_id = ?", (task_id,))
        conn.commit()
        return True
    except:
        return False


def get_user_battlepass_completed_count(user_id: int, task_id: int) -> int:
    """Получить количество выполнений задания пользователем"""
    try:
        cursor.execute("""
            SELECT COUNT(*) as count FROM user_battlepass_tasks 
            WHERE user_id = ? AND task_id = ?
        """, (user_id, task_id))
        row = cursor.fetchone()
        return row["count"] if row else 0
    except:
        return 0


def can_complete_battlepass_task(user_id: int, task_id: int) -> bool:
    """Проверить, может ли пользователь выполнить задание"""
    try:
        task = get_battlepass_task(task_id)
        if not task:
            return False
        
        completed = get_user_battlepass_completed_count(user_id, task_id)
        return completed < task["max_completions"]
    except:
        return False


def complete_battlepass_task(user_id: int, task_id: int) -> bool:
    """Отметить задание как выполненное и начислить XP"""
    try:
        if not can_complete_battlepass_task(user_id, task_id):
            return False
        
        task = get_battlepass_task(task_id)
        if not task:
            return False
        
        cursor.execute("""
            INSERT INTO user_battlepass_tasks (user_id, task_id)
            VALUES (?, ?)
        """, (user_id, task_id))
        
        # Начисляем опыт
        result = add_battlepass_exp_db(user_id, task["reward_xp"])
        
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка complete_battlepass_task: {e}")
        return False


def get_user_battlepass_tasks_status(user_id: int):
    """Получить статус всех заданий боевого пропуска для пользователя"""
    try:
        tasks = get_battlepass_tasks()
        for task in tasks:
            task["completed"] = get_user_battlepass_completed_count(user_id, task["id"])
            task["can_complete"] = task["completed"] < task["max_completions"]
        return tasks
    except:
        return []


def admin_get_all_battlepass_tasks():
    """Админка: получить все задания (включая неактивные)"""
    try:
        cursor.execute("SELECT * FROM battlepass_tasks ORDER BY id")
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def admin_toggle_battlepass_task(task_id: int, is_active: bool):
    """Админка: включить/выключить задание"""
    return update_battlepass_task(task_id, is_active=1 if is_active else 0)


# ========== ФУНКЦИИ ДЛЯ ЗЕРКАЛ ==========
def get_mirror_bots(include_main: bool = False):
    """Получить список зеркал"""
    try:
        if include_main:
            cursor.execute("SELECT * FROM mirror_bots ORDER BY is_main DESC, id ASC")
        else:
            cursor.execute("SELECT * FROM mirror_bots WHERE is_main = 0 ORDER BY id ASC")
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def get_active_mirror_bots_db(include_main: bool = False):
    """Получить список активных зеркал"""
    try:
        if include_main:
            cursor.execute("SELECT * FROM mirror_bots WHERE is_active = 1 ORDER BY is_main DESC, id ASC")
        else:
            cursor.execute("SELECT * FROM mirror_bots WHERE is_active = 1 AND is_main = 0 ORDER BY id ASC")
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def get_user_mirror_bots_db(user_id: int):
    """Получить зеркала пользователя"""
    try:
        cursor.execute("SELECT * FROM mirror_bots WHERE added_by = ? AND is_main = 0 ORDER BY id ASC", (user_id,))
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def add_mirror_bot_db(token: str, username: str, added_by: int, notes: str = ""):
    """Добавить зеркало в БД"""
    try:
        mirror_code = generate_ref_code(8)
        cursor.execute("""
            INSERT INTO mirror_bots (bot_token, bot_username, is_active, added_by, added_at, notes, is_main, mirror_code)
            VALUES (?, ?, 1, ?, ?, ?, 0, ?)
        """, (token, username, added_by, datetime.now(), notes, mirror_code))
        conn.commit()
        return True
    except:
        return False


def remove_mirror_bot_db(bot_id: int):
    """Удалить зеркало из БД"""
    try:
        cursor.execute("DELETE FROM mirror_bots WHERE id = ? AND is_main = 0", (bot_id,))
        conn.commit()
        return cursor.rowcount > 0
    except:
        return False


def toggle_mirror_bot_db(bot_id: int, is_active: bool):
    """Включить/выключить зеркало в БД"""
    try:
        cursor.execute("UPDATE mirror_bots SET is_active = ? WHERE id = ? AND is_main = 0", (1 if is_active else 0, bot_id))
        conn.commit()
        return cursor.rowcount > 0
    except:
        return False


def update_mirror_username_db(bot_id: int, username: str):
    """Обновить username зеркала в БД"""
    try:
        cursor.execute("UPDATE mirror_bots SET bot_username = ? WHERE id = ?", (username, bot_id))
        conn.commit()
        return True
    except:
        return False


def get_mirror_bot_by_token_db(token: str):
    """Получить зеркало по токену"""
    try:
        cursor.execute("SELECT * FROM mirror_bots WHERE bot_token = ?", (token,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None


def get_mirror_bot_by_code_db(code: str):
    """Получить зеркало по коду"""
    try:
        cursor.execute("SELECT * FROM mirror_bots WHERE mirror_code = ?", (code,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None


# ========== ЗАПУСК ИНИЦИАЛИЗАЦИИ ==========
init_db()
print("✅ db.py загружен")
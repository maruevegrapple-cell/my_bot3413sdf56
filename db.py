import asyncpg
import random
import string
import os
import json
import traceback
from datetime import datetime
from typing import Optional, List, Dict, Any

# ========== НАСТРОЙКИ ПОДКЛЮЧЕНИЯ ==========
DATABASE_URL = "postgresql://botuser:botpass123@localhost:5432/botdb"

# Пул соединений
db_pool: Optional[asyncpg.Pool] = None

# ========== КАТЕГОРИИ ЗАДАНИЙ ==========
TASK_CATEGORIES = {
    'easy': {'name': '🥉 ЛЕГКИЕ ЗАДАЧИ', 'emoji': '🥉', 'order': 1},
    'medium': {'name': '🥈 СРЕДНИЕ ЗАДАЧИ', 'emoji': '🥈', 'order': 2},
    'hard': {'name': '🥇 ЛУЧШИЕ ЗАДАЧИ', 'emoji': '🥇', 'order': 3}
}


# ========== БАЗОВЫЕ ФУНКЦИИ ==========
async def init_db_pool():
    global db_pool
    try:
        db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10, command_timeout=60)
        print("✅ PostgreSQL пул соединений создан")
        await init_tables()
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения к PostgreSQL: {e}")
        return False


async def close_db_pool():
    global db_pool
    if db_pool:
        await db_pool.close()
        print("✅ PostgreSQL пул соединений закрыт")


async def execute(query: str, *args):
    async with db_pool.acquire() as conn:
        return await conn.execute(query, *args)


async def fetch(query: str, *args):
    async with db_pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args):
    async with db_pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args):
    async with db_pool.acquire() as conn:
        return await conn.fetchval(query, *args)


# ========== ИНИЦИАЛИЗАЦИЯ ТАБЛИЦ ==========
async def init_tables():
    # ========== ТАБЛИЦА ПОЛЬЗОВАТЕЛЕЙ ==========
    await execute("""
    CREATE TABLE IF NOT EXISTS users (
        user_id BIGINT PRIMARY KEY,
        username TEXT,
        balance INTEGER DEFAULT 0,
        referrer BIGINT,
        last_bonus BIGINT DEFAULT 0,
        is_verified INTEGER DEFAULT 0,
        ref_code TEXT UNIQUE,
        subscribe_bonus_received INTEGER DEFAULT 0,
        is_admin INTEGER DEFAULT 0,
        pending_referrer_bonus BIGINT DEFAULT NULL,
        private_access INTEGER DEFAULT 0,
        language TEXT DEFAULT 'ru',
        last_mirror_used TEXT DEFAULT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Добавляем недостающие колонки
    await execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS pending_referrer_bonus BIGINT DEFAULT NULL")
    await execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS private_access INTEGER DEFAULT 0")
    await execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'ru'")
    await execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS last_mirror_used TEXT DEFAULT NULL")

    # ========== ТАБЛИЦА АДМИНОВ ==========
    await execute("""
    CREATE TABLE IF NOT EXISTS admins (
        user_id BIGINT PRIMARY KEY,
        username TEXT,
        added_by BIGINT,
        added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_main_admin INTEGER DEFAULT 0,
        can_add_admins INTEGER DEFAULT 0,
        FOREIGN KEY (added_by) REFERENCES users (user_id) ON DELETE SET NULL
    )
    """)

    # ========== ТАБЛИЦА КАНАЛОВ ОП ==========
    await execute("""
    CREATE TABLE IF NOT EXISTS mandatory_channels (
        channel_id TEXT PRIMARY KEY,
        channel_name TEXT,
        channel_link TEXT
    )
    """)

    # ========== ТАБЛИЦА ВИДЕО ==========
    await execute("""
    CREATE TABLE IF NOT EXISTS videos (
        id SERIAL PRIMARY KEY,
        file_id TEXT UNIQUE NOT NULL
    )
    """)

    # ========== ТАБЛИЦА ПРОСМОТРОВ ВИДЕО ==========
    await execute("""
    CREATE TABLE IF NOT EXISTS user_videos (
        user_id BIGINT,
        video_id INTEGER,
        watched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, video_id),
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
        FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE
    )
    """)

    # ========== ТАБЛИЦА ПРОМОКОДОВ ==========
    await execute("""
    CREATE TABLE IF NOT EXISTS promocodes (
        code TEXT PRIMARY KEY,
        reward INTEGER,
        activations_left INTEGER
    )
    """)

    # ========== ТАБЛИЦА ИСПОЛЬЗОВАННЫХ ПРОМОКОДОВ ==========
    await execute("""
    CREATE TABLE IF NOT EXISTS used_promocodes (
        user_id BIGINT,
        code TEXT,
        used_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, code),
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    )
    """)

    # ========== ТАБЛИЦА ПЛАТЕЖЕЙ ==========
    await execute("""
    CREATE TABLE IF NOT EXISTS payments (
        invoice_id TEXT PRIMARY KEY,
        user_id BIGINT,
        amount INTEGER,
        paid INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        payment_method TEXT DEFAULT 'cryptobot',
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE SET NULL
    )
    """)
    
    await execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS paid INTEGER DEFAULT 0")
    await execute("ALTER TABLE payments ADD COLUMN IF NOT EXISTS payment_method TEXT DEFAULT 'cryptobot'")

    # ========== ТАБЛИЦА ЗАДАНИЙ ==========
    await execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id SERIAL PRIMARY KEY,
        title TEXT,
        description TEXT,
        reward INTEGER,
        task_type TEXT DEFAULT 'photo',
        task_data TEXT,
        max_completions INTEGER DEFAULT 1,
        is_active INTEGER DEFAULT 1,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        category TEXT DEFAULT 'easy'
    )
    """)

    # ========== ТАБЛИЦА ВЫПОЛНЕНИЙ ЗАДАНИЙ ==========
    await execute("""
    CREATE TABLE IF NOT EXISTS user_tasks (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        task_id INTEGER,
        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'pending',
        proof TEXT,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
        FOREIGN KEY (task_id) REFERENCES tasks (id) ON DELETE CASCADE
    )
    """)

    # ========== ТАБЛИЦА АВТО-ЗАДАНИЙ ==========
    await execute("""
    CREATE TABLE IF NOT EXISTS auto_tasks (
        id SERIAL PRIMARY KEY,
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
    await execute("""
    CREATE TABLE IF NOT EXISTS user_auto_tasks (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        task_id INTEGER,
        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        status TEXT DEFAULT 'pending',
        proof TEXT,
        reward_claimed INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
        FOREIGN KEY (task_id) REFERENCES auto_tasks (id) ON DELETE CASCADE
    )
    """)

    # ========== ТАБЛИЦА ПОКУПОК ПРИВАТКИ ==========
    await execute("""
    CREATE TABLE IF NOT EXISTS private_purchases (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        invoice_id TEXT,
        amount REAL,
        paid INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE SET NULL
    )
    """)

    # ========== ТАБЛИЦА ПОДПИСОК ==========
    await execute("""
    CREATE TABLE IF NOT EXISTS user_subscriptions (
        user_id BIGINT PRIMARY KEY,
        subscription_type TEXT,
        expires_at TIMESTAMP,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_daily_bonus TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    )
    """)

    # ========== ТАБЛИЦА РЕЙТИНГОВ ВИДЕО ==========
    await execute("""
    CREATE TABLE IF NOT EXISTS video_ratings (
        video_id INTEGER,
        user_id BIGINT,
        rating INTEGER,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (video_id, user_id),
        FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    )
    """)

    # ========== ТАБЛИЦА СТАТИСТИКИ ВИДЕО ==========
    await execute("""
    CREATE TABLE IF NOT EXISTS video_stats (
        video_id INTEGER PRIMARY KEY,
        likes INTEGER DEFAULT 0,
        dislikes INTEGER DEFAULT 0,
        rating REAL DEFAULT 0,
        total_ratings INTEGER DEFAULT 0,
        FOREIGN KEY (video_id) REFERENCES videos (id) ON DELETE CASCADE
    )
    """)

    # ========== ТАБЛИЦА ЗАЯВОК НА ОПЛАТУ ЗВЕЗДАМИ ==========
    await execute("""
    CREATE TABLE IF NOT EXISTS stars_payment_requests (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        username TEXT,
        pack_amount INTEGER,
        stars_amount INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        processed_at TIMESTAMP,
        message_id INTEGER,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE SET NULL
    )
    """)

    # ========== ТАБЛИЦА ДЛЯ LOLZ ПЛАТЕЖЕЙ (СБП) ==========
    await execute("""
    CREATE TABLE IF NOT EXISTS lolz_payments (
        id SERIAL PRIMARY KEY,
        invoice_id TEXT UNIQUE,
        order_id TEXT,
        user_id BIGINT,
        amount_rub REAL,
        pack_amount INTEGER,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        paid_at TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE SET NULL
    )
    """)

    # ========== ТАБЛИЦА БОЕВОГО ПРОПУСКА ==========
    await execute("""
    CREATE TABLE IF NOT EXISTS battlepass (
        user_id BIGINT PRIMARY KEY,
        level INTEGER DEFAULT 1,
        exp INTEGER DEFAULT 0,
        daily_exp INTEGER DEFAULT 0,
        last_daily_reset TIMESTAMP,
        claimed_rewards TEXT DEFAULT '[]',
        premium INTEGER DEFAULT 0,
        premium_purchased INTEGER DEFAULT 0,
        last_hourly_claim TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    )
    """)

    # ========== ТАБЛИЦА ЗАДАНИЙ БОЕВОГО ПРОПУСКА ==========
    await execute("""
    CREATE TABLE IF NOT EXISTS battlepass_tasks (
        id SERIAL PRIMARY KEY,
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
    await execute("""
    CREATE TABLE IF NOT EXISTS user_battlepass_tasks (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        task_id INTEGER,
        completed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, task_id),
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE,
        FOREIGN KEY (task_id) REFERENCES battlepass_tasks (id) ON DELETE CASCADE
    )
    """)

    # ========== ТАБЛИЦА ИГР ==========
    await execute("""
    CREATE TABLE IF NOT EXISTS casino_games (
        id SERIAL PRIMARY KEY,
        user_id BIGINT,
        game_type TEXT,
        bet_amount INTEGER,
        win_amount INTEGER,
        is_win INTEGER,
        result_data TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
    )
    """)

    # ========== ИНДЕКСЫ ==========
    await execute("CREATE INDEX IF NOT EXISTS idx_users_ref_code ON users(ref_code)")
    await execute("CREATE INDEX IF NOT EXISTS idx_users_referrer ON users(referrer)")
    await execute("CREATE INDEX IF NOT EXISTS idx_user_tasks_status ON user_tasks(status)")
    await execute("CREATE INDEX IF NOT EXISTS idx_user_tasks_user_task ON user_tasks(user_id, task_id)")
    await execute("CREATE INDEX IF NOT EXISTS idx_payments_user_id ON payments(user_id)")
    await execute("CREATE INDEX IF NOT EXISTS idx_video_ratings_video_id ON video_ratings(video_id)")
    await execute("CREATE INDEX IF NOT EXISTS idx_user_subscriptions_expires ON user_subscriptions(expires_at)")

    print("✅ Все таблицы PostgreSQL созданы/проверены")


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ЯЗЫКОМ ==========
async def get_user_language_db(user_id: int) -> str:
    try:
        row = await fetchrow("SELECT language FROM users WHERE user_id = $1", user_id)
        return row["language"] if row and row["language"] else "ru"
    except:
        return "ru"


async def set_user_language_db(user_id: int, language: str) -> bool:
    try:
        await execute("UPDATE users SET language = $1 WHERE user_id = $2", language, user_id)
        return True
    except Exception as e:
        print(f"❌ Ошибка set_user_language_db: {e}")
        return False


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С БОЕВЫМ ПРОПУСКОМ ==========
async def get_battlepass(user_id: int):
    try:
        row = await fetchrow("SELECT * FROM battlepass WHERE user_id = $1", user_id)
        return dict(row) if row else None
    except Exception as e:
        print(f"❌ Ошибка get_battlepass: {e}")
        return None


async def update_battlepass(user_id: int, level: int = None, exp: int = None, daily_exp: int = None, 
                     claimed_rewards: str = None, premium: int = None, last_hourly_claim: str = None,
                     last_daily_reset: str = None):
    try:
        updates = []
        values = []
        
        if level is not None:
            updates.append(f"level = ${len(values) + 2}")
            values.append(level)
        if exp is not None:
            updates.append(f"exp = ${len(values) + 2}")
            values.append(exp)
        if daily_exp is not None:
            updates.append(f"daily_exp = ${len(values) + 2}")
            values.append(daily_exp)
        if claimed_rewards is not None:
            updates.append(f"claimed_rewards = ${len(values) + 2}")
            values.append(claimed_rewards)
        if premium is not None:
            updates.append(f"premium = ${len(values) + 2}")
            values.append(premium)
        if last_hourly_claim is not None:
            updates.append(f"last_hourly_claim = ${len(values) + 2}")
            values.append(last_hourly_claim)
        if last_daily_reset is not None:
            updates.append(f"last_daily_reset = ${len(values) + 2}")
            values.append(last_daily_reset)
        
        if not updates:
            return False
        
        values.append(user_id)
        query = f"UPDATE battlepass SET {', '.join(updates)} WHERE user_id = ${len(values)}"
        await execute(query, *values)
        return True
    except Exception as e:
        print(f"❌ Ошибка update_battlepass: {e}")
        return False


async def create_battlepass(user_id: int):
    try:
        await execute("""
            INSERT INTO battlepass (user_id, level, exp, daily_exp, last_daily_reset, claimed_rewards, last_hourly_claim)
            VALUES ($1, 1, 0, 0, CURRENT_TIMESTAMP, '[]', CURRENT_TIMESTAMP)
        """, user_id)
        return True
    except Exception as e:
        print(f"❌ Ошибка create_battlepass: {e}")
        return False


async def add_battlepass_exp_db(user_id: int, exp: int):
    try:
        from battlepass import BATTLEPASS_LEVELS, MAX_LEVEL
        bp = await get_battlepass(user_id)
        if not bp:
            if not await create_battlepass(user_id):
                return {"status": "error", "exp_gained": 0}
            bp = await get_battlepass(user_id)
        
        daily_exp = bp["daily_exp"]
        if daily_exp + exp > 200:
            exp = 200 - daily_exp
            if exp <= 0:
                return {"status": "limit_reached", "exp_gained": 0}
        
        new_daily_exp = daily_exp + exp
        new_exp = bp["exp"] + exp
        new_level = bp["level"]
        
        from battlepass import BATTLEPASS_LEVELS, MAX_LEVEL
        leveled_up = False
        while new_level < MAX_LEVEL and new_exp >= BATTLEPASS_LEVELS[new_level + 1]["exp"]:
            new_level += 1
            leveled_up = True
        
        await update_battlepass(user_id, exp=new_exp, level=new_level, daily_exp=new_daily_exp)
        
        return {"status": "success", "exp_gained": exp, "leveled_up": leveled_up, "new_level": new_level}
    except Exception as e:
        print(f"❌ Ошибка add_battlepass_exp_db: {e}")
        return {"status": "error", "exp_gained": 0}


async def claim_hourly_exp_db(user_id: int):
    try:
        bp = await get_battlepass(user_id)
        if not bp:
            if not await create_battlepass(user_id):
                return {"status": "error", "message": "Не удалось создать пропуск"}
            bp = await get_battlepass(user_id)
        
        last_claim = bp.get("last_hourly_claim")
        if last_claim:
            last_time = datetime.fromisoformat(last_claim)
            now = datetime.now()
            hours_passed = (now - last_time).total_seconds() / 3600
            
            if hours_passed < 1:
                minutes_left = int(60 - (now - last_time).total_seconds() / 60)
                return {"status": "cooldown", "minutes_left": minutes_left}
        
        result = await add_battlepass_exp_db(user_id, 5)
        
        if result["status"] == "success":
            await update_battlepass(user_id, last_hourly_claim=datetime.now().isoformat())
            return {"status": "success", "exp_gained": 5, "leveled_up": result.get("leveled_up", False), "new_level": result.get("new_level")}
        
        return {"status": "error", "message": "Ошибка при начислении опыта"}
    except Exception as e:
        print(f"❌ Ошибка claim_hourly_exp_db: {e}")
        return {"status": "error", "message": str(e)}


async def claim_battlepass_reward_db(user_id: int, level: int, is_premium: bool = False):
    try:
        from battlepass import BATTLEPASS_LEVELS
        bp = await get_battlepass(user_id)
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
        
        await update_user_balance(user_id, reward_amount)
        
        claimed.append(reward_key)
        await update_battlepass(user_id, claimed_rewards=json.dumps(claimed))
        
        return {"reward": reward_amount, "level": level, "is_premium": is_premium}
    except Exception as e:
        print(f"❌ Ошибка claim_battlepass_reward_db: {e}")
        return False


async def activate_premium_battlepass_db(user_id: int):
    try:
        bp = await get_battlepass(user_id)
        if not bp:
            if not await create_battlepass(user_id):
                return False
        
        await update_battlepass(user_id, premium=1, premium_purchased=1)
        return True
    except Exception as e:
        print(f"❌ Ошибка activate_premium_battlepass_db: {e}")
        return False


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ИГРАМИ ==========
async def add_game_record(user_id: int, game_type: str, bet_amount: int, win_amount: int, is_win: int, result_data: str = None):
    try:
        row = await fetchrow("""
            INSERT INTO casino_games (user_id, game_type, bet_amount, win_amount, is_win, result_data)
            VALUES ($1, $2, $3, $4, $5, $6) RETURNING id
        """, user_id, game_type, bet_amount, win_amount, is_win, result_data)
        return row["id"]
    except Exception as e:
        print(f"❌ Ошибка add_game_record: {e}")
        return None


async def get_user_game_stats(user_id: int):
    try:
        row = await fetchrow("""
            SELECT 
                COUNT(*) as total_games,
                SUM(CASE WHEN is_win = 1 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN is_win = 0 THEN 1 ELSE 0 END) as losses,
                COALESCE(SUM(bet_amount), 0) as total_bet,
                COALESCE(SUM(win_amount), 0) as total_win
            FROM casino_games 
            WHERE user_id = $1
        """, user_id)
        return dict(row) if row else {"total_games": 0, "wins": 0, "losses": 0, "total_bet": 0, "total_win": 0}
    except:
        return {"total_games": 0, "wins": 0, "losses": 0, "total_bet": 0, "total_win": 0}


# ========== ФУНКЦИИ ДЛЯ ЗАДАНИЙ (С КАТЕГОРИЯМИ) ==========
async def get_active_tasks():
    try:
        rows = await fetch("SELECT * FROM tasks WHERE is_active = 1 ORDER BY category, id")
        return [dict(row) for row in rows]
    except:
        return []


async def get_active_tasks_by_category(category: str = None):
    try:
        if category:
            rows = await fetch("SELECT * FROM tasks WHERE is_active = 1 AND category = $1 ORDER BY id", category)
        else:
            rows = await fetch("SELECT * FROM tasks WHERE is_active = 1 ORDER BY id")
        return [dict(row) for row in rows]
    except:
        return []


async def get_all_tasks_by_category():
    result = {}
    for cat_key in TASK_CATEGORIES.keys():
        result[cat_key] = await get_active_tasks_by_category(cat_key)
    return result


async def get_task(task_id: int):
    try:
        row = await fetchrow("SELECT * FROM tasks WHERE id = $1", task_id)
        return dict(row) if row else None
    except:
        return None


async def add_task(title: str, description: str, reward: int, category: str = 'easy', task_type: str = "photo", task_data: str = None, max_completions: int = 1):
    try:
        row = await fetchrow("""
            INSERT INTO tasks (title, description, reward, task_type, task_data, max_completions, category, is_active, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, $7, 1, CURRENT_TIMESTAMP) RETURNING id
        """, title, description, reward, task_type, task_data, max_completions, category)
        return row["id"]
    except Exception as e:
        print(f"❌ Ошибка добавления задания: {e}")
        return None


async def update_task(task_id: int, title: str = None, description: str = None, reward: int = None, max_completions: int = None, category: str = None):
    try:
        updates = []
        values = []
        
        if title is not None:
            updates.append(f"title = ${len(values) + 2}")
            values.append(title)
        if description is not None:
            updates.append(f"description = ${len(values) + 2}")
            values.append(description)
        if reward is not None:
            updates.append(f"reward = ${len(values) + 2}")
            values.append(reward)
        if max_completions is not None:
            updates.append(f"max_completions = ${len(values) + 2}")
            values.append(max_completions)
        if category is not None:
            updates.append(f"category = ${len(values) + 2}")
            values.append(category)
        
        if not updates:
            return False
        
        values.append(task_id)
        query = f"UPDATE tasks SET {', '.join(updates)} WHERE id = ${len(values)}"
        await execute(query, *values)
        return True
    except Exception as e:
        print(f"❌ Ошибка обновления задания: {e}")
        return False


async def remove_task(task_id: int):
    try:
        await execute("DELETE FROM tasks WHERE id = $1", task_id)
        await execute("DELETE FROM user_tasks WHERE task_id = $1", task_id)
        return True
    except:
        return False


async def get_user_task_status(user_id: int, task_id: int):
    try:
        row = await fetchrow("SELECT status, completed_at FROM user_tasks WHERE user_id = $1 AND task_id = $2 ORDER BY id DESC LIMIT 1", user_id, task_id)
        return dict(row) if row else None
    except:
        return None


async def get_user_task_records(user_id: int, task_id: int):
    try:
        rows = await fetch("SELECT * FROM user_tasks WHERE user_id = $1 AND task_id = $2 ORDER BY id DESC", user_id, task_id)
        return [dict(row) for row in rows]
    except:
        return []


async def delete_user_task_record(record_id: int):
    try:
        await execute("DELETE FROM user_tasks WHERE id = $1", record_id)
        return True
    except:
        return False


async def submit_task(user_id: int, task_id: int, proof: str = None):
    try:
        task = await get_task(task_id)
        if not task:
            return False
        
        max_completions = task["max_completions"]
        
        completed = await fetchval("SELECT COUNT(*) FROM user_tasks WHERE user_id = $1 AND task_id = $2 AND status = 'approved'", user_id, task_id) or 0
        
        if completed >= max_completions:
            return False
        
        await execute("""
            INSERT INTO user_tasks (user_id, task_id, status, proof)
            VALUES ($1, $2, 'pending', $3)
        """, user_id, task_id, proof)
        return True
    except Exception as e:
        print(f"❌ Ошибка submit_task: {e}")
        return False


async def approve_task(user_id: int, task_id: int, reward: int):
    try:
        task_record = await fetchrow("SELECT id FROM user_tasks WHERE user_id = $1 AND task_id = $2 AND status = 'pending' ORDER BY id DESC LIMIT 1", user_id, task_id)
        
        if not task_record:
            return False
        
        await execute("UPDATE user_tasks SET status = 'approved' WHERE id = $1", task_record["id"])
        await update_user_balance(user_id, reward)
        return True
    except Exception as e:
        print(f"❌ Ошибка approve_task: {e}")
        return False


async def reject_task(user_id: int, task_id: int):
    try:
        task_record = await fetchrow("SELECT id FROM user_tasks WHERE user_id = $1 AND task_id = $2 AND status = 'pending' ORDER BY id DESC LIMIT 1", user_id, task_id)
        
        if not task_record:
            return False
        
        await execute("UPDATE user_tasks SET status = 'rejected' WHERE id = $1", task_record["id"])
        return True
    except:
        return False


async def get_pending_tasks():
    try:
        rows = await fetch("""
            SELECT ut.*, u.username, t.title, t.reward, t.max_completions
            FROM user_tasks ut
            JOIN users u ON ut.user_id = u.user_id
            JOIN tasks t ON ut.task_id = t.id
            WHERE ut.status = 'pending'
            ORDER BY ut.completed_at
        """)
        return [dict(row) for row in rows]
    except:
        return []


async def get_user_completed_tasks(user_id: int):
    try:
        rows = await fetch("""
            SELECT t.*, ut.status, ut.completed_at, ut.id as record_id
            FROM user_tasks ut
            JOIN tasks t ON ut.task_id = t.id
            WHERE ut.user_id = $1 AND ut.status = 'approved'
            ORDER BY ut.completed_at DESC
        """, user_id)
        return [dict(row) for row in rows]
    except:
        return []


async def can_complete_task(user_id: int, task_id: int, max_completions: int) -> bool:
    try:
        completed = await fetchval("SELECT COUNT(*) FROM user_tasks WHERE user_id = $1 AND task_id = $2 AND status = 'approved'", user_id, task_id) or 0
        return completed < max_completions
    except:
        return False


async def get_user_completed_count(user_id: int, task_id: int) -> int:
    try:
        return await fetchval("SELECT COUNT(*) FROM user_tasks WHERE user_id = $1 AND task_id = $2 AND status = 'approved'", user_id, task_id) or 0
    except:
        return 0


async def get_task_record_by_id(record_id: int):
    try:
        row = await fetchrow("""
            SELECT ut.*, u.username, t.title, t.reward, t.max_completions
            FROM user_tasks ut
            JOIN users u ON ut.user_id = u.user_id
            JOIN tasks t ON ut.task_id = t.id
            WHERE ut.id = $1
        """, record_id)
        return dict(row) if row else None
    except:
        return None


async def delete_task_record_by_id(record_id: int):
    try:
        await execute("DELETE FROM user_tasks WHERE id = $1", record_id)
        return True
    except:
        return False


# ========== АВТО-ЗАДАНИЯ ==========
async def get_auto_tasks():
    try:
        rows = await fetch("SELECT * FROM auto_tasks WHERE is_active = 1 ORDER BY category, id")
        return [dict(row) for row in rows]
    except:
        return []


async def get_auto_task(task_id: int):
    try:
        row = await fetchrow("SELECT * FROM auto_tasks WHERE id = $1", task_id)
        return dict(row) if row else None
    except:
        return None


async def add_auto_task(title: str, description: str, reward: int, category: str = 'easy', 
                  task_type: str = "text", task_data: str = None, 
                  max_completions: int = 1, auto_verify: bool = True):
    try:
        row = await fetchrow("""
            INSERT INTO auto_tasks (title, description, reward, task_type, task_data, 
                                   max_completions, category, is_active, created_at, auto_verify)
            VALUES ($1, $2, $3, $4, $5, $6, $7, 1, CURRENT_TIMESTAMP, $8) RETURNING id
        """, title, description, reward, task_type, task_data, max_completions, category, 1 if auto_verify else 0)
        return row["id"]
    except Exception as e:
        print(f"❌ Ошибка add_auto_task: {e}")
        return None


async def update_auto_task(task_id: int, **kwargs):
    try:
        updates = []
        values = []
        for key, value in kwargs.items():
            if value is not None:
                updates.append(f"{key} = ${len(values) + 2}")
                values.append(value)
        
        if not updates:
            return False
        
        values.append(task_id)
        query = f"UPDATE auto_tasks SET {', '.join(updates)} WHERE id = ${len(values)}"
        await execute(query, *values)
        return True
    except Exception as e:
        print(f"❌ Ошибка update_auto_task: {e}")
        return False


async def remove_auto_task(task_id: int):
    try:
        await execute("DELETE FROM auto_tasks WHERE id = $1", task_id)
        await execute("DELETE FROM user_auto_tasks WHERE task_id = $1", task_id)
        return True
    except:
        return False


async def get_user_auto_task_status(user_id: int, task_id: int):
    try:
        row = await fetchrow("SELECT status, completed_at, reward_claimed FROM user_auto_tasks WHERE user_id = $1 AND task_id = $2 ORDER BY id DESC LIMIT 1", user_id, task_id)
        return dict(row) if row else None
    except:
        return None


async def get_user_auto_task_records(user_id: int, task_id: int):
    try:
        rows = await fetch("SELECT * FROM user_auto_tasks WHERE user_id = $1 AND task_id = $2 ORDER BY id DESC", user_id, task_id)
        return [dict(row) for row in rows]
    except:
        return []


async def submit_auto_task(user_id: int, task_id: int, proof: str = None) -> tuple:
    try:
        task = await get_auto_task(task_id)
        if not task or not task.get("is_active", 0):
            return False, "Задание не найдено или неактивно"
        
        max_completions = task.get("max_completions", 1)
        
        completed = await fetchval("SELECT COUNT(*) FROM user_auto_tasks WHERE user_id = $1 AND task_id = $2 AND status = 'completed'", user_id, task_id) or 0
        
        if completed >= max_completions:
            return False, f"Вы уже выполнили это задание {completed} раз из {max_completions}"
        
        pending = await fetchrow("SELECT id FROM user_auto_tasks WHERE user_id = $1 AND task_id = $2 AND status = 'pending'", user_id, task_id)
        if pending:
            return False, "У вас уже есть задание на проверке"
        
        row = await fetchrow("""
            INSERT INTO user_auto_tasks (user_id, task_id, status, proof, completed_at, reward_claimed)
            VALUES ($1, $2, 'pending', $3, CURRENT_TIMESTAMP, 0) RETURNING id
        """, user_id, task_id, proof)
        
        record_id = row["id"]
        
        if task.get("auto_verify", 1):
            await execute("UPDATE user_auto_tasks SET status = 'completed', reward_claimed = 1 WHERE id = $1", record_id)
            await update_user_balance(user_id, task["reward"])
            return True, f"✅ Задание выполнено! Начислено +{task['reward']} 🍬"
        
        return True, "Задание отправлено на проверку"
        
    except Exception as e:
        print(f"❌ Ошибка submit_auto_task: {e}")
        return False, f"Ошибка: {e}"


async def get_pending_auto_tasks():
    try:
        rows = await fetch("""
            SELECT ut.*, u.username, t.title, t.reward, t.max_completions, t.auto_verify
            FROM user_auto_tasks ut
            JOIN users u ON ut.user_id = u.user_id
            JOIN auto_tasks t ON ut.task_id = t.id
            WHERE ut.status = 'pending'
            ORDER BY ut.completed_at
        """)
        return [dict(row) for row in rows]
    except:
        return []


async def approve_auto_task(record_id: int, reward: int) -> bool:
    try:
        record = await fetchrow("SELECT user_id, reward_claimed FROM user_auto_tasks WHERE id = $1", record_id)
        if not record or record["reward_claimed"]:
            return False
        
        await execute("UPDATE user_auto_tasks SET status = 'completed', reward_claimed = 1 WHERE id = $1", record_id)
        await update_user_balance(record["user_id"], reward)
        return True
    except Exception as e:
        print(f"❌ Ошибка approve_auto_task: {e}")
        return False


async def reject_auto_task(record_id: int) -> bool:
    try:
        await execute("UPDATE user_auto_tasks SET status = 'rejected' WHERE id = $1", record_id)
        return True
    except:
        return False


async def get_auto_tasks_by_category(category: str = None):
    try:
        if category:
            rows = await fetch("SELECT * FROM auto_tasks WHERE is_active = 1 AND category = $1 ORDER BY id", category)
        else:
            rows = await fetch("SELECT * FROM auto_tasks WHERE is_active = 1 ORDER BY id")
        return [dict(row) for row in rows]
    except:
        return []


async def get_all_auto_tasks_by_category():
    result = {}
    for cat_key in TASK_CATEGORIES.keys():
        result[cat_key] = await get_auto_tasks_by_category(cat_key)
    return result


async def get_auto_task_record_by_id(record_id: int):
    try:
        row = await fetchrow("""
            SELECT ut.*, u.username, t.title, t.reward, t.max_completions, t.auto_verify
            FROM user_auto_tasks ut
            JOIN users u ON ut.user_id = u.user_id
            JOIN auto_tasks t ON ut.task_id = t.id
            WHERE ut.id = $1
        """, record_id)
        return dict(row) if row else None
    except:
        return None


async def delete_auto_task_record_by_id(record_id: int):
    try:
        await execute("DELETE FROM user_auto_tasks WHERE id = $1", record_id)
        return True
    except:
        return False


# ========== ФУНКЦИИ ДЛЯ ЗАЯВОК НА ОПЛАТУ ЗВЕЗДАМИ ==========
async def add_stars_payment_request_db(user_id: int, username: str, pack_amount: int, stars_amount: int, message_id: int = None):
    try:
        row = await fetchrow("""
            INSERT INTO stars_payment_requests (user_id, username, pack_amount, stars_amount, status, message_id)
            VALUES ($1, $2, $3, $4, 'pending', $5) RETURNING id
        """, user_id, username, pack_amount, stars_amount, message_id)
        return row["id"]
    except Exception as e:
        print(f"❌ Ошибка add_stars_payment_request_db: {e}")
        return None


async def get_stars_payment_request_db(request_id: int):
    try:
        row = await fetchrow("SELECT * FROM stars_payment_requests WHERE id = $1", request_id)
        return dict(row) if row else None
    except:
        return None


async def get_all_stars_payment_requests_db(status: str = None):
    try:
        if status:
            rows = await fetch("SELECT * FROM stars_payment_requests WHERE status = $1 ORDER BY created_at DESC", status)
        else:
            rows = await fetch("SELECT * FROM stars_payment_requests ORDER BY created_at DESC")
        return [dict(row) for row in rows]
    except:
        return []


async def approve_stars_payment_db(request_id: int):
    try:
        await execute("UPDATE stars_payment_requests SET status = 'approved', processed_at = CURRENT_TIMESTAMP WHERE id = $1", request_id)
        return True
    except:
        return False


async def reject_stars_payment_db(request_id: int):
    try:
        await execute("UPDATE stars_payment_requests SET status = 'rejected', processed_at = CURRENT_TIMESTAMP WHERE id = $1", request_id)
        return True
    except:
        return False


# ========== ФУНКЦИИ ДЛЯ LOLZ ПЛАТЕЖЕЙ (СБП) ==========
async def add_lolz_payment(invoice_id: str, order_id: str, user_id: int, amount_rub: float, pack_amount: int):
    try:
        await execute("""
            INSERT INTO lolz_payments (invoice_id, order_id, user_id, amount_rub, pack_amount, status)
            VALUES ($1, $2, $3, $4, $5, 'pending')
        """, invoice_id, order_id, user_id, amount_rub, pack_amount)
        return True
    except Exception as e:
        print(f"❌ Ошибка add_lolz_payment: {e}")
        return False


async def mark_lolz_payment_paid(invoice_id: str):
    try:
        await execute("""
            UPDATE lolz_payments 
            SET status = 'paid', paid_at = CURRENT_TIMESTAMP 
            WHERE invoice_id = $1
        """, invoice_id)
        return True
    except Exception as e:
        print(f"❌ Ошибка mark_lolz_payment_paid: {e}")
        return False


async def get_lolz_payment(invoice_id: str):
    try:
        row = await fetchrow("SELECT * FROM lolz_payments WHERE invoice_id = $1", invoice_id)
        return dict(row) if row else None
    except:
        return None


async def get_lolz_payment_by_order(order_id: str):
    try:
        row = await fetchrow("SELECT * FROM lolz_payments WHERE order_id = $1", order_id)
        return dict(row) if row else None
    except:
        return None


async def get_pending_lolz_payments():
    try:
        rows = await fetch("SELECT * FROM lolz_payments WHERE status = 'pending' ORDER BY created_at DESC")
        return [dict(row) for row in rows]
    except:
        return []


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С КАНАЛАМИ ОП ==========
async def get_mandatory_channels():
    try:
        rows = await fetch("SELECT channel_id, channel_name, channel_link FROM mandatory_channels")
        return [dict(row) for row in rows]
    except:
        return []


async def add_mandatory_channel(channel_id, channel_name, channel_link):
    try:
        await execute("INSERT INTO mandatory_channels (channel_id, channel_name, channel_link) VALUES ($1, $2, $3) ON CONFLICT (channel_id) DO UPDATE SET channel_name = EXCLUDED.channel_name, channel_link = EXCLUDED.channel_link", channel_id, channel_name, channel_link)
        return True
    except:
        return False


async def remove_mandatory_channel(channel_id):
    try:
        await execute("DELETE FROM mandatory_channels WHERE channel_id = $1", channel_id)
        return True
    except:
        return False


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С АДМИНАМИ ==========
async def is_admin(user_id: int) -> bool:
    try:
        row = await fetchrow("SELECT is_admin FROM users WHERE user_id = $1", user_id)
        return row and row["is_admin"] == 1
    except:
        return False


async def is_main_admin(user_id: int) -> bool:
    try:
        row = await fetchrow("SELECT is_main_admin FROM admins WHERE user_id = $1", user_id)
        return row and row["is_main_admin"] == 1
    except:
        return False


async def can_manage_admins(user_id: int) -> bool:
    try:
        if await is_main_admin(user_id):
            return True
        row = await fetchrow("SELECT can_add_admins FROM admins WHERE user_id = $1", user_id)
        return row and row["can_add_admins"] == 1
    except:
        return False


async def get_all_admins():
    try:
        rows = await fetch("""
            SELECT a.user_id, a.username, a.added_at, a.is_main_admin, a.can_add_admins, u.username as current_username
            FROM admins a
            LEFT JOIN users u ON a.user_id = u.user_id
            ORDER BY a.is_main_admin DESC, a.added_at
        """)
        return [dict(row) for row in rows]
    except:
        return []


async def add_admin(admin_id: int, username: str, added_by: int, can_add: bool = False):
    try:
        await execute("""
            INSERT INTO users (user_id, username, is_verified, is_admin)
            VALUES ($1, $2, 1, 1)
            ON CONFLICT (user_id) DO UPDATE SET is_admin = 1
        """, admin_id, username)
        
        await execute("""
            INSERT INTO admins (user_id, username, added_by, added_at, is_main_admin, can_add_admins)
            VALUES ($1, $2, $3, CURRENT_TIMESTAMP, 0, $4)
            ON CONFLICT (user_id) DO UPDATE SET username = EXCLUDED.username, added_by = EXCLUDED.added_by, can_add_admins = EXCLUDED.can_add_admins
        """, admin_id, username, added_by, 1 if can_add else 0)
        return True
    except:
        return False


async def remove_admin(admin_id: int):
    try:
        await execute("UPDATE users SET is_admin = 0 WHERE user_id = $1", admin_id)
        await execute("DELETE FROM admins WHERE user_id = $1", admin_id)
        return True
    except:
        return False


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С БОНУСАМИ ==========
async def has_received_subscribe_bonus(user_id: int) -> bool:
    try:
        row = await fetchrow("SELECT subscribe_bonus_received FROM users WHERE user_id = $1", user_id)
        return row and row["subscribe_bonus_received"] == 1
    except:
        return False


async def mark_subscribe_bonus_received(user_id: int):
    try:
        await execute("UPDATE users SET subscribe_bonus_received = 1 WHERE user_id = $1", user_id)
        return True
    except:
        return False


async def update_last_bonus(user_id: int, timestamp: int):
    try:
        await execute("UPDATE users SET last_bonus = $1 WHERE user_id = $2", timestamp, user_id)
        return True
    except:
        return False


async def get_bonus_stats():
    try:
        count = await fetchval("SELECT COUNT(*) FROM users WHERE last_bonus > 0") or 0
        return {"users_took_bonus": count}
    except:
        return {"users_took_bonus": 0}


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ПОЛЬЗОВАТЕЛЯМИ ==========
async def get_user(user_id: int):
    try:
        row = await fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)
        return dict(row) if row else None
    except:
        return None


async def update_user_balance(user_id: int, amount: int):
    try:
        await execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", amount, user_id)
        return True
    except:
        return False


async def get_user_by_ref_code(ref_code: str):
    try:
        row = await fetchrow("SELECT user_id FROM users WHERE ref_code = $1", ref_code)
        return row["user_id"] if row else None
    except:
        return None


async def get_referrals_count(user_id: int) -> int:
    try:
        return await fetchval("SELECT COUNT(*) FROM users WHERE referrer = $1", user_id) or 0
    except:
        return 0


async def get_top_referrers(limit: int = 10):
    try:
        rows = await fetch("""
            SELECT u.user_id, u.username, u.balance, COUNT(r.user_id) as referrals_count
            FROM users u
            LEFT JOIN users r ON r.referrer = u.user_id
            GROUP BY u.user_id
            HAVING COUNT(r.user_id) > 0
            ORDER BY COUNT(r.user_id) DESC
            LIMIT $1
        """, limit)
        return [dict(row) for row in rows]
    except:
        return []


async def get_top_balances(limit: int = 20):
    try:
        rows = await fetch("""
            SELECT user_id, username, balance 
            FROM users 
            WHERE balance > 0
            ORDER BY balance DESC 
            LIMIT $1
        """, limit)
        return [dict(row) for row in rows]
    except:
        return []


async def get_pending_referrer_bonus(user_id: int):
    try:
        row = await fetchrow("SELECT pending_referrer_bonus FROM users WHERE user_id = $1", user_id)
        return row["pending_referrer_bonus"] if row else None
    except:
        return None


async def clear_pending_referrer_bonus(user_id: int):
    try:
        await execute("UPDATE users SET pending_referrer_bonus = NULL WHERE user_id = $1", user_id)
        return True
    except:
        return False


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ПЛАТЕЖАМИ ==========
async def add_payment(invoice_id: str, user_id: int, amount: int, payment_method: str = "cryptobot"):
    try:
        await execute("INSERT INTO payments (invoice_id, user_id, amount, payment_method) VALUES ($1, $2, $3, $4)", invoice_id, user_id, amount, payment_method)
        return True
    except:
        return False


async def mark_payment_paid(invoice_id: str):
    try:
        await execute("UPDATE payments SET paid = 1 WHERE invoice_id = $1", invoice_id)
        return True
    except:
        return False


async def get_payment(invoice_id: str):
    try:
        row = await fetchrow("SELECT * FROM payments WHERE invoice_id = $1", invoice_id)
        return dict(row) if row else None
    except:
        return None


async def get_user_payments(user_id: int, limit: int = 10):
    try:
        rows = await fetch("SELECT * FROM payments WHERE user_id = $1 ORDER BY created_at DESC LIMIT $2", user_id, limit)
        return [dict(row) for row in rows]
    except:
        return []


async def get_payments_stats():
    try:
        row = await fetchrow("""
            SELECT 
                COUNT(*) as total_attempts,
                SUM(CASE WHEN paid = 1 THEN 1 ELSE 0 END) as successful,
                SUM(CASE WHEN paid = 0 THEN 1 ELSE 0 END) as pending,
                COALESCE(SUM(CASE WHEN paid = 1 THEN amount ELSE 0 END), 0) as total_candies
            FROM payments
        """)
        if row:
            return {
                "total_attempts": row["total_attempts"] or 0,
                "successful": row["successful"] or 0,
                "pending": row["pending"] or 0,
                "total_candies": row["total_candies"] or 0
            }
        return {"total_attempts": 0, "successful": 0, "pending": 0, "total_candies": 0}
    except Exception as e:
        print(f"❌ Ошибка get_payments_stats: {e}")
        return {"total_attempts": 0, "successful": 0, "pending": 0, "total_candies": 0}


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ВИДЕО ==========
async def get_all_videos():
    try:
        rows = await fetch("SELECT id, file_id FROM videos ORDER BY id")
        return [dict(row) for row in rows]
    except:
        return []


async def get_video_count() -> int:
    try:
        return await fetchval("SELECT COUNT(*) FROM videos") or 0
    except:
        return 0


async def add_video(file_id: str):
    try:
        await execute("INSERT INTO videos (file_id) VALUES ($1)", file_id)
        row = await fetchrow("SELECT id FROM videos WHERE file_id = $1", file_id)
        if row:
            await execute("INSERT INTO video_stats (video_id) VALUES ($1)", row["id"])
        return True
    except:
        return False


async def get_user_watched_videos(user_id: int):
    try:
        rows = await fetch("SELECT video_id FROM user_videos WHERE user_id = $1", user_id)
        return [row["video_id"] for row in rows]
    except:
        return []


async def mark_video_watched(user_id: int, video_id: int):
    try:
        await execute("INSERT INTO user_videos (user_id, video_id) VALUES ($1, $2) ON CONFLICT DO NOTHING", user_id, video_id)
        return True
    except:
        return False


async def get_watched_stats():
    try:
        row = await fetchrow("SELECT COUNT(DISTINCT user_id) as unique_viewers, COUNT(*) as total_views FROM user_videos")
        if row:
            return {"unique_viewers": row["unique_viewers"] or 0, "total_views": row["total_views"] or 0}
        return {"unique_viewers": 0, "total_views": 0}
    except:
        return {"unique_viewers": 0, "total_views": 0}


async def get_video_count_for_user(user_id: int):
    try:
        return await fetchval("SELECT COUNT(*) FROM videos WHERE id NOT IN (SELECT video_id FROM user_videos WHERE user_id = $1)", user_id) or 0
    except:
        return 0


async def get_videos_sorted_by_rating(user_id: int, limit: int = 1):
    try:
        subscription = await get_user_subscription(user_id)
        has_sub = subscription is not None
        
        if has_sub:
            rows = await fetch("""
                SELECT v.id, v.file_id, 
                       COALESCE(vs.rating, 0) as rating,
                       COALESCE(vs.likes, 0) as likes,
                       COALESCE(vs.dislikes, 0) as dislikes
                FROM videos v
                LEFT JOIN video_stats vs ON v.id = vs.video_id
                WHERE v.id NOT IN (
                    SELECT video_id FROM user_videos WHERE user_id = $1
                )
                ORDER BY COALESCE(vs.rating, 0) DESC, v.id ASC
                LIMIT $2
            """, user_id, limit)
        else:
            rows = await fetch("""
                SELECT v.id, v.file_id, 
                       COALESCE(vs.rating, 0) as rating,
                       COALESCE(vs.likes, 0) as likes,
                       COALESCE(vs.dislikes, 0) as dislikes
                FROM videos v
                LEFT JOIN video_stats vs ON v.id = vs.video_id
                WHERE v.id NOT IN (
                    SELECT video_id FROM user_videos WHERE user_id = $1
                )
                ORDER BY v.id ASC
                LIMIT $2
            """, user_id, limit)
        
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"❌ Ошибка get_videos_sorted_by_rating: {e}")
        return []


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ПРОМОКОДАМИ ==========
async def add_promo_code(code: str, reward: int, activations: int):
    try:
        await execute("INSERT INTO promocodes (code, reward, activations_left) VALUES ($1, $2, $3)", code, reward, activations)
        return True
    except:
        return False


async def get_promo_code(code: str):
    try:
        row = await fetchrow("SELECT * FROM promocodes WHERE code = $1", code)
        return dict(row) if row else None
    except:
        return None


async def use_promo_code(code: str, user_id: int):
    try:
        await execute("UPDATE promocodes SET activations_left = activations_left - 1 WHERE code = $1", code)
        await execute("INSERT INTO used_promocodes (user_id, code) VALUES ($1, $2)", user_id, code)
        return True
    except:
        return False


async def check_promo_used(user_id: int, code: str) -> bool:
    try:
        row = await fetchrow("SELECT 1 FROM used_promocodes WHERE user_id = $1 AND code = $2", user_id, code)
        return row is not None
    except:
        return False


async def get_promo_stats():
    try:
        row = await fetchrow("""
            SELECT 
                COUNT(*) as total_codes,
                COALESCE(SUM(activations_left), 0) as total_left,
                (SELECT COUNT(*) FROM used_promocodes) as total_used
            FROM promocodes
        """)
        if row:
            return {
                "total_codes": row["total_codes"] or 0,
                "total_left": row["total_left"] or 0,
                "total_used": row["total_used"] or 0
            }
        return {"total_codes": 0, "total_left": 0, "total_used": 0}
    except:
        return {"total_codes": 0, "total_left": 0, "total_used": 0}


# ========== ФУНКЦИИ ДЛЯ ПОЛУЧЕНИЯ ОБЩЕЙ СТАТИСТИКИ ==========
async def get_total_users() -> int:
    try:
        return await fetchval("SELECT COUNT(*) FROM users") or 0
    except:
        return 0


async def get_verified_users() -> int:
    try:
        return await fetchval("SELECT COUNT(*) FROM users WHERE is_verified = 1") or 0
    except:
        return 0


async def get_users_with_balance() -> int:
    try:
        return await fetchval("SELECT COUNT(*) FROM users WHERE balance > 0") or 0
    except:
        return 0


async def get_total_balance() -> int:
    try:
        return await fetchval("SELECT COALESCE(SUM(balance), 0) FROM users") or 0
    except:
        return 0


async def get_max_balance() -> int:
    try:
        return await fetchval("SELECT COALESCE(MAX(balance), 0) FROM users") or 0
    except:
        return 0


async def get_avg_balance() -> float:
    try:
        return await fetchval("SELECT COALESCE(AVG(balance), 0) FROM users") or 0.0
    except:
        return 0.0


async def get_referral_stats():
    try:
        row = await fetchrow("SELECT COUNT(*) as total_refs, COUNT(DISTINCT referrer) as unique_referrers FROM users WHERE referrer IS NOT NULL")
        if row:
            return {"total_refs": row["total_refs"] or 0, "unique_referrers": row["unique_referrers"] or 0}
        return {"total_refs": 0, "unique_referrers": 0}
    except:
        return {"total_refs": 0, "unique_referrers": 0}


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ПРИВАТКОЙ ==========
async def add_private_purchase(user_id: int, invoice_id: str, amount: float):
    try:
        await execute("""
            INSERT INTO private_purchases (user_id, invoice_id, amount)
            VALUES ($1, $2, $3)
        """, user_id, invoice_id, amount)
        return True
    except:
        return False


async def mark_private_paid(invoice_id: str):
    try:
        await execute("UPDATE private_purchases SET paid = 1 WHERE invoice_id = $1", invoice_id)
        await execute("""
            UPDATE users SET private_access = 1 
            WHERE user_id = (SELECT user_id FROM private_purchases WHERE invoice_id = $1)
        """, invoice_id)
        return True
    except:
        return False


async def get_private_purchase(invoice_id: str):
    try:
        row = await fetchrow("SELECT * FROM private_purchases WHERE invoice_id = $1", invoice_id)
        return dict(row) if row else None
    except:
        return None


async def has_private_access(user_id: int) -> bool:
    try:
        row = await fetchrow("SELECT private_access FROM users WHERE user_id = $1", user_id)
        return row and row["private_access"] == 1
    except:
        return False


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С ПОДПИСКАМИ ==========
async def get_user_subscription(user_id: int):
    try:
        row = await fetchrow("""
            SELECT subscription_type, expires_at, last_daily_bonus 
            FROM user_subscriptions 
            WHERE user_id = $1 AND expires_at > CURRENT_TIMESTAMP
        """, user_id)
        return dict(row) if row else None
    except:
        return None


async def get_user_subscriptions(user_id: int):
    try:
        rows = await fetch("""
            SELECT subscription_type, expires_at, created_at 
            FROM user_subscriptions 
            WHERE user_id = $1
            ORDER BY created_at DESC
        """, user_id)
        return [dict(row) for row in rows]
    except:
        return []


async def add_subscription(user_id: int, sub_type: str, days: int):
    try:
        await execute("""
            INSERT INTO user_subscriptions (user_id, subscription_type, expires_at)
            VALUES ($1, $2, CURRENT_TIMESTAMP + ($3 || ' days')::INTERVAL)
            ON CONFLICT (user_id) DO UPDATE SET subscription_type = EXCLUDED.subscription_type, expires_at = EXCLUDED.expires_at
        """, user_id, sub_type, days)
        return True
    except Exception as e:
        print(f"❌ Ошибка добавления подписки: {e}")
        return False


async def remove_subscription(user_id: int):
    try:
        await execute("DELETE FROM user_subscriptions WHERE user_id = $1", user_id)
        return True
    except:
        return False


async def get_all_active_subscriptions():
    try:
        rows = await fetch("""
            SELECT user_id, subscription_type, expires_at 
            FROM user_subscriptions 
            WHERE expires_at > CURRENT_TIMESTAMP
            ORDER BY expires_at
        """)
        return [dict(row) for row in rows]
    except Exception as e:
        print(f"❌ Ошибка get_all_active_subscriptions: {e}")
        return []


async def check_and_give_daily_bonus(user_id: int):
    try:
        sub = await fetchrow("""
            SELECT subscription_type, last_daily_bonus 
            FROM user_subscriptions 
            WHERE user_id = $1 AND expires_at > CURRENT_TIMESTAMP
        """, user_id)
        if not sub:
            return False
        last_bonus = sub["last_daily_bonus"]
        today = datetime.now().date()
        if last_bonus:
            last_date = last_bonus.date()
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
            await update_user_balance(user_id, bonus_amount)
            await execute("UPDATE user_subscriptions SET last_daily_bonus = CURRENT_TIMESTAMP WHERE user_id = $1", user_id)
            return bonus_amount
        return False
    except Exception as e:
        print(f"❌ Ошибка check_and_give_daily_bonus: {e}")
        return False


# ========== ФУНКЦИИ ДЛЯ РАБОТЫ С РЕЙТИНГОМ ВИДЕО ==========
async def rate_video(video_id: int, user_id: int, rating: int):
    try:
        row = await fetchrow("SELECT id FROM videos WHERE id = $1", video_id)
        if not row:
            return None
        
        existing = await fetchrow("SELECT rating FROM video_ratings WHERE video_id = $1 AND user_id = $2", video_id, user_id)
        
        if existing:
            old_rating = existing["rating"]
            if old_rating == rating:
                await execute("DELETE FROM video_ratings WHERE video_id = $1 AND user_id = $2", video_id, user_id)
                if old_rating == 1:
                    await execute("UPDATE video_stats SET likes = likes - 1 WHERE video_id = $1", video_id)
                else:
                    await execute("UPDATE video_stats SET dislikes = dislikes - 1 WHERE video_id = $1", video_id)
            else:
                await execute("UPDATE video_ratings SET rating = $1 WHERE video_id = $2 AND user_id = $3", rating, video_id, user_id)
                if old_rating == 1:
                    await execute("UPDATE video_stats SET likes = likes - 1, dislikes = dislikes + 1 WHERE video_id = $1", video_id)
                else:
                    await execute("UPDATE video_stats SET dislikes = dislikes - 1, likes = likes + 1 WHERE video_id = $1", video_id)
        else:
            await execute("INSERT INTO video_ratings (video_id, user_id, rating) VALUES ($1, $2, $3)", video_id, user_id, rating)
            if rating == 1:
                await execute("UPDATE video_stats SET likes = likes + 1 WHERE video_id = $1", video_id)
            else:
                await execute("UPDATE video_stats SET dislikes = dislikes + 1 WHERE video_id = $1", video_id)
        
        await execute("""
            UPDATE video_stats 
            SET total_ratings = likes + dislikes,
                rating = CASE 
                    WHEN (likes + dislikes) > 0 THEN (likes::REAL / (likes + dislikes)) * 100
                    ELSE 0
                END
            WHERE video_id = $1
        """, video_id)
        
        stats = await fetchrow("SELECT likes, dislikes, rating FROM video_stats WHERE video_id = $1", video_id)
        return dict(stats) if stats else {"likes": 0, "dislikes": 0, "rating": 0}
    except Exception as e:
        print(f"❌ Ошибка rate_video: {e}")
        traceback.print_exc()
        return None


async def get_video_rating(video_id: int):
    try:
        row = await fetchrow("SELECT likes, dislikes, rating FROM video_stats WHERE video_id = $1", video_id)
        return dict(row) if row else {"likes": 0, "dislikes": 0, "rating": 0}
    except:
        return {"likes": 0, "dislikes": 0, "rating": 0}


async def get_user_video_rating(video_id: int, user_id: int):
    try:
        row = await fetchrow("SELECT rating FROM video_ratings WHERE video_id = $1 AND user_id = $2", video_id, user_id)
        return row["rating"] if row else 0
    except:
        return 0


# ========== ФУНКЦИИ ДЛЯ ЗАДАНИЙ БОЕВОГО ПРОПУСКА ==========
async def get_battlepass_tasks():
    try:
        rows = await fetch("SELECT * FROM battlepass_tasks WHERE is_active = 1 ORDER BY id")
        return [dict(row) for row in rows]
    except:
        return []


async def get_battlepass_task(task_id: int):
    try:
        row = await fetchrow("SELECT * FROM battlepass_tasks WHERE id = $1", task_id)
        return dict(row) if row else None
    except:
        return None


async def add_battlepass_task(title: str, description: str, reward_xp: int, max_completions: int = 1, task_type: str = 'default'):
    try:
        row = await fetchrow("""
            INSERT INTO battlepass_tasks (title, description, reward_xp, max_completions, task_type)
            VALUES ($1, $2, $3, $4, $5) RETURNING id
        """, title, description, reward_xp, max_completions, task_type)
        return row["id"]
    except Exception as e:
        print(f"❌ Ошибка add_battlepass_task: {e}")
        return None


async def update_battlepass_task(task_id: int, **kwargs):
    try:
        updates = []
        values = []
        for key, value in kwargs.items():
            if value is not None:
                updates.append(f"{key} = ${len(values) + 2}")
                values.append(value)
        
        if not updates:
            return False
        
        values.append(task_id)
        query = f"UPDATE battlepass_tasks SET {', '.join(updates)} WHERE id = ${len(values)}"
        await execute(query, *values)
        return True
    except Exception as e:
        print(f"❌ Ошибка update_battlepass_task: {e}")
        return False


async def remove_battlepass_task(task_id: int):
    try:
        await execute("DELETE FROM battlepass_tasks WHERE id = $1", task_id)
        await execute("DELETE FROM user_battlepass_tasks WHERE task_id = $1", task_id)
        return True
    except:
        return False


async def get_user_battlepass_completed_count(user_id: int, task_id: int) -> int:
    try:
        return await fetchval("SELECT COUNT(*) FROM user_battlepass_tasks WHERE user_id = $1 AND task_id = $2", user_id, task_id) or 0
    except:
        return 0


async def can_complete_battlepass_task(user_id: int, task_id: int) -> bool:
    try:
        task = await get_battlepass_task(task_id)
        if not task:
            return False
        completed = await get_user_battlepass_completed_count(user_id, task_id)
        return completed < task["max_completions"]
    except:
        return False


async def complete_battlepass_task(user_id: int, task_id: int) -> bool:
    try:
        if not await can_complete_battlepass_task(user_id, task_id):
            return False
        task = await get_battlepass_task(task_id)
        if not task:
            return False
        await execute("INSERT INTO user_battlepass_tasks (user_id, task_id) VALUES ($1, $2)", user_id, task_id)
        await add_battlepass_exp_db(user_id, task["reward_xp"])
        return True
    except Exception as e:
        print(f"❌ Ошибка complete_battlepass_task: {e}")
        return False


async def get_user_battlepass_tasks_status(user_id: int):
    try:
        tasks = await get_battlepass_tasks()
        for task in tasks:
            task["completed"] = await get_user_battlepass_completed_count(user_id, task["id"])
            task["can_complete"] = task["completed"] < task["max_completions"]
        return tasks
    except:
        return []


async def admin_get_all_battlepass_tasks():
    try:
        rows = await fetch("SELECT * FROM battlepass_tasks ORDER BY id")
        return [dict(row) for row in rows]
    except:
        return []


async def admin_toggle_battlepass_task(task_id: int, is_active: bool):
    return await update_battlepass_task(task_id, is_active=1 if is_active else 0)


# ========== ФУНКЦИИ ДЛЯ ОБЯЗАТЕЛЬНЫХ КАНАЛОВ ==========
async def get_main_admin_id() -> Optional[int]:
    row = await fetchrow("SELECT user_id FROM admins WHERE is_main_admin = 1 LIMIT 1")
    return row["user_id"] if row else None


async def set_main_admin(user_id: int, username: str = "") -> Optional[int]:
    try:
        current_main = await get_main_admin_id()
        if current_main:
            return current_main
        
        await execute("""
            INSERT INTO users (user_id, username, is_verified, is_admin)
            VALUES ($1, $2, 1, 1)
            ON CONFLICT (user_id) DO UPDATE SET is_admin = 1
        """, user_id, username)
        
        await execute("""
            INSERT INTO admins (user_id, username, added_by, added_at, is_main_admin, can_add_admins)
            VALUES ($1, $2, $1, CURRENT_TIMESTAMP, 1, 1)
            ON CONFLICT (user_id) DO UPDATE SET is_main_admin = 1, can_add_admins = 1
        """, user_id, username)
        return user_id
    except Exception as e:
        print(f"❌ Ошибка установки главного админа: {e}")
        return None


def is_verified_sync(user_id: int) -> bool:
    import asyncio
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.run_coroutine_threadsafe(_is_verified_async(user_id), loop).result()
        else:
            return asyncio.run(_is_verified_async(user_id))
    except:
        return False


async def _is_verified_async(user_id: int) -> bool:
    row = await fetchrow("SELECT is_verified FROM users WHERE user_id = $1", user_id)
    return row and row["is_verified"] == 1


print("✅ db.py (PostgreSQL) загружен")
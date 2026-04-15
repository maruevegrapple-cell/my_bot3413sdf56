# ================= БОЕВОЙ ПРОПУСК =================
import json
from datetime import datetime
from db import execute, fetchrow

# Уровни боевого пропуска
BATTLEPASS_LEVELS = {
    1: {"exp": 0, "reward": 10, "premium_reward": 130},
    2: {"exp": 50, "reward": 10, "premium_reward": 130},
    3: {"exp": 100, "reward": 10, "premium_reward": 130},
    4: {"exp": 150, "reward": 10, "premium_reward": 130},
    5: {"exp": 200, "reward": 20, "premium_reward": 130},
    6: {"exp": 250, "reward": 10, "premium_reward": 130},
    7: {"exp": 300, "reward": 10, "premium_reward": 130},
    8: {"exp": 350, "reward": 10, "premium_reward": 130},
    9: {"exp": 400, "reward": 10, "premium_reward": 130},
    10: {"exp": 450, "reward": 30, "premium_reward": 130},
    11: {"exp": 500, "reward": 10, "premium_reward": 130},
    12: {"exp": 550, "reward": 10, "premium_reward": 130},
    13: {"exp": 600, "reward": 10, "premium_reward": 130},
    14: {"exp": 650, "reward": 10, "premium_reward": 130},
    15: {"exp": 700, "reward": 40, "premium_reward": 130},
    16: {"exp": 750, "reward": 10, "premium_reward": 130},
    17: {"exp": 800, "reward": 10, "premium_reward": 130},
    18: {"exp": 850, "reward": 10, "premium_reward": 130},
    19: {"exp": 900, "reward": 10, "premium_reward": 130},
    20: {"exp": 950, "reward": 60, "premium_reward": 260},
}

MAX_LEVEL = 20
DAILY_EXP_LIMIT = 200
HOURLY_EXP = 5
HOURLY_COOLDOWN = 3600
PREMIUM_PRICE_STARS = 400
PREMIUM_PRICE_USD = 5.0


async def init_battlepass_table():
    """Создать таблицу для боевого пропуска"""
    try:
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
                last_hourly_claim TIMESTAMP
            )
        """)
        print("✅ Таблица battlepass создана")
    except Exception as e:
        print(f"❌ Ошибка создания battlepass: {e}")


async def get_battlepass(user_id: int):
    """Получить данные боевого пропуска пользователя"""
    try:
        row = await fetchrow("SELECT * FROM battlepass WHERE user_id = $1", user_id)
        
        if not row:
            await execute("""
                INSERT INTO battlepass (user_id, level, exp, daily_exp, last_daily_reset, claimed_rewards, last_hourly_claim)
                VALUES ($1, 1, 0, 0, CURRENT_TIMESTAMP, '[]', CURRENT_TIMESTAMP)
            """, user_id)
            row = await fetchrow("SELECT * FROM battlepass WHERE user_id = $1", user_id)
        
        # Проверяем сброс ежедневного опыта
        if row:
            last_reset = row["last_daily_reset"]
            if last_reset:
                last_date = last_reset.date()
                today = datetime.now().date()
                if last_date != today:
                    await execute("UPDATE battlepass SET daily_exp = 0, last_daily_reset = CURRENT_TIMESTAMP WHERE user_id = $1", user_id)
                    row = await fetchrow("SELECT * FROM battlepass WHERE user_id = $1", user_id)
        
        return dict(row) if row else None
    except Exception as e:
        print(f"❌ Ошибка get_battlepass: {e}")
        return None


async def create_battlepass(user_id: int):
    """Создать новый боевой пропуск для пользователя"""
    try:
        await execute("""
            INSERT INTO battlepass (user_id, level, exp, daily_exp, last_daily_reset, claimed_rewards, last_hourly_claim)
            VALUES ($1, 1, 0, 0, CURRENT_TIMESTAMP, '[]', CURRENT_TIMESTAMP)
            ON CONFLICT (user_id) DO NOTHING
        """, user_id)
        return True
    except Exception as e:
        print(f"❌ Ошибка create_battlepass: {e}")
        return False


async def update_battlepass(user_id: int, level: int = None, exp: int = None, daily_exp: int = None, 
                     claimed_rewards: str = None, premium: int = None, last_hourly_claim=None,
                     last_daily_reset=None):
    """Обновить данные боевого пропуска"""
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


async def add_battlepass_exp_db(user_id: int, exp: int):
    """Добавить опыт в боевой пропуск"""
    try:
        bp = await get_battlepass(user_id)
        if not bp:
            return {"status": "error", "exp_gained": 0}
        
        # Проверка дневного лимита
        daily_exp = bp["daily_exp"]
        if daily_exp + exp > DAILY_EXP_LIMIT:
            exp = DAILY_EXP_LIMIT - daily_exp
            if exp <= 0:
                return {"status": "limit_reached", "exp_gained": 0}
        
        new_daily_exp = daily_exp + exp
        new_exp = bp["exp"] + exp
        new_level = bp["level"]
        
        # Повышение уровня
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
    """Забрать ежечасный опыт"""
    try:
        bp = await get_battlepass(user_id)
        if not bp:
            return {"status": "error", "message": "Не удалось создать пропуск"}
        
        last_claim = bp.get("last_hourly_claim")
        if last_claim:
            now = datetime.now()
            hours_passed = (now - last_claim).total_seconds() / 3600
            
            if hours_passed < 1:
                minutes_left = int(60 - (now - last_claim).total_seconds() / 60)
                return {"status": "cooldown", "minutes_left": minutes_left}
        
        # Добавляем 5 XP
        result = await add_battlepass_exp_db(user_id, HOURLY_EXP)
        
        if result["status"] == "success":
            await update_battlepass(user_id, last_hourly_claim=datetime.now())
            return {"status": "success", "exp_gained": HOURLY_EXP, 
                    "leveled_up": result.get("leveled_up", False), 
                    "new_level": result.get("new_level")}
        
        return {"status": "error", "message": "Ошибка при начислении опыта"}
    except Exception as e:
        print(f"❌ Ошибка claim_hourly_exp_db: {e}")
        return {"status": "error", "message": str(e)}


async def claim_battlepass_reward_db(user_id: int, level: int, is_premium: bool = False):
    """Забрать награду уровня"""
    try:
        bp = await get_battlepass(user_id)
        if not bp or bp["level"] < level:
            return False
        
        claimed = json.loads(bp["claimed_rewards"])
        
        reward_key = f"level_{level}"
        if is_premium:
            if not bp.get("premium", 0):
                return False
            reward_key = f"premium_{level}"
        
        if reward_key in claimed:
            return False
        
        if is_premium:
            reward_amount = BATTLEPASS_LEVELS[level]["premium_reward"]
        else:
            reward_amount = BATTLEPASS_LEVELS[level]["reward"]
        
        # Начисляем награду
        await execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", reward_amount, user_id)
        
        claimed.append(reward_key)
        await update_battlepass(user_id, claimed_rewards=json.dumps(claimed))
        
        return {"reward": reward_amount, "level": level, "is_premium": is_premium}
    except Exception as e:
        print(f"❌ Ошибка claim_battlepass_reward_db: {e}")
        return False


async def activate_premium_battlepass_db(user_id: int):
    """Активировать премиум пропуск"""
    try:
        await update_battlepass(user_id, premium=1, premium_purchased=1)
        return True
    except Exception as e:
        print(f"❌ Ошибка activate_premium_battlepass_db: {e}")
        return False


print("✅ battlepass.py загружен")
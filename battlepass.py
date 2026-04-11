# ================= БОЕВОЙ ПРОПУСК =================
import json
from datetime import datetime, timedelta
from db import cursor, conn

# Уровни боевого пропуска с повышенными наградами
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
    20: {"exp": 950, "reward": 60, "premium_reward": 260},  # Последний уровень двойная награда
}

MAX_LEVEL = 20
DAILY_EXP_LIMIT = 200
HOURLY_EXP = 5
HOURLY_COOLDOWN = 3600  # 1 час в секундах
PREMIUM_PRICE_STARS = 400
PREMIUM_PRICE_USD = 5.0


def init_battlepass_table():
    """Создать таблицу для боевого пропуска"""
    try:
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
        conn.commit()
        print("✅ Таблица battlepass создана")
    except Exception as e:
        print(f"❌ Ошибка создания battlepass: {e}")


def get_battlepass(user_id: int):
    """Получить данные боевого пропуска пользователя"""
    try:
        cursor.execute("SELECT * FROM battlepass WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        
        if not row:
            # Создаем новый пропуск
            cursor.execute("""
                INSERT INTO battlepass (user_id, level, exp, daily_exp, last_daily_reset, claimed_rewards, last_hourly_claim)
                VALUES (?, 1, 0, 0, ?, '[]', ?)
            """, (user_id, datetime.now(), datetime.now()))
            conn.commit()
            
            cursor.execute("SELECT * FROM battlepass WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
        
        # Проверяем сброс ежедневного опыта
        if row:
            last_reset = row["last_daily_reset"]
            if last_reset:
                last_date = datetime.fromisoformat(last_reset).date()
                today = datetime.now().date()
                if last_date != today:
                    cursor.execute("UPDATE battlepass SET daily_exp = 0, last_daily_reset = ? WHERE user_id = ?", 
                                  (datetime.now(), user_id))
                    conn.commit()
                    row = dict(row)
                    row["daily_exp"] = 0
        
        return dict(row) if row else None
    except Exception as e:
        print(f"❌ Ошибка get_battlepass: {e}")
        return None


def create_battlepass(user_id: int):
    """Создать новый боевой пропуск для пользователя (для совместимости)"""
    try:
        cursor.execute("""
            INSERT OR IGNORE INTO battlepass (user_id, level, exp, daily_exp, last_daily_reset, claimed_rewards, last_hourly_claim)
            VALUES (?, 1, 0, 0, ?, '[]', ?)
        """, (user_id, datetime.now(), datetime.now()))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка create_battlepass: {e}")
        return False


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


def add_battlepass_exp(user_id: int, exp: int, source: str = "unknown"):
    """Добавить опыт в боевой пропуск"""
    try:
        bp = get_battlepass(user_id)
        if not bp:
            return False
        
        # Проверка дневного лимита
        if bp["daily_exp"] + exp > DAILY_EXP_LIMIT:
            exp = DAILY_EXP_LIMIT - bp["daily_exp"]
            if exp <= 0:
                return False
        
        new_daily_exp = bp["daily_exp"] + exp
        new_exp = bp["exp"] + exp
        new_level = bp["level"]
        
        # Повышение уровня
        leveled_up = False
        while new_level < MAX_LEVEL and new_exp >= BATTLEPASS_LEVELS[new_level + 1]["exp"]:
            new_level += 1
            leveled_up = True
        
        cursor.execute("""
            UPDATE battlepass 
            SET exp = ?, level = ?, daily_exp = ?
            WHERE user_id = ?
        """, (new_exp, new_level, new_daily_exp, user_id))
        conn.commit()
        
        return {"leveled_up": leveled_up, "new_level": new_level, "exp_gained": exp}
    except Exception as e:
        print(f"❌ Ошибка add_battlepass_exp: {e}")
        return False


def add_battlepass_exp_db(user_id: int, exp: int):
    """Обёртка для add_battlepass_exp (для совместимости с handlers.py)"""
    result = add_battlepass_exp(user_id, exp, "unknown")
    if result:
        return {"status": "success", "exp_gained": result["exp_gained"], 
                "leveled_up": result["leveled_up"], "new_level": result["new_level"]}
    return {"status": "error", "exp_gained": 0}


def claim_hourly_exp(user_id: int) -> dict:
    """Забрать ежечасный опыт (5 XP в час)"""
    try:
        bp = get_battlepass(user_id)
        if not bp:
            return {"status": "error", "message": "Пропуск не найден"}
        
        last_claim = bp.get("last_hourly_claim")
        if last_claim:
            last_time = datetime.fromisoformat(last_claim)
            now = datetime.now()
            hours_passed = (now - last_time).total_seconds() / 3600
            
            if hours_passed < 1:
                minutes_left = int(60 - (now - last_time).total_seconds() / 60)
                return {"status": "cooldown", "minutes_left": minutes_left}
        
        # Добавляем 5 XP
        result = add_battlepass_exp(user_id, HOURLY_EXP, "hourly")
        
        if result:
            cursor.execute("UPDATE battlepass SET last_hourly_claim = ? WHERE user_id = ?", 
                          (datetime.now(), user_id))
            conn.commit()
            return {"status": "success", "exp_gained": HOURLY_EXP, 
                    "leveled_up": result.get("leveled_up", False), 
                    "new_level": result.get("new_level")}
        
        return {"status": "error", "message": "Ошибка при начислении опыта"}
    except Exception as e:
        print(f"❌ Ошибка claim_hourly_exp: {e}")
        return {"status": "error", "message": str(e)}


def claim_hourly_exp_db(user_id: int):
    """Обёртка для claim_hourly_exp (для совместимости с handlers.py)"""
    return claim_hourly_exp(user_id)


def claim_battlepass_reward(user_id: int, level: int, is_premium: bool = False):
    """Забрать награду уровня"""
    try:
        bp = get_battlepass(user_id)
        if not bp:
            return False
        
        if bp["level"] < level:
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
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (reward_amount, user_id))
        
        claimed.append(reward_key)
        cursor.execute("UPDATE battlepass SET claimed_rewards = ? WHERE user_id = ?", 
                      (json.dumps(claimed), user_id))
        conn.commit()
        
        return {"reward": reward_amount, "level": level, "is_premium": is_premium}
    except Exception as e:
        print(f"❌ Ошибка claim_battlepass_reward: {e}")
        return False


def claim_battlepass_reward_db(user_id: int, level: int, is_premium: bool = False):
    """Обёртка для claim_battlepass_reward (для совместимости с handlers.py)"""
    return claim_battlepass_reward(user_id, level, is_premium)


def buy_premium_battlepass(user_id: int):
    """Купить премиум боевой пропуск (создаёт заявку на оплату)"""
    try:
        bp = get_battlepass(user_id)
        if bp and bp.get("premium", 0):
            return {"status": "error", "message": "У вас уже есть премиум пропуск"}
        
        return {"status": "payment_required", "price_stars": PREMIUM_PRICE_STARS, "price_usd": PREMIUM_PRICE_USD}
    except Exception as e:
        print(f"❌ Ошибка buy_premium_battlepass: {e}")
        return {"status": "error", "message": str(e)}


def activate_premium_battlepass(user_id: int):
    """Активировать премиум пропуск после оплаты"""
    try:
        cursor.execute("UPDATE battlepass SET premium = 1, premium_purchased = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка activate_premium_battlepass: {e}")
        return False


def activate_premium_battlepass_db(user_id: int):
    """Обёртка для activate_premium_battlepass (для совместимости)"""
    return activate_premium_battlepass(user_id)


def can_claim_premium_rewards(user_id: int) -> bool:
    """Проверить, может ли пользователь забирать премиум награды"""
    bp = get_battlepass(user_id)
    return bp and bp.get("premium", 0) == 1


def get_battlepass_stats(user_id: int):
    """Получить статистику пропуска"""
    bp = get_battlepass(user_id)
    if not bp:
        return None
    
    claimed = json.loads(bp["claimed_rewards"])
    
    total_rewards = 0
    total_premium_rewards = 0
    claimed_rewards = 0
    claimed_premium = 0
    
    for lvl in range(1, bp["level"] + 1):
        total_rewards += BATTLEPASS_LEVELS[lvl]["reward"]
        if f"level_{lvl}" in claimed:
            claimed_rewards += BATTLEPASS_LEVELS[lvl]["reward"]
        
        if bp.get("premium", 0):
            total_premium_rewards += BATTLEPASS_LEVELS[lvl]["premium_reward"]
            if f"premium_{lvl}" in claimed:
                claimed_premium += BATTLEPASS_LEVELS[lvl]["premium_reward"]
    
    # Время до следующего ежечасного бонуса
    last_hourly = bp.get("last_hourly_claim")
    next_hourly_seconds = 3600
    if last_hourly:
        last_time = datetime.fromisoformat(last_hourly)
        elapsed = (datetime.now() - last_time).total_seconds()
        if elapsed < 3600:
            next_hourly_seconds = int(3600 - elapsed)
        else:
            next_hourly_seconds = 0
    
    # Опыт до следующего уровня
    next_level_exp = BATTLEPASS_LEVELS.get(bp["level"] + 1, {}).get("exp", BATTLEPASS_LEVELS[bp["level"]]["exp"])
    exp_to_next = next_level_exp - bp["exp"]
    
    return {
        "level": bp["level"],
        "exp": bp["exp"],
        "exp_to_next": exp_to_next,
        "daily_exp": bp["daily_exp"],
        "premium": bp.get("premium", 0),
        "total_rewards": total_rewards,
        "claimed_rewards": claimed_rewards,
        "total_premium_rewards": total_premium_rewards,
        "claimed_premium": claimed_premium,
        "next_hourly_seconds": next_hourly_seconds
    }


def get_battlepass_info_text(user_id: int):
    """Получить текст для отображения боевого пропуска"""
    stats = get_battlepass_stats(user_id)
    if not stats:
        return "❌ Ошибка загрузки пропуска"
    
    bp = get_battlepass(user_id)
    claimed = json.loads(bp["claimed_rewards"])
    
    # Время до следующего бонуса
    hourly_text = ""
    if stats["next_hourly_seconds"] > 0:
        minutes = stats["next_hourly_seconds"] // 60
        seconds = stats["next_hourly_seconds"] % 60
        hourly_text = f"⏰ Следующий бонус: {minutes:02d}:{seconds:02d}"
    else:
        hourly_text = "⏰ Бонус доступен!"
    
    # Подсчёт заработанных конфет
    earned_from_free = 0
    earned_from_premium = 0
    for lvl in range(1, stats["level"] + 1):
        if f"level_{lvl}" in claimed:
            earned_from_free += BATTLEPASS_LEVELS[lvl]["reward"]
        if stats["premium"] and f"premium_{lvl}" in claimed:
            earned_from_premium += BATTLEPASS_LEVELS[lvl]["premium_reward"]
    
    total_candies = earned_from_free + earned_from_premium
    
    text = f"🎖 <b>Боевой пропуск!</b>\n\n"
    text += f"📊 <b>Твой уровень сейчас:</b> {stats['level']}/20\n"
    text += f"📈 <b>До следующего уровня:</b> {stats['exp_to_next']} XP\n"
    text += f"{hourly_text}\n"
    text += f"Получить опыт можно выполняя задания, и забирая ежечасный бонус!\n\n"
    text += f"🍬 <b>Ты заработал конфет с пропуском:</b> {total_candies} 🍬\n"
    
    if stats["premium"]:
        text += f"\n💎 <b>Премиум пропуск активен!</b>\n"
        available_premium = 0
        for lvl in range(1, stats["level"] + 1):
            if f"premium_{lvl}" not in claimed:
                available_premium += BATTLEPASS_LEVELS[lvl]["premium_reward"]
        text += f"🎁 Доступно премиум наград: {available_premium} 🍬"
    
    return text


init_battlepass_table()
print("✅ battlepass.py загружен")
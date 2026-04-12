import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession

logger = logging.getLogger(__name__)

active_mirror_bots: Dict[str, Bot] = {}
active_mirror_dispatchers: Dict[str, Dispatcher] = {}


def init_mirrors_table():
    try:
        from db import cursor, conn
        
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
        
        cursor.execute("PRAGMA table_info(mirror_bots)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'is_main' not in columns:
            cursor.execute("ALTER TABLE mirror_bots ADD COLUMN is_main INTEGER DEFAULT 0")
        if 'notes' not in columns:
            cursor.execute("ALTER TABLE mirror_bots ADD COLUMN notes TEXT")
        if 'mirror_code' not in columns:
            cursor.execute("ALTER TABLE mirror_bots ADD COLUMN mirror_code TEXT UNIQUE")
        
        conn.commit()
        print("✅ Таблица mirror_bots создана/проверена")
    except Exception as e:
        print(f"❌ Ошибка init_mirrors_table: {e}")


def get_mirror_bot_by_id(bot_id: int) -> Optional[dict]:
    try:
        from db import cursor
        cursor.execute("SELECT * FROM mirror_bots WHERE id = ?", (bot_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None


def get_mirror_bot_by_token_db(token: str) -> Optional[dict]:
    try:
        from db import cursor
        cursor.execute("SELECT * FROM mirror_bots WHERE bot_token = ?", (token,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None


def get_mirror_bot_by_code_db(code: str) -> Optional[dict]:
    try:
        from db import cursor
        cursor.execute("SELECT * FROM mirror_bots WHERE mirror_code = ?", (code,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None


def get_user_mirror_bots_db(user_id: int) -> list:
    try:
        from db import cursor
        cursor.execute("SELECT * FROM mirror_bots WHERE added_by = ? AND is_main = 0 ORDER BY id ASC", (user_id,))
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def get_all_mirror_bots(include_main: bool = False) -> list:
    try:
        from db import cursor
        if include_main:
            cursor.execute("SELECT * FROM mirror_bots ORDER BY is_main DESC, id ASC")
        else:
            cursor.execute("SELECT * FROM mirror_bots WHERE is_main = 0 ORDER BY id ASC")
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def get_active_mirror_bots_db(include_main: bool = False) -> list:
    try:
        from db import cursor
        if include_main:
            cursor.execute("SELECT * FROM mirror_bots WHERE is_active = 1 ORDER BY is_main DESC, id ASC")
        else:
            cursor.execute("SELECT * FROM mirror_bots WHERE is_active = 1 AND is_main = 0 ORDER BY id ASC")
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def add_mirror_bot_db(token: str, username: str, added_by: int, notes: str = "") -> bool:
    try:
        from db import cursor, conn, generate_ref_code
        mirror_code = generate_ref_code(8)
        cursor.execute("""
            INSERT INTO mirror_bots (bot_token, bot_username, is_active, added_by, added_at, notes, is_main, mirror_code)
            VALUES (?, ?, 1, ?, ?, ?, 0, ?)
        """, (token, username, added_by, datetime.now(), notes, mirror_code))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ add_mirror_bot_db error: {e}")
        return False


def remove_mirror_bot_db(bot_id: int) -> bool:
    try:
        from db import cursor, conn
        cursor.execute("DELETE FROM mirror_bots WHERE id = ? AND is_main = 0", (bot_id,))
        conn.commit()
        return cursor.rowcount > 0
    except:
        return False


def remove_mirror_bot(bot_id: int) -> bool:
    return remove_mirror_bot_db(bot_id)


def toggle_mirror_bot_db(bot_id: int, is_active: bool) -> bool:
    try:
        from db import cursor, conn
        cursor.execute("UPDATE mirror_bots SET is_active = ? WHERE id = ? AND is_main = 0", (1 if is_active else 0, bot_id))
        conn.commit()
        return cursor.rowcount > 0
    except:
        return False


def update_mirror_username_db(bot_id: int, username: str) -> bool:
    try:
        from db import cursor, conn
        cursor.execute("UPDATE mirror_bots SET bot_username = ? WHERE id = ?", (username, bot_id))
        conn.commit()
        return True
    except:
        return False


def set_main_bot(token: str, username: str = "", added_by: int = None) -> bool:
    try:
        from db import cursor, conn
        
        cursor.execute("UPDATE mirror_bots SET is_main = 0")
        
        cursor.execute("SELECT id FROM mirror_bots WHERE bot_token = ?", (token,))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute("UPDATE mirror_bots SET is_main = 1, bot_username = ?, is_active = 1 WHERE bot_token = ?", 
                          (username, token))
        else:
            from db import generate_ref_code
            mirror_code = generate_ref_code(8)
            cursor.execute("""
                INSERT INTO mirror_bots (bot_token, bot_username, is_active, is_main, added_by, added_at, mirror_code)
                VALUES (?, ?, 1, 1, ?, ?, ?)
            """, (token, username, added_by, datetime.now(), mirror_code))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ set_main_bot error: {e}")
        return False


def add_mirror_bot_by_user(token: str, username: str, user_id: int) -> tuple:
    try:
        from db import cursor, conn, generate_ref_code
        
        cursor.execute("SELECT id FROM mirror_bots WHERE bot_token = ?", (token,))
        if cursor.fetchone():
            return False, "❌ Этот бот уже зарегистрирован как зеркало!"
        
        cursor.execute("SELECT COUNT(*) as count FROM mirror_bots WHERE added_by = ? AND is_main = 0", (user_id,))
        count = cursor.fetchone()["count"]
        if count >= 3:
            return False, "❌ Вы можете создать не более 3 зеркал!"
        
        mirror_code = generate_ref_code(8)
        cursor.execute("""
            INSERT INTO mirror_bots (bot_token, bot_username, is_active, added_by, added_at, notes, is_main, mirror_code)
            VALUES (?, ?, 1, ?, ?, ?, 0, ?)
        """, (token, username, user_id, datetime.now(), f"Создано пользователем {user_id}", mirror_code))
        
        conn.commit()
        
        cursor.execute("SELECT id FROM mirror_bots WHERE bot_token = ?", (token,))
        row = cursor.fetchone()
        
        return True, row["id"] if row else None
    except Exception as e:
        print(f"❌ add_mirror_bot_by_user error: {e}")
        return False, f"❌ Ошибка: {e}"


def remove_mirror_bot_by_user(bot_id: int, user_id: int) -> bool:
    try:
        from db import cursor, conn
        cursor.execute("DELETE FROM mirror_bots WHERE id = ? AND added_by = ? AND is_main = 0", (bot_id, user_id))
        conn.commit()
        return cursor.rowcount > 0
    except:
        return False


async def start_mirror_bot(token: str, username: str = ""):
    """Запустить отдельного бота-зеркало"""
    logger.info(f"🔵 Запуск зеркала {username}")
    
    try:
        from handlers import (
            start, videos, shop, profile, battlepass_menu, bonus, promo, tasks_menu,
            suggestion_start, support_start, check_subscribe, show_languages,
            change_language, buy_pack, select_payment_method, buy_subscription,
            pay_subscription_asset, pay_subscription_stars, check_subscription_payment,
            buy_private, private_crypto, private_asset_selected, private_pay_stars,
            check_private_payment, tasks_category, tasks_refresh, task_detail, do_task,
            like_video, dislike_video, back_to_menu, safe_answer
        )
        from locales import get_text
        from db import is_verified
        
        session = AiohttpSession(timeout=60)
        bot = Bot(
            token=token,
            session=session,
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML,
                protect_content=True
            )
        )
        
        me = await bot.get_me()
        logger.info(f"✅ Зеркало @{me.username} (ID: {me.id}) запущено")
        
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        
        mirror_router = Router()
        
        # Обёртки для зеркал (без проверки подписки, только верификация)
        async def mirror_start_wrapper(message: Message, state: FSMContext, bot: Bot):
            user_id = message.from_user.id
            if not is_verified(user_id):
                await message.answer(get_text(user_id, "verification_required"))
                return
            await start(message, state, bot)
        
        async def mirror_videos_wrapper(call: CallbackQuery, state: FSMContext, bot: Bot):
            user_id = call.from_user.id
            if not is_verified(user_id):
                await safe_answer(call, get_text(user_id, "verification_required"), True)
                return
            await videos(call, state, bot)
        
        async def mirror_shop_wrapper(call: CallbackQuery, state: FSMContext, bot: Bot):
            user_id = call.from_user.id
            if not is_verified(user_id):
                await safe_answer(call, get_text(user_id, "verification_required"), True)
                return
            await shop(call, state, bot)
        
        async def mirror_profile_wrapper(call: CallbackQuery, state: FSMContext, bot: Bot):
            user_id = call.from_user.id
            if not is_verified(user_id):
                await safe_answer(call, get_text(user_id, "verification_required"), True)
                return
            await profile(call, state, bot)
        
        async def mirror_battlepass_wrapper(call: CallbackQuery, state: FSMContext, bot: Bot):
            user_id = call.from_user.id
            if not is_verified(user_id):
                await safe_answer(call, get_text(user_id, "verification_required"), True)
                return
            await battlepass_menu(call, state, bot)
        
        async def mirror_bonus_wrapper(call: CallbackQuery, state: FSMContext, bot: Bot):
            user_id = call.from_user.id
            if not is_verified(user_id):
                await safe_answer(call, get_text(user_id, "verification_required"), True)
                return
            await bonus(call, state, bot)
        
        async def mirror_promo_wrapper(call: CallbackQuery, state: FSMContext, bot: Bot):
            user_id = call.from_user.id
            if not is_verified(user_id):
                await safe_answer(call, get_text(user_id, "verification_required"), True)
                return
            await promo(call, state, bot)
        
        async def mirror_tasks_wrapper(call: CallbackQuery, state: FSMContext, bot: Bot):
            user_id = call.from_user.id
            if not is_verified(user_id):
                await safe_answer(call, get_text(user_id, "verification_required"), True)
                return
            await tasks_menu(call, state, bot)
        
        async def mirror_suggestion_wrapper(call: CallbackQuery, state: FSMContext, bot: Bot):
            user_id = call.from_user.id
            if not is_verified(user_id):
                await safe_answer(call, get_text(user_id, "verification_required"), True)
                return
            await suggestion_start(call, state)
        
        async def mirror_support_wrapper(call: CallbackQuery, state: FSMContext, bot: Bot):
            user_id = call.from_user.id
            if not is_verified(user_id):
                await safe_answer(call, get_text(user_id, "verification_required"), True)
                return
            await support_start(call, state, bot)
        
        # Регистрируем обёртки
        mirror_router.message(CommandStart())(mirror_start_wrapper)
        mirror_router.callback_query(F.data == "videos")(mirror_videos_wrapper)
        mirror_router.callback_query(F.data == "shop")(mirror_shop_wrapper)
        mirror_router.callback_query(F.data == "profile")(mirror_profile_wrapper)
        mirror_router.callback_query(F.data == "battlepass_menu")(mirror_battlepass_wrapper)
        mirror_router.callback_query(F.data == "bonus")(mirror_bonus_wrapper)
        mirror_router.callback_query(F.data == "promo")(mirror_promo_wrapper)
        mirror_router.callback_query(F.data == "tasks")(mirror_tasks_wrapper)
        mirror_router.callback_query(F.data == "suggestion")(mirror_suggestion_wrapper)
        mirror_router.callback_query(F.data == "support")(mirror_support_wrapper)
        mirror_router.callback_query(F.data == "check_subscribe")(check_subscribe)
        mirror_router.callback_query(F.data == "show_languages")(show_languages)
        mirror_router.callback_query(F.data.startswith("lang_"))(change_language)
        mirror_router.callback_query(F.data.startswith("buy_pack_"))(buy_pack)
        mirror_router.callback_query(F.data.startswith("pay_method_"))(select_payment_method)
        mirror_router.callback_query(F.data.startswith("buy_subscription_"))(buy_subscription)
        mirror_router.callback_query(F.data.startswith("pay_subscription_asset_"))(pay_subscription_asset)
        mirror_router.callback_query(F.data.startswith("pay_subscription_stars_"))(pay_subscription_stars)
        mirror_router.callback_query(F.data.startswith("check_subscription_"))(check_subscription_payment)
        mirror_router.callback_query(F.data == "buy_private")(buy_private)
        mirror_router.callback_query(F.data == "private_crypto")(private_crypto)
        mirror_router.callback_query(F.data.startswith("private_asset_"))(private_asset_selected)
        mirror_router.callback_query(F.data == "private_stars")(private_pay_stars)
        mirror_router.callback_query(F.data.startswith("check_private_"))(check_private_payment)
        mirror_router.callback_query(F.data.startswith("tasks_category_"))(tasks_category)
        mirror_router.callback_query(F.data.startswith("tasks_refresh_"))(tasks_refresh)
        mirror_router.callback_query(F.data.startswith("task_"))(task_detail)
        mirror_router.callback_query(F.data.startswith("do_task_"))(do_task)
        mirror_router.callback_query(F.data.startswith("like_video_"))(like_video)
        mirror_router.callback_query(F.data.startswith("dislike_video_"))(dislike_video)
        mirror_router.callback_query(F.data == "menu")(back_to_menu)
        
        dp.include_router(mirror_router)
        
        @dp.message(F.forward_from | F.forward_from_chat)
        async def block_forward(message: Message):
            await message.delete()
        
        active_mirror_bots[token] = bot
        active_mirror_dispatchers[token] = dp
        
        asyncio.create_task(dp.start_polling(bot))
        
        mirror = get_mirror_bot_by_token_db(token)
        if mirror and me.username:
            update_mirror_username_db(mirror["id"], me.username)
        
        logger.info(f"✅ Зеркало @{me.username} успешно запущено!")
        return bot
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска зеркала @{username}: {e}")
        import traceback
        traceback.print_exc()
        return None


async def stop_mirror_bot(token: str):
    if token in active_mirror_bots:
        bot = active_mirror_bots[token]
        try:
            await bot.session.close()
        except:
            pass
        del active_mirror_bots[token]
        if token in active_mirror_dispatchers:
            del active_mirror_dispatchers[token]
        logger.info(f"✅ Зеркало остановлено")


async def stop_all_mirror_bots():
    for token in list(active_mirror_bots.keys()):
        await stop_mirror_bot(token)


async def start_all_mirror_bots(dp_main=None):
    from db import init_db
    init_db()
    init_mirrors_table()
    mirrors = get_active_mirror_bots_db(include_main=False)
    logger.info(f"🔄 Запуск {len(mirrors)} зеркал...")
    for mirror in mirrors:
        await start_mirror_bot(mirror["bot_token"], mirror.get("bot_username", ""))
    logger.info(f"✅ Запущено {len(active_mirror_bots)} зеркал")


init_mirrors_table()

print("✅ mirrors.py загружен")
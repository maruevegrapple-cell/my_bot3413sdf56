import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.filters import CommandStart, Command
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
        # Импортируем все необходимые функции из handlers (без проблемных импортов)
        from handlers import (
            start, videos, shop, profile, battlepass_menu, bonus, promo, tasks_menu,
            suggestion_start, support_start, check_subscribe, show_languages,
            change_language, buy_pack, select_payment_method, buy_subscription,
            pay_subscription_asset, pay_subscription_stars, check_subscription_payment,
            buy_private, private_crypto, private_asset_selected, private_pay_stars,
            check_private_payment, tasks_category, tasks_refresh, task_detail, do_task,
            like_video, dislike_video, back_to_menu, safe_answer,
            CaptchaStates, MathCaptchaStates, SubscribeStates,
            generate_captcha_image, generate_math_captcha,
            check_admin_access, get_admin_menu,
            upload_video, handle_suggestion_video,
            admin_panel, admin_stats, admin_broadcast,
            admin_add_balance, admin_remove_balance, admin_add_promo,
            admin_op_menu, admin_manage_menu_callback,
            admin_tasks_menu_handler, admin_auto_tasks_menu,
            block_forward,
            # Эти переменные нужны для капчи
            captcha_data, captcha_attempts, math_captcha_data, math_captcha_attempts, banned_users
        )
        from db import (
            is_verified, get_user, cursor, conn, update_user_balance, 
            generate_ref_code, has_received_subscribe_bonus, 
            mark_subscribe_bonus_received, get_user_language_db, set_user_language_db
        )
        from config import CHANNEL_ID, SUBSCRIBE_BONUS, REF_BONUS
        from keyboards import subscribe_menu
        from locales import get_text, set_user_language, get_user_language
        
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
        
        # Создаем роутер для зеркала
        mirror_router = Router()
        
        # ========== ПОЛНОЦЕННЫЙ ХЭНДЛЕР START ДЛЯ ЗЕРКАЛ ==========
        @mirror_router.message(CommandStart())
        async def mirror_start_handler(message: Message, state: FSMContext, bot: Bot):
            user_id = message.from_user.id
            username = message.from_user.username or "пользователь"
            logger.info(f"🟢 MIRROR START from {user_id} (@{username})")
            
            # Проверяем язык пользователя
            user_lang = get_user_language_db(user_id)
            set_user_language(user_id, user_lang)
            
            # Проверяем бан
            if user_id in banned_users:
                ban_until = banned_users[user_id]
                if datetime.now() < ban_until:
                    remaining = ban_until - datetime.now()
                    minutes = remaining.seconds // 60
                    seconds = remaining.seconds % 60
                    await message.answer(
                        f"🚫 <b>ДОСТУП ЗАБЛОКИРОВАН</b>\n\n"
                        f"⏳ Осталось: {minutes} мин {seconds} сек"
                    )
                    return
                else:
                    del banned_users[user_id]
            
            # Проверяем, админ ли пользователь
            has_access, _, is_main, can_manage = check_admin_access(user_id)
            if has_access:
                cursor.execute("""
                    INSERT OR IGNORE INTO users (user_id, username, is_verified, is_admin)
                    VALUES (?, ?, 1, 1)
                """, (user_id, username))
                cursor.execute("UPDATE users SET is_verified = 1, username = ? WHERE user_id = ?", (username, user_id))
                cursor.execute("SELECT ref_code FROM users WHERE user_id = ?", (user_id,))
                admin_data = cursor.fetchone()
                if not admin_data or not admin_data["ref_code"]:
                    ref_code = generate_ref_code()
                    cursor.execute("UPDATE users SET ref_code = ? WHERE user_id = ?", (ref_code, user_id))
                conn.commit()
                await message.answer("👑 Админ-панель", reply_markup=get_admin_menu(is_main, can_manage))
                return
            
            # Получаем или создаем пользователя
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
            
            # Проверяем реферальную ссылку
            args = message.text.split()
            referrer_id = None
            has_ref_in_link = False
            if len(args) > 1:
                ref_code = args[1].upper()
                cursor.execute("SELECT user_id FROM users WHERE ref_code = ?", (ref_code,))
                referrer = cursor.fetchone()
                if referrer:
                    referrer_id = referrer["user_id"]
                    if referrer_id != user_id:
                        has_ref_in_link = True
            
            if not user:
                new_ref_code = generate_ref_code()
                cursor.execute("""
                    INSERT INTO users (user_id, username, referrer, is_verified, ref_code, subscribe_bonus_received, is_admin, language)
                    VALUES (?, ?, ?, 0, ?, 0, 0, ?)
                """, (user_id, username, referrer_id, new_ref_code, user_lang))
                conn.commit()
                if referrer_id:
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REF_BONUS, referrer_id))
                    conn.commit()
                    try:
                        await bot.send_message(
                            referrer_id,
                            f"🎁 <b>Новый реферал!</b>\n\n"
                            f"По вашей ссылке зарегистрировался новый пользователь @{username}\n"
                            f"➕ Вам начислено +{REF_BONUS} 🍬"
                        )
                    except:
                        pass
            else:
                if not user["ref_code"]:
                    new_ref_code = generate_ref_code()
                    cursor.execute("UPDATE users SET ref_code = ? WHERE user_id = ?", (new_ref_code, user_id))
                    conn.commit()
                if has_ref_in_link and user["referrer"] is None:
                    cursor.execute("UPDATE users SET referrer = ? WHERE user_id = ?", (referrer_id, user_id))
                    conn.commit()
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (REF_BONUS, referrer_id))
                    conn.commit()
                    try:
                        await bot.send_message(
                            referrer_id,
                            f"🎁 <b>Новый реферал!</b>\n\n"
                            f"По вашей ссылке зарегистрировался пользователь @{username}\n"
                            f"➕ Вам начислено +{REF_BONUS} 🍬"
                        )
                    except:
                        pass
            
            # Проверка верификации
            if not is_verified(user_id):
                image_bytes, captcha_code = generate_captcha_image()
                captcha_data[user_id] = captcha_code
                await state.update_data(captcha_code=captcha_code)
                await state.set_state(CaptchaStates.waiting_for_captcha)
                await message.answer_photo(
                    photo=BufferedInputFile(file=image_bytes, filename="captcha.png"),
                    caption="🔐 <b>ПОДТВЕРЖДЕНИЕ (ШАГ 1/2)</b>\n\n"
                            "Введите код с картинки:\n"
                            "⚠️ Только заглавные буквы и цифры\n"
                            "📊 Осталось попыток: 3/3"
                )
                return
            
            # Проверка подписки на канал
            try:
                member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
                is_subscribed = member.status not in ["left", "kicked"]
            except:
                is_subscribed = False
            
            if not is_subscribed:
                await state.set_state(SubscribeStates.waiting_for_subscribe)
                await message.answer(
                    get_text(user_id, "subscribe_required").format(SUBSCRIBE_BONUS),
                    reply_markup=subscribe_menu
                )
                return
            
            # Все проверки пройдены - показываем главное меню
            from keyboards import get_main_menu
            await message.answer(get_text(user_id, "welcome"), reply_markup=get_main_menu(user_id))
        
        # ========== ХЭНДЛЕР ДЛЯ ПРОВЕРКИ ПОДПИСКИ ==========
        @mirror_router.callback_query(F.data == "check_subscribe")
        async def mirror_check_subscribe(call: CallbackQuery, state: FSMContext, bot: Bot):
            user_id = call.from_user.id
            
            if not is_verified(user_id):
                image_bytes, captcha_code = generate_captcha_image()
                captcha_data[user_id] = captcha_code
                await state.update_data(captcha_code=captcha_code)
                await state.set_state(CaptchaStates.waiting_for_captcha)
                try:
                    await call.message.delete()
                except:
                    pass
                await call.message.answer_photo(
                    photo=BufferedInputFile(file=image_bytes, filename="captcha.png"),
                    caption="🔐 <b>ПОДТВЕРЖДЕНИЕ (ШАГ 1/2)</b>\n\n"
                            "Сначала пройдите верификацию.\n"
                            "Введите код с картинки:"
                )
                await safe_answer(call, get_text(user_id, "verification_required"), show_alert=True)
                return
            
            try:
                member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
                is_subscribed = member.status not in ["left", "kicked"]
            except:
                is_subscribed = False
            
            if is_subscribed:
                if not has_received_subscribe_bonus(user_id):
                    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (SUBSCRIBE_BONUS, user_id))
                    mark_subscribe_bonus_received(user_id)
                    conn.commit()
                    await safe_answer(call, get_text(user_id, "bonus_received").format(SUBSCRIBE_BONUS), show_alert=True)
                
                await safe_answer(call, "✅ Спасибо за подписку!", show_alert=True)
                await state.set_state(None)
                try:
                    await call.message.delete()
                except:
                    pass
                
                has_access, _, is_main, can_manage = check_admin_access(user_id)
                if has_access:
                    await call.message.answer("👑 Админ-панель", reply_markup=get_admin_menu(is_main, can_manage))
                else:
                    from keyboards import get_main_menu
                    await call.message.answer(get_text(user_id, "welcome"), reply_markup=get_main_menu(user_id))
            else:
                await safe_answer(call, "❌ Вы не подписались на канал! Подпишитесь и нажмите кнопку снова.", show_alert=True)
        
        # ========== ХЭНДЛЕРЫ ДЛЯ КАПЧИ ==========
        @mirror_router.message(CaptchaStates.waiting_for_captcha)
        async def mirror_process_captcha(message: Message, state: FSMContext, bot: Bot):
            user_id = message.from_user.id
            user_input = message.text.strip().upper()
            
            if user_id in banned_users:
                ban_until = banned_users[user_id]
                if datetime.now() < ban_until:
                    remaining = ban_until - datetime.now()
                    minutes = remaining.seconds // 60
                    seconds = remaining.seconds % 60
                    await message.answer(
                        f"🚫 <b>ДОСТУП ЗАБЛОКИРОВАН</b>\n\n"
                        f"⏳ Осталось: {minutes} мин {seconds} сек"
                    )
                    await state.clear()
                    return
                else:
                    del banned_users[user_id]
            
            data = await state.get_data()
            correct_code = data.get('captcha_code') or captcha_data.get(user_id)
            
            if not correct_code:
                await message.answer("❌ Ошибка верификации. Нажми /start заново")
                await state.clear()
                return
            
            if user_input == correct_code:
                if user_id in captcha_data:
                    del captcha_data[user_id]
                if user_id in captcha_attempts:
                    del captcha_attempts[user_id]
                
                math_text, math_answer = generate_math_captcha()
                math_captcha_data[user_id] = math_answer
                await state.update_data(math_answer=math_answer)
                await state.set_state(MathCaptchaStates.waiting_for_math_captcha)
                
                await message.answer(
                    f"✅ <b>Первый шаг пройден!</b>\n\n"
                    f"🔢 <b>МАТЕМАТИЧЕСКАЯ ПРОВЕРКА (ШАГ 2/2)</b>\n\n"
                    f"Решите пример:\n"
                    f"<b>{math_text}</b>\n\n"
                    f"Введите только число:\n"
                    f"📊 Осталось попыток: 3/3"
                )
            else:
                attempts = captcha_attempts.get(user_id, 0) + 1
                captcha_attempts[user_id] = attempts
                if attempts >= 3:
                    from datetime import timedelta
                    ban_time = datetime.now() + timedelta(minutes=10)
                    banned_users[user_id] = ban_time
                    if user_id in captcha_data:
                        del captcha_data[user_id]
                    if user_id in captcha_attempts:
                        del captcha_attempts[user_id]
                    await state.clear()
                    await message.answer(
                        f"🚫 <b>ДОСТУП ЗАБЛОКИРОВАН</b>\n\n"
                        f"❌ Вы исчерпали все попытки (3/3)\n"
                        f"⏳ Блокировка на 10 минут"
                    )
                    return
                image_bytes, new_code = generate_captcha_image()
                captcha_data[user_id] = new_code
                await state.update_data(captcha_code=new_code)
                remaining_attempts = 3 - attempts
                await message.answer_photo(
                    photo=BufferedInputFile(file=image_bytes, filename="captcha.png"),
                    caption=f"❌ <b>НЕПРАВИЛЬНЫЙ КОД!</b>\n\n"
                            f"Попробуйте еще раз:\n"
                            f"⚠️ Только заглавные буквы и цифры\n"
                            f"📊 Осталось попыток: {remaining_attempts}/3"
                )
        
        @mirror_router.message(MathCaptchaStates.waiting_for_math_captcha)
        async def mirror_process_math_captcha(message: Message, state: FSMContext, bot: Bot):
            user_id = message.from_user.id
            user_input = message.text.strip()
            
            if user_id in banned_users:
                ban_until = banned_users[user_id]
                if datetime.now() < ban_until:
                    remaining = ban_until - datetime.now()
                    minutes = remaining.seconds // 60
                    seconds = remaining.seconds % 60
                    await message.answer(
                        f"🚫 <b>ДОСТУП ЗАБЛОКИРОВАН</b>\n\n"
                        f"⏳ Осталось: {minutes} мин {seconds} сек"
                    )
                    await state.clear()
                    return
                else:
                    del banned_users[user_id]
            
            data = await state.get_data()
            correct_answer = data.get('math_answer') or math_captcha_data.get(user_id)
            
            if correct_answer is None:
                await message.answer("❌ Ошибка верификации. Нажми /start заново")
                await state.clear()
                return
            
            try:
                user_answer = int(user_input)
            except ValueError:
                user_answer = None
            
            if user_answer == correct_answer:
                if user_id in math_captcha_data:
                    del math_captcha_data[user_id]
                if user_id in math_captcha_attempts:
                    del math_captcha_attempts[user_id]
                
                cursor.execute("UPDATE users SET is_verified = 1 WHERE user_id = ?", (user_id,))
                conn.commit()
                await state.clear()
                
                await message.answer(
                    f"🎉 <b>ВЕРИФИКАЦИЯ ПРОЙДЕНА!</b>\n\n"
                    f"✅ Вы успешно прошли обе проверки!"
                )
                
                try:
                    member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
                    is_subscribed = member.status not in ["left", "kicked"]
                except:
                    is_subscribed = False
                
                if not is_subscribed:
                    await state.set_state(SubscribeStates.waiting_for_subscribe)
                    await message.answer(
                        get_text(user_id, "subscribe_required").format(SUBSCRIBE_BONUS),
                        reply_markup=subscribe_menu
                    )
                else:
                    from keyboards import get_main_menu
                    await message.answer(
                        get_text(user_id, "welcome"),
                        reply_markup=get_main_menu(user_id)
                    )
            else:
                attempts = math_captcha_attempts.get(user_id, 0) + 1
                math_captcha_attempts[user_id] = attempts
                
                if attempts >= 3:
                    from datetime import timedelta
                    ban_time = datetime.now() + timedelta(minutes=10)
                    banned_users[user_id] = ban_time
                    if user_id in math_captcha_data:
                        del math_captcha_data[user_id]
                    if user_id in math_captcha_attempts:
                        del math_captcha_attempts[user_id]
                    await state.clear()
                    await message.answer(
                        f"🚫 <b>ДОСТУП ЗАБЛОКИРОВАН</b>\n\n"
                        f"❌ Вы исчерпали все попытки (3/3)\n"
                        f"⏳ Блокировка на 10 минут"
                    )
                    return
                
                math_text, math_answer = generate_math_captcha()
                math_captcha_data[user_id] = math_answer
                await state.update_data(math_answer=math_answer)
                remaining_attempts = 3 - attempts
                
                await message.answer(
                    f"❌ <b>НЕПРАВИЛЬНЫЙ ОТВЕТ!</b>\n\n"
                    f"Попробуйте еще раз:\n"
                    f"<b>{math_text}</b>\n\n"
                    f"Введите только число:\n"
                    f"📊 Осталось попыток: {remaining_attempts}/3"
                )
        
        # ========== КОПИРУЕМ ОСТАЛЬНЫЕ ХЭНДЛЕРЫ ==========
        mirror_router.callback_query(F.data == "videos")(videos)
        mirror_router.callback_query(F.data == "shop")(shop)
        mirror_router.callback_query(F.data == "profile")(profile)
        mirror_router.callback_query(F.data == "battlepass_menu")(battlepass_menu)
        mirror_router.callback_query(F.data == "bonus")(bonus)
        mirror_router.callback_query(F.data == "promo")(promo)
        mirror_router.callback_query(F.data == "tasks")(tasks_menu)
        mirror_router.callback_query(F.data == "suggestion")(suggestion_start)
        mirror_router.callback_query(F.data == "support")(support_start)
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
        mirror_router.callback_query(F.data == "menu_back")(back_to_menu)
        
        # Админские хэндлеры
        mirror_router.callback_query(F.data == "admin_panel")(admin_panel)
        mirror_router.callback_query(F.data == "admin_stats")(admin_stats)
        mirror_router.callback_query(F.data == "admin_broadcast")(admin_broadcast)
        mirror_router.callback_query(F.data == "admin_add_balance")(admin_add_balance)
        mirror_router.callback_query(F.data == "admin_remove_balance")(admin_remove_balance)
        mirror_router.callback_query(F.data == "admin_add_promo")(admin_add_promo)
        mirror_router.callback_query(F.data == "admin_op")(admin_op_menu)
        mirror_router.callback_query(F.data == "admin_manage")(admin_manage_menu_callback)
        mirror_router.callback_query(F.data == "admin_tasks")(admin_tasks_menu_handler)
        mirror_router.callback_query(F.data == "admin_auto_tasks")(admin_auto_tasks_menu)
        
        # Блокировка пересылки
        @mirror_router.message(F.forward_from | F.forward_from_chat)
        async def mirror_block_forward(message: Message):
            await message.delete()
        
        # Хэндлер для видео (предложка)
        @mirror_router.message(F.video)
        async def mirror_handle_video(message: Message, bot: Bot):
            user_id = message.from_user.id
            has_access, _, _, _ = check_admin_access(user_id)
            if has_access:
                await upload_video(message)
            else:
                await handle_suggestion_video(message, bot)
        
        dp.include_router(mirror_router)
        
        # Блокировка пересылки на уровне диспетчера
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
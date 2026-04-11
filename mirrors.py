import os
import json
import sqlite3
import asyncio
import logging
import random
import string
from datetime import datetime
from typing import List, Dict, Optional

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession

logger = logging.getLogger(__name__)

# Хранилище активных ботов-зеркал
active_mirror_bots = {}
active_mirror_dispatchers = {}


# ================= СОСТОЯНИЯ ДЛЯ СОЗДАНИЯ ЗЕРКАЛА =================
class MirrorStates(StatesGroup):
    waiting_for_token = State()
    waiting_for_confirmation = State()


def init_mirrors_table():
    """Инициализировать таблицу для зеркал"""
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
        
        # Проверяем наличие колонок
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


def generate_mirror_code(length=8):
    """Сгенерировать уникальный код для зеркала"""
    chars = string.ascii_uppercase + string.digits
    chars = chars.replace('O', '').replace('0', '').replace('I', '').replace('1', '')
    while True:
        code = ''.join(random.choices(chars, k=length))
        from db import cursor
        cursor.execute("SELECT id FROM mirror_bots WHERE mirror_code = ?", (code,))
        if not cursor.fetchone():
            return code


def get_main_bot_token() -> Optional[str]:
    """Получить токен главного бота"""
    try:
        from db import cursor
        cursor.execute("SELECT bot_token FROM mirror_bots WHERE is_main = 1 AND is_active = 1 LIMIT 1")
        row = cursor.fetchone()
        return row["bot_token"] if row else None
    except Exception as e:
        print(f"❌ Ошибка get_main_bot_token: {e}")
        return None


def get_main_bot_info() -> Optional[Dict]:
    """Получить информацию о главном боте"""
    try:
        from db import cursor
        cursor.execute("SELECT * FROM mirror_bots WHERE is_main = 1 LIMIT 1")
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None


def set_main_bot(token: str, username: str = "", added_by: int = None) -> bool:
    """Установить главного бота"""
    try:
        from db import cursor, conn
        
        # Снимаем флаг is_main со всех
        cursor.execute("UPDATE mirror_bots SET is_main = 0")
        
        # Проверяем, существует ли уже такой токен
        cursor.execute("SELECT id FROM mirror_bots WHERE bot_token = ?", (token,))
        existing = cursor.fetchone()
        
        if existing:
            cursor.execute("UPDATE mirror_bots SET is_main = 1, bot_username = ?, is_active = 1 WHERE bot_token = ?", 
                          (username, token))
        else:
            mirror_code = generate_mirror_code()
            cursor.execute("""
                INSERT INTO mirror_bots (bot_token, bot_username, is_active, is_main, added_by, added_at, mirror_code)
                VALUES (?, ?, 1, 1, ?, ?, ?)
            """, (token, username, added_by, datetime.now(), mirror_code))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка set_main_bot: {e}")
        return False


def add_mirror_bot(token: str, username: str, added_by: int, notes: str = "") -> bool:
    """Добавить бота-зеркало"""
    try:
        from db import cursor, conn
        
        # Проверяем, не существует ли уже
        cursor.execute("SELECT id FROM mirror_bots WHERE bot_token = ?", (token,))
        if cursor.fetchone():
            return False
        
        mirror_code = generate_mirror_code()
        cursor.execute("""
            INSERT INTO mirror_bots (bot_token, bot_username, is_active, added_by, added_at, notes, is_main, mirror_code)
            VALUES (?, ?, 1, ?, ?, ?, 0, ?)
        """, (token, username, added_by, datetime.now(), notes, mirror_code))
        conn.commit()
        return True
    except Exception as e:
        print(f"❌ Ошибка add_mirror_bot: {e}")
        return False


def add_mirror_bot_by_user(token: str, username: str, user_id: int) -> tuple:
    """Добавить бота-зеркало от обычного пользователя"""
    try:
        from db import cursor, conn
        
        # Проверяем, не существует ли уже
        cursor.execute("SELECT id FROM mirror_bots WHERE bot_token = ?", (token,))
        if cursor.fetchone():
            return False, "❌ Этот бот уже зарегистрирован как зеркало!"
        
        # Проверяем, не пытается ли пользователь создать слишком много зеркал
        cursor.execute("SELECT COUNT(*) as count FROM mirror_bots WHERE added_by = ? AND is_main = 0", (user_id,))
        count = cursor.fetchone()["count"]
        if count >= 3:
            return False, "❌ Вы можете создать не более 3 зеркал!"
        
        mirror_code = generate_mirror_code()
        cursor.execute("""
            INSERT INTO mirror_bots (bot_token, bot_username, is_active, added_by, added_at, notes, is_main, mirror_code)
            VALUES (?, ?, 1, ?, ?, ?, 0, ?)
        """, (token, username, user_id, datetime.now(), f"Создано пользователем {user_id}", mirror_code))
        conn.commit()
        
        # Получаем ID созданного зеркала
        cursor.execute("SELECT id FROM mirror_bots WHERE bot_token = ?", (token,))
        row = cursor.fetchone()
        
        return True, row["id"] if row else None
    except Exception as e:
        print(f"❌ Ошибка add_mirror_bot_by_user: {e}")
        return False, f"❌ Ошибка: {e}"


def remove_mirror_bot(bot_id: int) -> bool:
    """Удалить бота-зеркало"""
    try:
        from db import cursor, conn
        cursor.execute("DELETE FROM mirror_bots WHERE id = ? AND is_main = 0", (bot_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"❌ Ошибка remove_mirror_bot: {e}")
        return False


def remove_mirror_bot_by_token(token: str) -> bool:
    """Удалить бота-зеркало по токену"""
    try:
        from db import cursor, conn
        cursor.execute("DELETE FROM mirror_bots WHERE bot_token = ? AND is_main = 0", (token,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"❌ Ошибка remove_mirror_bot_by_token: {e}")
        return False


def remove_mirror_bot_by_user(bot_id: int, user_id: int) -> bool:
    """Удалить зеркало, созданное пользователем"""
    try:
        from db import cursor, conn
        cursor.execute("DELETE FROM mirror_bots WHERE id = ? AND added_by = ? AND is_main = 0", (bot_id, user_id))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"❌ Ошибка remove_mirror_bot_by_user: {e}")
        return False


def toggle_mirror_bot(bot_id: int, is_active: bool) -> bool:
    """Включить/выключить бота-зеркало"""
    try:
        from db import cursor, conn
        cursor.execute("UPDATE mirror_bots SET is_active = ? WHERE id = ? AND is_main = 0", 
                      (1 if is_active else 0, bot_id))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"❌ Ошибка toggle_mirror_bot: {e}")
        return False


def get_all_mirror_bots(include_main: bool = False) -> List[Dict]:
    """Получить список всех зеркал"""
    try:
        from db import cursor
        if include_main:
            cursor.execute("SELECT * FROM mirror_bots ORDER BY is_main DESC, id ASC")
        else:
            cursor.execute("SELECT * FROM mirror_bots WHERE is_main = 0 ORDER BY id ASC")
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def get_active_mirror_bots(include_main: bool = False) -> List[Dict]:
    """Получить список активных зеркал"""
    try:
        from db import cursor
        if include_main:
            cursor.execute("SELECT * FROM mirror_bots WHERE is_active = 1 ORDER BY is_main DESC, id ASC")
        else:
            cursor.execute("SELECT * FROM mirror_bots WHERE is_active = 1 AND is_main = 0 ORDER BY id ASC")
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def get_user_mirror_bots(user_id: int) -> List[Dict]:
    """Получить список зеркал, созданных пользователем"""
    try:
        from db import cursor
        cursor.execute("SELECT * FROM mirror_bots WHERE added_by = ? AND is_main = 0 ORDER BY id ASC", (user_id,))
        return [dict(row) for row in cursor.fetchall()]
    except:
        return []


def get_mirror_bot_by_id(bot_id: int) -> Optional[Dict]:
    """Получить зеркало по ID"""
    try:
        from db import cursor
        cursor.execute("SELECT * FROM mirror_bots WHERE id = ?", (bot_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None


def get_mirror_bot_by_token(token: str) -> Optional[Dict]:
    """Получить зеркало по токену"""
    try:
        from db import cursor
        cursor.execute("SELECT * FROM mirror_bots WHERE bot_token = ?", (token,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None


def get_mirror_bot_by_code(code: str) -> Optional[Dict]:
    """Получить зеркало по коду"""
    try:
        from db import cursor
        cursor.execute("SELECT * FROM mirror_bots WHERE mirror_code = ?", (code,))
        row = cursor.fetchone()
        return dict(row) if row else None
    except:
        return None


def update_mirror_health(bot_id: int, status: bool = True):
    """Обновить статус проверки здоровья зеркала"""
    try:
        from db import cursor, conn
        cursor.execute("UPDATE mirror_bots SET last_health_check = ?, is_active = ? WHERE id = ?", 
                      (datetime.now(), 1 if status else 0, bot_id))
        conn.commit()
    except:
        pass


def update_mirror_username(bot_id: int, username: str) -> bool:
    """Обновить username зеркала"""
    try:
        from db import cursor, conn
        cursor.execute("UPDATE mirror_bots SET bot_username = ? WHERE id = ?", (username, bot_id))
        conn.commit()
        return True
    except:
        return False


def update_mirror_notes(bot_id: int, notes: str) -> bool:
    """Обновить заметки зеркала"""
    try:
        from db import cursor, conn
        cursor.execute("UPDATE mirror_bots SET notes = ? WHERE id = ?", (notes, bot_id))
        conn.commit()
        return True
    except:
        return False


def is_mirror_owner(user_id: int, bot_token: str) -> bool:
    """Проверить, является ли пользователь владельцем зеркала"""
    try:
        from db import cursor
        cursor.execute("SELECT id FROM mirror_bots WHERE bot_token = ? AND added_by = ? AND is_main = 0", 
                      (bot_token, user_id))
        return cursor.fetchone() is not None
    except:
        return False


async def create_bot_instance(token: str, username: str = "", is_mirror: bool = True):
    """Создать экземпляр бота для зеркала"""
    try:
        session = AiohttpSession(timeout=60)
        
        bot = Bot(
            token=token,
            session=session,
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML,
                protect_content=True
            )
        )
        
        # Проверяем, что бот работает
        me = await bot.get_me()
        logger.info(f"✅ Зеркало @{me.username} (ID: {me.id}) запущено")
        
        return bot, me
    except Exception as e:
        logger.error(f"❌ Ошибка создания зеркала @{username}: {e}")
        return None, None


async def start_mirror_bot(token: str, username: str = "", dp_main=None):
    """Запустить отдельного бота-зеркало с полным функционалом"""
    try:
        from handlers import get_main_router_for_mirror
        
        bot, me = await create_bot_instance(token, username, is_mirror=True)
        if not bot or not me:
            return None
        
        # Обновляем username в БД
        if me.username:
            update_mirror_username(get_mirror_bot_by_token(token)["id"], me.username)
        
        # Создаем диспетчер для зеркала
        from aiogram.fsm.storage.memory import MemoryStorage
        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        
        # Подключаем роутер для зеркала (без админ-функций)
        router = get_main_router_for_mirror()
        dp.include_router(router)
        
        # Блокировка пересылки
        @dp.message(F.forward_from | F.forward_from_chat)
        async def block_forward(message: Message):
            await message.delete()
        
        active_mirror_bots[token] = bot
        active_mirror_dispatchers[token] = dp
        
        # Запускаем polling в отдельной задаче
        asyncio.create_task(dp.start_polling(bot))
        
        logger.info(f"✅ Зеркало @{me.username} полностью запущено")
        return bot
        
    except Exception as e:
        logger.error(f"❌ Ошибка запуска зеркала @{username}: {e}")
        return None


async def stop_mirror_bot(token: str):
    """Остановить бота-зеркало"""
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


async def start_all_mirror_bots(dp_main=None):
    """Запустить все активные зеркала"""
    from db import init_db
    init_db()
    init_mirrors_table()
    
    mirrors = get_active_mirror_bots(include_main=False)
    logger.info(f"🔄 Запуск {len(mirrors)} зеркал...")
    
    for mirror in mirrors:
        await start_mirror_bot(mirror["bot_token"], mirror.get("bot_username", ""), dp_main)
    
    logger.info(f"✅ Запущено {len(active_mirror_bots)} зеркал")


async def stop_all_mirror_bots():
    """Остановить все зеркала"""
    for token in list(active_mirror_bots.keys()):
        await stop_mirror_bot(token)


# ================= ФУНКЦИИ ДЛЯ КЛАВИАТУР ПОЛЬЗОВАТЕЛЯ =================
def get_mirror_menu(user_id: int = None):
    """Получить меню управления зеркалами для пользователя"""
    from locales import get_text
    if user_id is None:
        user_id = 0
    
    keyboard = [
        [InlineKeyboardButton(text="➕ Создать зеркало", callback_data="mirror_create")],
        [InlineKeyboardButton(text="📋 Мои зеркала", callback_data="mirror_my_list")],
        [InlineKeyboardButton(text="ℹ️ Что такое зеркало?", callback_data="mirror_info")],
        [InlineKeyboardButton(text=get_text(user_id, "back_to_menu"), callback_data="menu")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_my_mirrors_keyboard(mirrors: List[Dict], user_id: int = None):
    """Клавиатура со списком зеркал пользователя"""
    from locales import get_text
    if user_id is None:
        user_id = 0
    
    keyboard = []
    for mirror in mirrors:
        status = "✅" if mirror["is_active"] else "❌"
        keyboard.append([InlineKeyboardButton(
            text=f"{status} @{mirror['bot_username'] or 'без юзернейма'}",
            callback_data=f"mirror_details_{mirror['id']}"
        )])
    
    keyboard.append([InlineKeyboardButton(text="➕ Создать новое зеркало", callback_data="mirror_create")])
    keyboard.append([InlineKeyboardButton(text=get_text(user_id, "back"), callback_data="mirror_menu")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_mirror_details_keyboard(mirror: Dict, user_id: int = None):
    """Клавиатура для деталей зеркала"""
    from locales import get_text
    if user_id is None:
        user_id = 0
    
    keyboard = []
    
    if mirror["is_active"]:
        keyboard.append([InlineKeyboardButton(text="🔄 Перезапустить зеркало", callback_data=f"mirror_restart_{mirror['id']}")])
        keyboard.append([InlineKeyboardButton(text="⏸ Остановить зеркало", callback_data=f"mirror_stop_{mirror['id']}")])
    else:
        keyboard.append([InlineKeyboardButton(text="▶️ Запустить зеркало", callback_data=f"mirror_start_{mirror['id']}")])
    
    keyboard.append([InlineKeyboardButton(text="🗑 Удалить зеркало", callback_data=f"mirror_delete_{mirror['id']}")])
    keyboard.append([InlineKeyboardButton(text=get_text(user_id, "back"), callback_data="mirror_my_list")])
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_mirror_info_text() -> str:
    """Текст с информацией о зеркалах"""
    return (
        "🪞 <b>ЧТО ТАКОЕ БОТ-ЗЕРКАЛО?</b>\n\n"
        "Бот-зеркало — это точная копия нашего основного бота, но со своим токеном.\n\n"
        "<b>Зачем это нужно?</b>\n"
        "• Если основной бот заблокируют — вы продолжите пользоваться зеркалом\n"
        "• Вы можете приглашать друзей через своё зеркало\n"
        "• Все данные синхронизируются между всеми зеркалами\n"
        "• Ваш баланс и прогресс сохраняются\n\n"
        "<b>Как создать зеркало?</b>\n"
        "1. Создайте нового бота через @BotFather\n"
        "2. Скопируйте токен бота\n"
        "3. Нажмите «Создать зеркало» и вставьте токен\n"
        "4. Готово! Ваше зеркало запущено\n\n"
        "<b>Важно!</b>\n"
        "• Вы можете создать до 3 зеркал\n"
        "• Не передавайте токен бота никому\n"
        "• Зеркало не имеет админ-функций"
    )


def get_mirror_create_instruction() -> str:
    """Инструкция по созданию зеркала"""
    return (
        "🪞 <b>СОЗДАНИЕ БОТА-ЗЕРКАЛА</b>\n\n"
        "1️⃣ <b>Создайте нового бота</b>\n"
        "   • Напишите @BotFather в Telegram\n"
        "   • Отправьте команду /newbot\n"
        "   • Придумайте имя и username для бота\n"
        "   • Скопируйте полученный токен\n\n"
        "2️⃣ <b>Отправьте токен сюда</b>\n"
        "   • Токен выглядит так: <code>1234567890:ABCdefGHIjklMNOpqrsTUVwxyz</code>\n"
        "   • Просто вставьте его в ответ на это сообщение\n\n"
        "3️⃣ <b>Готово!</b>\n"
        "   • Бот автоматически запустится\n"
        "   • Вы можете приглашать друзей через своего бота\n"
        "   • Все данные будут синхронизированы\n\n"
        "⚠️ <b>Важно!</b>\n"
        "• Никому не передавайте токен бота\n"
        "• Вы можете создать не более 3 зеркал"
    )


# Инициализация при загрузке
init_mirrors_table()

print("✅ mirrors.py загружен")
import asyncio
import os
import random
import sqlite3
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton
)
from aiogram.filters import CommandStart, Command

# ================== CONFIG ==================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

VIDEO_PRICE = 1
BONUS_AMOUNT = 3
BONUS_COOLDOWN = 3600  # 1 час
REF_REWARD = 3

RESERVE_CHANNEL = "https://t.me/your_channel"
BUY_CONTACT = "@balikcyda"

# ================== DB ==================

conn = sqlite3.connect("db.sqlite3")
cursor = conn.cursor()

cursor.executescript("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    balance INTEGER DEFAULT 0,
    referrer_id INTEGER,
    joined INTEGER
);

CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT UNIQUE
);

CREATE TABLE IF NOT EXISTS user_videos (
    user_id INTEGER,
    video_id INTEGER,
    UNIQUE(user_id, video_id)
);

CREATE TABLE IF NOT EXISTS bonuses (
    user_id INTEGER PRIMARY KEY,
    last_claim INTEGER
);
""")
conn.commit()

# ================== DB HELPERS ==================

def add_user(uid, username, ref=None):
    cursor.execute(
        "INSERT OR IGNORE INTO users VALUES (?,?,?,?,?)",
        (uid, username, 0, ref, int(datetime.utcnow().timestamp()))
    )
    conn.commit()

def get_user(uid):
    return cursor.execute(
        "SELECT * FROM users WHERE user_id=?", (uid,)
    ).fetchone()

def has_access(uid):
    row = cursor.execute(
        "SELECT referrer_id FROM users WHERE user_id=?", (uid,)
    ).fetchone()
    return row and row[0] is not None

def add_balance(uid, amount):
    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id=?",
        (amount, uid)
    )
    conn.commit()

def get_balance(uid):
    row = cursor.execute(
        "SELECT balance FROM users WHERE user_id=?", (uid,)
    ).fetchone()
    return row[0] if row else 0

# ================== KEYBOARDS ==================

def fake_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("📥 Скачать видео с YouTube", callback_data="fake_youtube")],
        [InlineKeyboardButton("💱 Узнать курс валют", callback_data="fake_rate")],
        [InlineKeyboardButton("🎲 Сыграть в кости", callback_data="fake_dice")]
    ])

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("🎬 Смотреть видео", callback_data="get_video")],
        [InlineKeyboardButton("🍬 Шоп конфет", callback_data="shop")],
        [InlineKeyboardButton("👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton("🎁 Бонус", callback_data="bonus")],
        [InlineKeyboardButton("📢 Резервный канал", url=RESERVE_CHANNEL)]
    ])

def shop_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("💳 Пополнить баланс", callback_data="topup")]
    ])

# ================== ROUTER ==================

router = Router()

# ---------- START ----------

@router.message(CommandStart())
async def start(message: Message):
    args = message.text.split()
    ref = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    add_user(
        message.from_user.id,
        message.from_user.username,
        ref
    )

    if ref and ref != message.from_user.id:
        add_balance(ref, REF_REWARD)

    if not has_access(message.from_user.id):
        await message.answer(
            "⛔ Доступ только по реферальной ссылке",
            reply_markup=fake_menu()
        )
    else:
        await message.answer(
            "✅ Добро пожаловать",
            reply_markup=main_menu()
        )

# ---------- FAKE MENU ----------

@router.callback_query(F.data.startswith("fake"))
async def fake(call: CallbackQuery):
    if call.data == "fake_youtube":
        await call.answer("❌ Ошибка загрузки", show_alert=True)
    elif call.data == "fake_rate":
        await call.answer(
            f"Курс: {random.randint(50,150)}",
            show_alert=True
        )
    else:
        await call.answer(
            f"🎲 Выпало {random.randint(1,6)}",
            show_alert=True
        )

# ---------- PROFILE ----------

@router.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    uid = call.from_user.id
    bal = get_balance(uid)
    bot = call.bot
    ref_link = f"https://t.me/{(await bot.me()).username}?start={uid}"

    await call.message.answer(
        f"👤 Профиль\n\n"
        f"🍬 Баланс: {bal}\n\n"
        f"🔗 Реферальная ссылка:\n{ref_link}"
    )

# ---------- BONUS ----------

@router.callback_query(F.data == "bonus")
async def bonus(call: CallbackQuery):
    uid = call.from_user.id
    now = int(datetime.utcnow().timestamp())

    row = cursor.execute(
        "SELECT last_claim FROM bonuses WHERE user_id=?",
        (uid,)
    ).fetchone()

    if row and now - row[0] < BONUS_COOLDOWN:
        await call.answer("⏳ Бонус уже был", show_alert=True)
        return

    cursor.execute(
        "INSERT OR REPLACE INTO bonuses VALUES (?,?)",
        (uid, now)
    )
    add_balance(uid, BONUS_AMOUNT)
    conn.commit()

    await call.answer("🎁 +3 конфеты", show_alert=True)

# ---------- SHOP / PAYMENT ----------

@router.callback_query(F.data == "shop")
async def shop(call: CallbackQuery):
    await call.message.answer(
        "🍬 Шоп конфет",
        reply_markup=shop_menu()
    )

@router.callback_query(F.data == "topup")
async def topup(call: CallbackQuery):
    text = (
        "💳 Пополнение баланса\n\n"
        "Курс:\n"
        "1$ = 299 конфет | 75 ⭐\n\n"
        "Если нужно больше — умножайте сумму на 2\n\n"
        "Оплата принимается:\n"
        "• CryptoBot (крипта)\n"
        "• Telegram Stars\n\n"
        f"Для покупки напишите {BUY_CONTACT}"
    )
    await call.message.answer(text)

    await call.bot.send_message(
        ADMIN_ID,
        f"💰 Запрос на покупку\n"
        f"@{call.from_user.username}\n"
        f"ID: {call.from_user.id}"
    )

# ---------- VIDEO ----------

@router.callback_query(F.data == "get_video")
async def get_video(call: CallbackQuery):
    uid = call.from_user.id
    bal = get_balance(uid)

    if bal < VIDEO_PRICE:
        await call.answer("❌ Недостаточно конфет", show_alert=True)
        return

    video = cursor.execute(
        "SELECT id, file_id FROM videos WHERE id NOT IN "
        "(SELECT video_id FROM user_videos WHERE user_id=?) "
        "ORDER BY RANDOM() LIMIT 1",
        (uid,)
    ).fetchone()

    if not video:
        await call.answer("🎬 Видео закончились", show_alert=True)
        return

    cursor.execute(
        "INSERT INTO user_videos VALUES (?,?)",
        (uid, video[0])
    )
    cursor.execute(
        "UPDATE users SET balance = balance - ? WHERE user_id=?",
        (VIDEO_PRICE, uid)
    )
    conn.commit()

    await call.message.answer_video(video[1])

# ---------- ADMIN ----------

@router.message(Command("add"))
async def admin_add(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    _, uid, amount = message.text.split()
    add_balance(int(uid), int(amount))
    await message.answer("✅ Баланс выдан")

@router.message(Command("addvideo"))
async def admin_add_video(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    if not message.video:
        await message.answer("❌ Пришли видео")
        return

    cursor.execute(
        "INSERT OR IGNORE INTO videos (file_id) VALUES (?)",
        (message.video.file_id,)
    )
    conn.commit()
    await message.answer("🎬 Видео добавлено")

# ================== START BOT ==================

async def main():
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

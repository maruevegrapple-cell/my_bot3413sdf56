import asyncio
import random
import time
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command

# ========== CONFIG ==========
BOT_TOKEN = "8405907915:AAHG8r-Dg0hrucmMe0G3rdQnpUQIXDJJFSc"
BOT_USERNAME = "@CandyBlossom34_bot"
ADMINS = [5925859280]
RESERVE_CHANNEL = "https://t.me/+JZdfikxXx-M0ZDll"
ADMIN_CONTACT = "@balikcyda"

VIDEO_PRICE = 1
BONUS_AMOUNT = 3
BONUS_COOLDOWN = 3600
# ============================

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ========== DATABASE ==========
db = sqlite3.connect("database.db")
sql = db.cursor()

sql.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    joined_by_ref INTEGER DEFAULT 0,
    last_bonus INTEGER DEFAULT 0
)
""")

sql.execute("""
CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT
)
""")

sql.execute("""
CREATE TABLE IF NOT EXISTS watched (
    user_id INTEGER,
    video_id INTEGER,
    UNIQUE(user_id, video_id)
)
""")

db.commit()
# =============================

# ========== KEYBOARDS ==========
fake_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📥 Скачать видео с YouTube", callback_data="fake")],
    [InlineKeyboardButton(text="💱 Узнать курс валют", callback_data="fake")],
    [InlineKeyboardButton(text="🎲 Сыграть в кости", callback_data="fake")]
])

main_menu = InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="📹 Смотреть видео", callback_data="watch")],
    [
        InlineKeyboardButton(text="👤 Профиль", callback_data="profile"),
        InlineKeyboardButton(text="🛒 Шоп конфет", callback_data="shop")
    ],
    [InlineKeyboardButton(text="🎁 Бонус", callback_data="bonus")],
    [InlineKeyboardButton(text="💳 Пополнить баланс", callback_data="topup")],
    [InlineKeyboardButton(text="📢 Резервный канал", url=RESERVE_CHANNEL)]
])
# ==============================

@dp.message(CommandStart())
async def start(message: Message):
    args = message.text.split()
    ref = int(args[1]) if len(args) > 1 else None

    sql.execute(
        "INSERT OR IGNORE INTO users (user_id, joined_by_ref) VALUES (?, ?)",
        (message.from_user.id, 1 if ref else 0)
    )
    db.commit()

    if ref:
        sql.execute("UPDATE users SET balance = balance + 3 WHERE user_id=?", (ref,))
        db.commit()
        await message.answer("✅ Доступ открыт", reply_markup=main_menu)
    else:
        await message.answer("❌ Доступ ограничен", reply_markup=fake_menu)

@dp.callback_query(F.data == "fake")
async def fake(call: CallbackQuery):
    await call.answer(random.choice([
        "Ошибка загрузки ❌",
        f"Курс USD: {random.randint(50,150)}",
        f"🎲 Выпало: {random.randint(1,6)}"
    ]), show_alert=True)

@dp.callback_query(F.data == "watch")
async def watch(call: CallbackQuery):
    sql.execute("SELECT balance FROM users WHERE user_id=?", (call.from_user.id,))
    balance = sql.fetchone()[0]

    if balance < VIDEO_PRICE:
        await call.answer("❌ Недостаточно конфет", show_alert=True)
        return

    sql.execute("""
    SELECT id, file_id FROM videos
    WHERE id NOT IN (
        SELECT video_id FROM watched WHERE user_id=?
    )
    ORDER BY RANDOM() LIMIT 1
    """, (call.from_user.id,))
    video = sql.fetchone()

    if not video:
        await call.answer("Видео закончились", show_alert=True)
        return

    sql.execute("UPDATE users SET balance = balance - 1 WHERE user_id=?", (call.from_user.id,))
    sql.execute("INSERT INTO watched VALUES (?, ?)", (call.from_user.id, video[0]))
    db.commit()

    await call.message.answer_video(video[1])

@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    sql.execute("SELECT balance FROM users WHERE user_id=?", (call.from_user.id,))
    balance = sql.fetchone()[0]

    ref_link = f"https://t.me/{BOT_USERNAME}?start={call.from_user.id}"

    await call.message.answer(
        f"👤 Профиль\n\n"
        f"ID: {call.from_user.id}\n"
        f"Баланс: {balance} 🍬\n\n"
        f"Реферальная ссылка:\n{ref_link}\n\n"
        f"+3 🍬 за каждого"
    )

@dp.callback_query(F.data == "shop")
async def shop(call: CallbackQuery):
    await call.message.answer(
        "🛒 Шоп конфет\n\n1 конфета = 1 видео"
    )

@dp.callback_query(F.data == "bonus")
async def bonus(call: CallbackQuery):
    sql.execute("SELECT last_bonus FROM users WHERE user_id=?", (call.from_user.id,))
    last = sql.fetchone()[0]

    if time.time() - last < BONUS_COOLDOWN:
        await call.answer("⏳ Бонус уже был", show_alert=True)
        return

    sql.execute("UPDATE users SET balance = balance + 3, last_bonus=? WHERE user_id=?",
                (int(time.time()), call.from_user.id))
    db.commit()

    await call.answer("🎁 +3 конфеты", show_alert=True)

@dp.callback_query(F.data == "topup")
async def topup(call: CallbackQuery):
    await call.message.answer(
        "💰 Курс:\n"
        "1$ = 299 конфет | 75 ⭐\n\n"
        "Оплата:\n"
        "• CryptoBot\n"
        "• Telegram Stars\n\n"
        f"Пишите: {ADMIN_CONTACT}"
    )

    for admin in ADMINS:
        await bot.send_message(
            admin,
            f"💳 Запрос на покупку\n"
            f"@{call.from_user.username}\n"
            f"ID: {call.from_user.id}"
        )

@dp.message(F.video)
async def save_video(message: Message):
    if message.from_user.id not in ADMINS:
        return
    sql.execute("INSERT INTO videos (file_id) VALUES (?)", (message.video.file_id,))
    db.commit()
    await message.answer("✅ Видео добавлено")

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import random
import time
import sqlite3
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from aiogram.filters import CommandStart, Command
from aiogram.exceptions import TelegramForbiddenError

# ================= CONFIG =================
BOT_TOKEN = "8405907915:AAHG8r-Dg0hrucmMe0G3rdQnpUQIXDJJFSc"
BOT_USERNAME = "@CandyBlossom34_bot"
ADMINS = [5925859280]
ADMIN_CONTACT = "@balikcyda"
RESERVE_CHANNEL = "https://t.me/+JZdfikxXx-M0ZDll"

VIDEO_PRICE = 1
BONUS_AMOUNT = 3
BONUS_COOLDOWN = 3600
# ==========================================

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# ================= DATABASE =================
db = sqlite3.connect("database.db")
sql = db.cursor()

sql.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    balance INTEGER DEFAULT 0,
    is_verified INTEGER DEFAULT 0,
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

sql.execute("""
CREATE TABLE IF NOT EXISTS promo (
    code TEXT PRIMARY KEY,
    amount INTEGER
)
""")

db.commit()

# ================= KEYBOARDS =================
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎥 Смотреть видео", callback_data="watch")],
        [InlineKeyboardButton(text="🍬 Шоп конфет", callback_data="shop")],
        [InlineKeyboardButton(text="🎁 Бонус", callback_data="bonus")],
        [InlineKeyboardButton(text="🎟 Промокод", callback_data="promo")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="📢 Резервный канал", url=RESERVE_CHANNEL)]
    ])

def fake_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Скачать видео с YouTube", callback_data="fake_youtube")],
        [InlineKeyboardButton(text="💱 Узнать курс валют", callback_data="fake_rate")],
        [InlineKeyboardButton(text="🎲 Поиграть в кости", callback_data="fake_dice")]
    ])

# ================= UTIL =================
def get_user(user_id):
    sql.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    db.commit()

def is_verified(user_id):
    sql.execute("SELECT is_verified FROM users WHERE user_id=?", (user_id,))
    return sql.fetchone()[0] == 1

def set_verified(user_id):
    sql.execute("UPDATE users SET is_verified=1 WHERE user_id=?", (user_id,))
    db.commit()

# ================= START =================
@dp.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id
    get_user(user_id)

    if user_id in ADMINS:
        await message.answer("👑 Админ-доступ", reply_markup=main_menu())
        return

    args = message.text.split()
    if len(args) > 1:
        set_verified(user_id)

    if is_verified(user_id):
        await message.answer("Добро пожаловать!", reply_markup=main_menu())
    else:
        await message.answer("❌ Доступ ограничен", reply_markup=fake_menu())

# ================= FAKE =================
@dp.callback_query(F.data.startswith("fake_"))
async def fake(callback: CallbackQuery):
    if callback.data == "fake_youtube":
        await callback.answer("Ошибка ❌", show_alert=True)
    elif callback.data == "fake_rate":
        await callback.answer(f"Курс: {random.randint(60,120)}₽", show_alert=True)
    elif callback.data == "fake_dice":
        await callback.answer(f"🎲 {random.randint(1,6)}", show_alert=True)

# ================= SHOP =================
@dp.callback_query(F.data == "shop")
async def shop(callback: CallbackQuery):
    await callback.message.answer(
        "💰 Пополнение баланса\n\n"
        "Курс 1$ = 299 конфет | 75 Звезд Telegram\n"
        "Если вам нужно больше, то умножайте свое число на 2\n\n"
        "Оплата принимается:\n"
        "• CryptoBot (Крипта)\n"
        "• Telegram stars\n\n"
        "Для покупки обязательно напишите на этот аккаунт - @balikcyda\n\n"
        "✍️ Введите количество конфет:"
    )

@dp.message(F.text.regexp(r"^\d+$"))
async def buy_amount(message: Message):
    amount = int(message.text)
    user = message.from_user

    for admin in ADMINS:
        try:
            await bot.send_message(
                admin,
                f"🍬 Заявка\n"
                f"👤 @{user.username or 'без_username'}\n"
                f"🆔 {user.id}\n"
                f"📦 {amount}"
            )
        except TelegramForbiddenError:
            pass

    await message.answer("✅ Заявка отправлена админу")

# ================= PROMO =================
@dp.callback_query(F.data == "promo")
async def promo(callback: CallbackQuery):
    await callback.message.answer("🎟 Введите промокод:")

@dp.message(F.text.len() > 1)
async def activate_promo(message: Message):
    code = message.text.strip()

    sql.execute("SELECT amount FROM promo WHERE code=?", (code,))
    promo = sql.fetchone()
    if not promo:
        return

    amount = promo[0]
    sql.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, message.from_user.id))
    sql.execute("DELETE FROM promo WHERE code=?", (code,))
    db.commit()

    await message.answer(f"🎉 Промокод активирован! +{amount} конфет")

# ================= PROFILE =================
@dp.callback_query(F.data == "profile")
async def profile(callback: CallbackQuery):
    user_id = callback.from_user.id
    sql.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    balance = sql.fetchone()[0]

    ref = f"https://t.me/{BOT_USERNAME}?start={user_id}"

    await callback.message.answer(
        f"👤 Профиль\n\n"
        f"🍬 Баланс: {balance}\n"
        f"🔗 Реферальная ссылка:\n{ref}\n\n"
        f"+3 конфеты за приглашение"
    )

# ================= BONUS =================
@dp.callback_query(F.data == "bonus")
async def bonus(callback: CallbackQuery):
    uid = callback.from_user.id
    now = int(time.time())

    sql.execute("SELECT last_bonus FROM users WHERE user_id=?", (uid,))
    last = sql.fetchone()[0]

    if now - last < BONUS_COOLDOWN:
        await callback.answer("⏳ Раз в час", show_alert=True)
        return

    sql.execute("UPDATE users SET balance = balance + ?, last_bonus=? WHERE user_id=?", (BONUS_AMOUNT, now, uid))
    db.commit()
    await callback.answer("🎁 +3 конфеты", show_alert=True)

# ================= VIDEO =================
@dp.callback_query(F.data == "watch")
async def watch(callback: CallbackQuery):
    uid = callback.from_user.id
    sql.execute("SELECT balance FROM users WHERE user_id=?", (uid,))
    bal = sql.fetchone()[0]

    if bal < VIDEO_PRICE:
        await callback.answer("❌ Недостаточно конфет", show_alert=True)
        return

    sql.execute("""
    SELECT id, file_id FROM videos
    WHERE id NOT IN (SELECT video_id FROM watched WHERE user_id=?)
    ORDER BY RANDOM() LIMIT 1
    """, (uid,))
    video = sql.fetchone()

    if not video:
        await callback.answer("🎬 Видео закончились", show_alert=True)
        return

    vid, file = video
    await callback.message.answer_video(file)

    sql.execute("UPDATE users SET balance = balance - 1 WHERE user_id=?", (uid,))
    sql.execute("INSERT INTO watched VALUES (?,?)", (uid, vid))
    db.commit()

# ================= ADMIN =================
@dp.message(Command("addpromo"))
async def addpromo(message: Message):
    if message.from_user.id not in ADMINS:
        return
    _, code, amount = message.text.split()
    sql.execute("INSERT OR REPLACE INTO promo VALUES (?,?)", (code, int(amount)))
    db.commit()
    await message.answer("✅ Промокод создан")

@dp.message(Command("delpromo"))
async def delpromo(message: Message):
    if message.from_user.id not in ADMINS:
        return
    _, code = message.text.split()
    sql.execute("DELETE FROM promo WHERE code=?", (code,))
    db.commit()
    await message.answer("🗑 Промокод удалён")

@dp.message(Command("addbalance"))
async def addbalance(message: Message):
    if message.from_user.id not in ADMINS:
        return
    _, uid, amt = message.text.split()
    sql.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (int(amt), int(uid)))
    db.commit()
    await message.answer("✅ Баланс пополнен")

@dp.message(Command("subbalance"))
async def subbalance(message: Message):
    if message.from_user.id not in ADMINS:
        return
    _, uid, amt = message.text.split()
    sql.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (int(amt), int(uid)))
    db.commit()
    await message.answer("➖ Баланс уменьшен")

@dp.message(Command("addvideo"))
async def addvideo(message: Message):
    if message.from_user.id not in ADMINS:
        return
    if not message.video:
        await message.answer("Отправь видео")
        return
    sql.execute("INSERT INTO videos (file_id) VALUES (?)", (message.video.file_id,))
    db.commit()
    await message.answer("🎬 Видео добавлено")

# ================= RUN =================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

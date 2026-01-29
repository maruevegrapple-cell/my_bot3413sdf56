import time
import random

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart, Command

from config import (
    ADMIN_ID,
    BOT_USERNAME,
    VIDEO_PRICE,
    BONUS_AMOUNT,
    BONUS_COOLDOWN,
    REF_BONUS,
)

from db import cursor, conn
from keyboards import fake_menu, main_menu, video_menu, shop_menu
from payments import create_invoice, check_invoice

router = Router()

# ================= STATE =================
promo_wait = set()
custom_pay_wait = set()
captcha_wait = {}

# ================= CAPTCHA =================
def gen_captcha():
    a = random.randint(1, 9)
    b = random.randint(1, 9)
    return a, b, a + b

# ================= ACCESS =================
def has_access(user_id: int) -> bool:
    cursor.execute("SELECT is_verified FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return row and row["is_verified"] == 1

# ================= START =================
@router.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username

    # ADMIN
    if user_id == ADMIN_ID:
        cursor.execute("""
            INSERT OR IGNORE INTO users (user_id, username, is_verified)
            VALUES (?, ?, 1)
        """, (user_id, username))
        cursor.execute(
            "UPDATE users SET is_verified = 1 WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()
        await message.answer("👑 Админ-доступ", reply_markup=main_menu)
        return

    # REF
    args = message.text.split()
    ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()

    if not user:
        cursor.execute("""
            INSERT INTO users (user_id, username, referrer, is_verified)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, ref_id, 0))
        conn.commit()

    # CAPTCHA
    a, b, res = gen_captcha()
    captcha_wait[user_id] = res
    await message.answer(f"🤖 Реши пример: {a} + {b} = ?")

# ================= CAPTCHA CHECK =================
@router.message(F.text)
async def captcha_check(message: Message):
    user_id = message.from_user.id

    if user_id not in captcha_wait:
        return

    if message.text.strip() == str(captcha_wait[user_id]):
        del captcha_wait[user_id]
        cursor.execute(
            "UPDATE users SET is_verified = 1 WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()
        await message.answer("✅ Доступ открыт", reply_markup=main_menu)
    else:
        await message.answer("❌ Неверно, попробуй ещё")

# ================= FAKE MENU =================
@router.callback_query(F.data.startswith("fake_"))
async def fake_menu_actions(call: CallbackQuery):
    if call.from_user.id not in captcha_wait and not has_access(call.from_user.id):
        await call.answer("❌ Сначала пройди капчу", show_alert=True)
        return

    if call.data == "fake_download":
        await call.answer("❌ Ошибка загрузки", show_alert=True)
    elif call.data == "fake_rate":
        await call.answer(f"💱 Курс: {random.randint(60,120)}", show_alert=True)
    elif call.data == "fake_dice":
        await call.answer(f"🎲 Выпало: {random.randint(1,6)}", show_alert=True)

# ================= MENU =================
@router.callback_query(F.data == "menu")
async def back_to_menu(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return
    await call.message.answer("🎥 Видео платформа", reply_markup=main_menu)

# ================= VIDEOS =================
@router.callback_query(F.data == "videos")
async def videos(call: CallbackQuery):
    user_id = call.from_user.id

    if not has_access(user_id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()["balance"]

    if balance < VIDEO_PRICE:
        await call.answer("❌ Недостаточно конфет", show_alert=True)
        return

    cursor.execute("""
        SELECT id, file_id FROM videos
        WHERE id NOT IN (
            SELECT video_id FROM user_videos WHERE user_id = ?
        )
        ORDER BY id ASC
        LIMIT 1
    """, (user_id,))
    video = cursor.fetchone()

    if not video:
        await call.answer("❌ Видео закончились", show_alert=True)
        return

    cursor.execute(
        "UPDATE users SET balance = balance - ? WHERE user_id = ?",
        (VIDEO_PRICE, user_id)
    )
    cursor.execute(
        "INSERT OR IGNORE INTO user_videos (user_id, video_id) VALUES (?, ?)",
        (user_id, video["id"])
    )
    conn.commit()

    await call.message.answer_video(
        video["file_id"],
        caption="🎥 Видео\n🍬 -1 конфета",
        reply_markup=video_menu,
        protect_content=True
    )

# ================= BONUS =================
@router.callback_query(F.data == "bonus")
async def bonus(call: CallbackQuery):
    user_id = call.from_user.id

    if not has_access(user_id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    now = int(time.time())
    cursor.execute("SELECT last_bonus FROM users WHERE user_id = ?", (user_id,))
    last = cursor.fetchone()["last_bonus"]

    if now - last < BONUS_COOLDOWN:
        await call.answer("⏳ Бонус уже получен", show_alert=True)
        return

    cursor.execute("""
        UPDATE users
        SET balance = balance + ?, last_bonus = ?
        WHERE user_id = ?
    """, (BONUS_AMOUNT, now, user_id))
    conn.commit()

    await call.answer(f"🎁 +{BONUS_AMOUNT} 🍬", show_alert=True)

# ================= PROFILE =================
@router.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    user_id = call.from_user.id

    if not has_access(user_id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
    balance = cursor.fetchone()["balance"]

    ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"

    await call.message.answer(
        f"👤 Профиль\n\n"
        f"🍬 Баланс: {balance}\n\n"
        f"🔗 Реферальная ссылка:\n{ref_link}\n\n"
        f"🎁 За друга: +{REF_BONUS} 🍬"
    )

# ================= SHOP =================
@router.callback_query(F.data == "shop")
async def shop(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    await call.message.answer(
        "🍬 <b>Магазин конфет</b>\n\n"
        "⭐ Для оплаты звездами:\n"
        "<a href='https://t.me/voprosy?start=fasn6fm'>писать сюда</a>\n\n"
        "📊 Курс звезд Telegram:\n"
        "100 ⭐ = 299 🍬",
        parse_mode="HTML",
        reply_markup=shop_menu
    )

# ================= PAY (шаблоны) =================
@router.callback_query(F.data.startswith("pay_"))
async def pay(call: CallbackQuery):
    prices = {
        "pay_50": (50, 0.2),
        "pay_100": (100, 0.3),
        "pay_140": (140, 0.4),
        "pay_170": (170, 0.5),
        "pay_200": (200, 0.6),
        "pay_333": (333, 1.0),
    }

    if call.data not in prices:
        return

    amount, usdt = prices[call.data]
    invoice = create_invoice(usdt)

    cursor.execute("""
        INSERT INTO payments (invoice_id, user_id, amount)
        VALUES (?, ?, ?)
    """, (invoice["invoice_id"], call.from_user.id, amount))
    conn.commit()

    await call.message.answer(
        f"💳 <b>Оплата</b>\n\n"
        f"🍬 Конфеты: <b>{amount}</b>\n"
        f"💵 Сумма: <b>{usdt} USDT</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Оплатить", url=invoice["pay_url"])],
            [InlineKeyboardButton(text="🔄 Проверить оплату", callback_data=f"check_{invoice['invoice_id']}")]
        ])
    )

# ================= CUSTOM PAY =================
@router.callback_query(F.data == "pay_custom")
async def pay_custom(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return
    custom_pay_wait.add(call.from_user.id)
    await call.message.answer("✏️ Введите количество 🍬:")

@router.message(F.text)
async def custom_pay_input(message: Message):
    user_id = message.from_user.id

    if user_id not in custom_pay_wait:
        return

    custom_pay_wait.remove(user_id)

    if not message.text.isdigit():
        await message.answer("❌ Введите число")
        return

    amount = int(message.text)
    usdt = round(amount / 333, 2)

    invoice = create_invoice(usdt)

    cursor.execute("""
        INSERT INTO payments (invoice_id, user_id, amount)
        VALUES (?, ?, ?)
    """, (invoice["invoice_id"], user_id, amount))
    conn.commit()

    await message.answer(
        f"💳 <b>Оплата</b>\n\n🍬 {amount}\n💵 {usdt} USDT",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="💰 Оплатить", url=invoice["pay_url"])],
            [InlineKeyboardButton(text="🔄 Проверить", callback_data=f"check_{invoice['invoice_id']}")]
        ])
    )

# ================= CHECK =================
@router.callback_query(F.data.startswith("check_"))
async def check(call: CallbackQuery):
    invoice_id = call.data.split("_", 1)[1]

    cursor.execute(
        "SELECT user_id, amount FROM payments WHERE invoice_id = ?",
        (invoice_id,)
    )
    row = cursor.fetchone()

    if not row:
        await call.answer("❌ Платёж не найден", show_alert=True)
        return

    if check_invoice(invoice_id):
        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (row["amount"], row["user_id"])
        )
        cursor.execute(
            "DELETE FROM payments WHERE invoice_id = ?",
            (invoice_id,)
        )
        conn.commit()

        await call.message.answer(f"✅ Оплата прошла!\n🍬 +{row['amount']}")
    else:
        await call.answer("⏳ Платёж не найден", show_alert=True)

# ================= PROMO =================
@router.callback_query(F.data == "promo")
async def promo_button(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    promo_wait.add(call.from_user.id)
    await call.message.answer("🎟 Введите промокод:")

@router.message(F.text)
async def promo_input(message: Message):
    user_id = message.from_user.id

    if user_id not in promo_wait:
        return

    promo_wait.remove(user_id)
    code = message.text.strip()

    cursor.execute("SELECT * FROM promocodes WHERE code = ?", (code,))
    promo = cursor.fetchone()

    if not promo or promo["activations_left"] <= 0:
        await message.answer("❌ Неверный или закончился")
        return

    cursor.execute("""
        SELECT 1 FROM used_promocodes
        WHERE user_id = ? AND code = ?
    """, (user_id, code))
    if cursor.fetchone():
        await message.answer("❌ Вы уже использовали этот код")
        return

    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (promo["reward"], user_id))
    cursor.execute("UPDATE promocodes SET activations_left = activations_left - 1 WHERE code = ?", (code,))
    cursor.execute("INSERT INTO used_promocodes (user_id, code) VALUES (?, ?)", (user_id, code))

    conn.commit()
    await message.answer(f"🎉 +{promo['reward']} 🍬")

# ================= ADMIN =================
@router.message(F.video)
async def upload_video(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("INSERT INTO videos (file_id) VALUES (?)", (message.video.file_id,))
    conn.commit()
    await message.answer("✅ Видео добавлено")

@router.message(Command("add_promo"))
async def add_promo(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        _, code, reward, count = message.text.split()
        reward = int(reward)
        count = int(count)
    except ValueError:
        await message.answer("❌ Формат: /add_promo CODE REWARD COUNT")
        return

    cursor.execute("""
        INSERT OR REPLACE INTO promocodes
        (code, reward, activations_left)
        VALUES (?, ?, ?)
    """, (code, reward, count))
    conn.commit()

    await message.answer("✅ Промокод добавлен")

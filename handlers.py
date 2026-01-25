import time
import random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command

from config import *
from db import cursor, conn
from keyboards import fake_menu, main_menu, video_menu

router = Router()

# ================= ACCESS =================
def has_access(user_id: int) -> bool:
    cursor.execute("SELECT is_verified FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return bool(row and row["is_verified"] == 1)


# ================= START =================
@router.message(CommandStart())
async def start(message: Message):
    args = message.text.split()
    ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    cursor.execute("SELECT * FROM users WHERE user_id = ?", (message.from_user.id,))
    user = cursor.fetchone()

    if not user:
        cursor.execute(
            "INSERT INTO users (user_id, username, referrer, is_verified) VALUES (?, ?, ?, ?)",
            (
                message.from_user.id,
                message.from_user.username,
                ref_id,
                1 if ref_id else 0
            )
        )

        if ref_id:
            cursor.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (REF_BONUS, ref_id)
            )

        conn.commit()

    else:
        if ref_id and user["is_verified"] == 0:
            cursor.execute(
                "UPDATE users SET referrer = ?, is_verified = 1 WHERE user_id = ?",
                (ref_id, message.from_user.id)
            )
            cursor.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (REF_BONUS, ref_id)
            )
            conn.commit()

    if has_access(message.from_user.id):
        await message.answer("🎥 Видео платформа", reply_markup=main_menu)
    else:
        await message.answer("🎬 Онлайн сервис", reply_markup=fake_menu)


# ================= FAKE MENU =================
@router.callback_query(F.data.startswith("fake_"))
async def fake_menu_actions(call: CallbackQuery):
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
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (call.from_user.id,))
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
    """, (call.from_user.id,))
    video = cursor.fetchone()

    if not video:
        await call.answer("❌ Видео закончились", show_alert=True)
        return

    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (VIDEO_PRICE, call.from_user.id))
    cursor.execute("INSERT INTO user_videos VALUES (?, ?)", (call.from_user.id, video["id"]))
    conn.commit()

    await call.message.answer_video(
        video["file_id"],
        caption=f"🎥 Видео\n🍬 -{VIDEO_PRICE} конфета",
        reply_markup=video_menu
    )


# ================= BONUS =================
@router.callback_query(F.data == "bonus")
async def bonus(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    now = int(time.time())
    cursor.execute("SELECT last_bonus FROM users WHERE user_id = ?", (call.from_user.id,))
    last = cursor.fetchone()["last_bonus"]

    if now - last < BONUS_COOLDOWN:
        await call.answer("⏳ Бонус уже получен", show_alert=True)
        return

    cursor.execute(
        "UPDATE users SET balance = balance + ?, last_bonus = ? WHERE user_id = ?",
        (BONUS_AMOUNT, now, call.from_user.id)
    )
    conn.commit()

    await call.answer(f"🎁 +{BONUS_AMOUNT} конфеты", show_alert=True)


# ================= PROFILE =================
@router.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (call.from_user.id,))
    balance = cursor.fetchone()["balance"]

    ref_link = f"https://t.me/{BOT_USERNAME}?start={call.from_user.id}"

    await call.message.answer(
        f"👤 Профиль\n\n"
        f"🍬 Баланс: {balance}\n\n"
        f"🔗 Реферальная ссылка:\n{ref_link}\n\n"
        f"🎁 За каждого друга: +{REF_BONUS} конфеты"
    )


# ================= SHOP =================
@router.callback_query(F.data == "shop")
async def shop(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return
    await call.message.answer(PAYMENT_TEXT)


# ================= PROMO =================
promo_wait = set()

@router.callback_query(F.data == "promo")
async def promo_button(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return
    promo_wait.add(call.from_user.id)
    await call.message.answer("🎟 Введите промокод:")


@router.message(F.text)
async def promo_input(message: Message):
    if message.from_user.id not in promo_wait:
        return

    promo_wait.remove(message.from_user.id)
    code = message.text.strip()

    cursor.execute("SELECT * FROM promocodes WHERE code = ?", (code,))
    promo = cursor.fetchone()

    if not promo or promo["activations_left"] <= 0:
        await message.answer("❌ Неверный или закончился промокод")
        return

    cursor.execute(
        "SELECT 1 FROM promo_uses WHERE user_id = ? AND code = ?",
        (message.from_user.id, code)
    )
    if cursor.fetchone():
        await message.answer("❌ Вы уже использовали этот промокод")
        return

    cursor.execute(
        "INSERT INTO promo_uses (user_id, code) VALUES (?, ?)",
        (message.from_user.id, code)
    )
    cursor.execute(
        "UPDATE promocodes SET activations_left = activations_left - 1 WHERE code = ?",
        (code,)
    )
    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (promo["reward"], message.from_user.id)
    )
    conn.commit()

    await message.answer(f"🎉 Промокод активирован! +{promo['reward']} 🍬")


# ================= ADMIN =================
@router.message(F.video)
async def upload_video(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute(
        "INSERT INTO videos (file_id) VALUES (?)",
        (message.video.file_id,)
    )
    conn.commit()

    await message.answer("✅ Видео загружено и добавлено в очередь")


@router.message(Command("add_balance"))
async def add_balance(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    _, user_id, amount = message.text.split()
    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (int(amount), int(user_id))
    )
    conn.commit()
    await message.answer("✅ Баланс пополнен")


@router.message(Command("remove_balance"))
async def remove_balance(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    _, user_id, amount = message.text.split()
    cursor.execute(
        "UPDATE users SET balance = balance - ? WHERE user_id = ?",
        (int(amount), int(user_id))
    )
    conn.commit()
    await message.answer("✅ Баланс уменьшен")


@router.message(Command("add_promo"))
async def add_promo(message: Message):
    if message.from_user.id != ADMIN_ID:
        return
    _, code, reward, count = message.text.split()
    cursor.execute(
        "INSERT OR REPLACE INTO promocodes (code, reward, activations_left) VALUES (?, ?, ?)",
        (code, int(reward), int(count))
    )
    conn.commit()
    await message.answer("✅ Промокод добавлен")

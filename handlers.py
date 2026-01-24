import time
import random

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command

from config import *
from db import cursor, conn
from keyboards import fake_menu, main_menu, video_menu

router = Router()


# ---------- ACCESS ----------
def has_access(user_id: int) -> bool:
    cursor.execute(
        "SELECT is_verified FROM users WHERE user_id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    return row and row[0] == 1


# ---------- START ----------
@router.message(CommandStart())
async def start(message: Message):
    # 👑 АДМИН
    if message.from_user.id == ADMIN_ID:
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, is_verified) VALUES (?, ?, 1)",
            (message.from_user.id, message.from_user.username)
        )
        cursor.execute(
            "UPDATE users SET is_verified = 1 WHERE user_id = ?",
            (message.from_user.id,)
        )
        conn.commit()

        await message.answer("👑 Админ-доступ", reply_markup=main_menu)
        return

    # ---------- USERS ----------
    args = message.text.split()
    ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    cursor.execute(
        "SELECT user_id FROM users WHERE user_id = ?",
        (message.from_user.id,)
    )
    exists = cursor.fetchone()

    if not exists:
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

    if has_access(message.from_user.id):
        await message.answer("🎥 Видео платформа", reply_markup=main_menu)
    else:
        await message.answer("🎬 Онлайн сервис", reply_markup=fake_menu)


# ---------- FAKE MENU ----------
@router.callback_query(F.data.startswith("fake_"))
async def fake_actions(call: CallbackQuery):
    if call.data == "fake_download":
        await call.answer("❌ Ошибка загрузки", show_alert=True)

    elif call.data == "fake_rate":
        await call.answer(f"💱 Курс: {random.randint(60,120)}", show_alert=True)

    elif call.data == "fake_dice":
        await call.answer(f"🎲 Выпало: {random.randint(1,6)}", show_alert=True)


# ---------- BACK ----------
@router.callback_query(F.data == "menu")
async def back_menu(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    await call.message.answer("🎥 Видео платформа", reply_markup=main_menu)


# ---------- VIDEOS ----------
@router.callback_query(F.data == "videos")
async def videos(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    cursor.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (call.from_user.id,)
    )
    balance = cursor.fetchone()[0]

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

    video_id, file_id = video

    cursor.execute(
        "UPDATE users SET balance = balance - ? WHERE user_id = ?",
        (VIDEO_PRICE, call.from_user.id)
    )
    cursor.execute(
        "INSERT INTO user_videos VALUES (?, ?)",
        (call.from_user.id, video_id)
    )
    conn.commit()

    await call.message.answer_video(
        file_id,
        caption="🎥 Видео\n🍬 -1 конфета",
        reply_markup=video_menu
    )


# ---------- BONUS ----------
@router.callback_query(F.data == "bonus")
async def bonus(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    now = int(time.time())
    cursor.execute(
        "SELECT last_bonus FROM users WHERE user_id = ?",
        (call.from_user.id,)
    )
    last = cursor.fetchone()[0]

    if now - last < BONUS_COOLDOWN:
        await call.answer("⏳ Бонус уже получен", show_alert=True)
        return

    cursor.execute(
        "UPDATE users SET balance = balance + ?, last_bonus = ? WHERE user_id = ?",
        (BONUS_AMOUNT, now, call.from_user.id)
    )
    conn.commit()

    await call.answer("🎁 +3 конфеты", show_alert=True)


# ---------- PROFILE ----------
@router.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    cursor.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (call.from_user.id,)
    )
    balance = cursor.fetchone()[0]

    ref_link = f"https://t.me/CandyBlossom34_bot?start={call.from_user.id}"

    await call.message.answer(
        f"👤 Профиль\n\n"
        f"🍬 Баланс: {balance}\n\n"
        f"🔗 Реферальная ссылка:\n{ref_link}\n\n"
        f"🎁 За каждого друга: +3 конфеты"
    )


# ---------- SHOP ----------
@router.callback_query(F.data == "shop")
async def shop(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    await call.message.answer(PAYMENT_TEXT)


# ---------- ADMIN VIDEO ----------
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


# ---------- PROMO ADMIN ----------
@router.message(Command("add_promo"))
async def add_promo(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    parts = message.text.split()
    if len(parts) != 3:
        await message.answer("❌ Формат: /add_promo КОД СУММА")
        return

    code = parts[1]
    amount = int(parts[2])

    cursor.execute(
        "INSERT OR IGNORE INTO promo_codes (code, amount) VALUES (?, ?)",
        (code, amount)
    )
    conn.commit()

    await message.answer(f"✅ Промокод {code} на {amount} конфет создан")


# ---------- PROMO USER ----------
@router.message(Command("use_promo"))
async def use_promo(message: Message):
    parts = message.text.split()
    if len(parts) != 2:
        await message.answer("❌ Формат: /use_promo КОД")
        return

    code = parts[1]

    cursor.execute(
        "SELECT amount FROM promo_codes WHERE code = ?",
        (code,)
    )
    promo = cursor.fetchone()

    if not promo:
        await message.answer("❌ Промокод не найден")
        return

    amount = promo[0]

    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (amount, message.from_user.id)
    )
    cursor.execute(
        "DELETE FROM promo_codes WHERE code = ?",
        (code,)
    )
    conn.commit()

    await message.answer(f"🎉 Промокод активирован! +{amount} конфет")

import time, random
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart

from config import *
from db import cursor, conn
from keyboards import fake_menu, main_menu, video_menu

router = Router()

# ---------- ACCESS ----------
def has_access(user_id: int) -> bool:
    cursor.execute("SELECT is_verified FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    return bool(row and row[0] == 1)

# ---------- START ----------
@router.message(CommandStart())
async def start(message: Message):
    if message.from_user.id == ADMIN_ID:
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, is_verified) VALUES (?, ?, 1)",
            (message.from_user.id, message.from_user.username)
        )
        cursor.execute("UPDATE users SET is_verified = 1 WHERE user_id = ?", (message.from_user.id,))
        conn.commit()

        await message.answer("👑 Админ-доступ", reply_markup=main_menu)
        return

    args = message.text.split()
    ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (message.from_user.id,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (user_id, username, referrer, is_verified) VALUES (?, ?, ?, ?)",
            (message.from_user.id, message.from_user.username, ref_id, 1 if ref_id else 0)
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

# ---------- FAKE ----------
@router.callback_query(F.data.startswith("fake_"))
async def fake_actions(call: CallbackQuery):
    await call.answer("❌ Недоступно", show_alert=True)

# ---------- MENU ----------
@router.callback_query(F.data == "menu")
async def menu(call: CallbackQuery):
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

    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (call.from_user.id,))
    balance = cursor.fetchone()[0]

    if balance < VIDEO_PRICE:
        await call.answer("❌ Недостаточно конфет", show_alert=True)
        return

    cursor.execute("""
        SELECT id, file_id FROM videos
        WHERE id NOT IN (
            SELECT video_id FROM user_videos WHERE user_id = ?
        )
        ORDER BY id ASC LIMIT 1
    """, (call.from_user.id,))
    video = cursor.fetchone()

    if not video:
        await call.answer("❌ Видео закончились", show_alert=True)
        return

    video_id, file_id = video

    cursor.execute("UPDATE users SET balance = balance - 1 WHERE user_id = ?", (call.from_user.id,))
    cursor.execute("INSERT INTO user_videos VALUES (?, ?)", (call.from_user.id, video_id))
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
    cursor.execute("SELECT last_bonus FROM users WHERE user_id = ?", (call.from_user.id,))
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
    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (call.from_user.id,))
    balance = cursor.fetchone()[0]

    ref_link = f"https://t.me/{BOT_USERNAME}?start={call.from_user.id}"

    await call.message.answer(
        f"👤 Профиль\n\n"
        f"🍬 Баланс: {balance}\n"
        f"👥 За каждого друга: +3 конфеты\n\n"
        f"🔗 Реферальная ссылка:\n{ref_link}"
    )

# ---------- SHOP (ПОЧИНЕНО) ----------
@router.callback_query(F.data == "shop")
async def shop(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return
    await call.message.answer(PAYMENT_TEXT)

# ---------- PROMO ----------
@router.callback_query(F.data == "promo")
async def promo(call: CallbackQuery):
    await call.message.answer("🎟 Введите промокод:")

# ---------- ADMIN VIDEO ----------
@router.message(F.video)
async def upload_video(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute("INSERT INTO videos (file_id) VALUES (?)", (message.video.file_id,))
    conn.commit()
    await message.answer("✅ Видео загружено")

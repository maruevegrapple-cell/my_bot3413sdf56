import time
import random

from aiogram import Router, Bot, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from config import *
from db import cursor, conn
from keyboards import fake_menu, main_menu, video_menu

router = Router()


# ================= STATES =================
class TopUpState(StatesGroup):
    waiting_amount = State()


# ================= ACCESS =================
def has_access(user_id: int) -> bool:
    if user_id in ADMINS:
        return True

    cursor.execute(
        "SELECT is_verified FROM users WHERE user_id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    return row and row[0] == 1


# ================= START =================
@router.message(Command("start"))
async def start_handler(message: Message):
    if message.from_user.id in ADMINS:
        await message.answer(
            "👑 Админ-доступ",
            reply_markup=main_menu
        )
        return

    cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (message.from_user.id,))
    exists = cursor.fetchone()

    if not exists:
        cursor.execute(
            "INSERT INTO users (user_id, username, referrer, is_verified) VALUES (?, ?, ?, ?)",
            (
                message.from_user.id,
                message.from_user.username,
                None,
                1
            )
        )
        conn.commit()

    await message.answer(
        "🎥 Видео платформа\n\nВыберите раздел:",
        reply_markup=main_menu if has_access(message.from_user.id) else fake_menu
    )


# ================= MENU =================
@router.callback_query(F.data == "menu")
async def back_to_menu(call: CallbackQuery):
    await call.message.answer(
        "🎥 Видео платформа\n\nВыберите раздел:",
        reply_markup=main_menu
    )


# ================= VIDEOS =================
@router.callback_query(F.data == "videos")
async def videos_handler(call: CallbackQuery):
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


# ================= BONUS =================
@router.callback_query(F.data == "bonus")
async def bonus_handler(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    now = int(time.time())
    cursor.execute("SELECT last_bonus FROM users WHERE user_id = ?", (call.from_user.id,))
    last = cursor.fetchone()[0]

    if last and now - last < BONUS_COOLDOWN:
        await call.answer("⏳ Бонус уже получен", show_alert=True)
        return

    cursor.execute(
        "UPDATE users SET balance = balance + ?, last_bonus = ? WHERE user_id = ?",
        (BONUS_AMOUNT, now, call.from_user.id)
    )
    conn.commit()

    await call.answer("🎁 Бонус получен!", show_alert=True)


# ================= PROFILE =================
@router.callback_query(F.data == "profile")
async def profile_handler(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    cursor.execute("SELECT balance FROM users WHERE user_id = ?", (call.from_user.id,))
    balance = cursor.fetchone()[0]

    await call.message.answer(
        f"👤 Профиль\n\n"
        f"🍬 Баланс: {balance}"
    )


# ================= TOP UP =================
@router.callback_query(F.data == "shop")
async def shop_handler(call: CallbackQuery, state: FSMContext):
    await state.set_state(TopUpState.waiting_amount)
    await call.message.answer("💰 Введите сумму пополнения:")


@router.message(TopUpState.waiting_amount)
async def process_amount(message: Message, state: FSMContext, bot: Bot):
    if not message.text.isdigit():
        await message.answer("❌ Введите число")
        return

    amount = int(message.text)

    for admin in ADMINS:
        await bot.send_message(
            admin,
            f"💰 Запрос на пополнение\n"
            f"👤 @{message.from_user.username}\n"
            f"🆔 {message.from_user.id}\n"
            f"💵 Сумма: {amount}"
        )

    await message.answer("✅ Запрос отправлен администратору")
    await state.clear()


# ================= ADMIN ADD VIDEO =================
@router.message(F.video, F.from_user.id.in_(ADMINS))
async def add_video(message: Message):
    cursor.execute(
        "INSERT OR IGNORE INTO videos (file_id) VALUES (?)",
        (message.video.file_id,)
    )
    conn.commit()
    await message.answer("✅ Видео добавлено")

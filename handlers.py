import time
import random

from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart, Command

from config import (
    ADMIN_ID,
    BOT_USERNAME,
    REF_BONUS,
    BONUS_AMOUNT,
    BONUS_COOLDOWN,
    VIDEO_PRICE,
    PAYMENT_TEXT
)

from db import cursor, conn
from keyboards import fake_menu, main_menu, video_menu

router = Router()

# ================= ACCESS =================
def has_access(user_id: int) -> bool:
    row = cursor.execute(
        "SELECT is_verified FROM users WHERE user_id = ?",
        (user_id,)
    ).fetchone()
    return bool(row and row[0] == 1)


# ================= START =================
@router.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username
    args = message.text.split()
    ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    row = cursor.execute(
        "SELECT user_id, is_verified FROM users WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    # админ всегда с доступом
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

    # новый пользователь
    if not row:
        verified = 1 if ref_id else 0
        cursor.execute("""
            INSERT INTO users (user_id, username, referrer, is_verified)
            VALUES (?, ?, ?, ?)
        """, (user_id, username, ref_id, verified))

        if ref_id:
            cursor.execute(
                "UPDATE users SET balance = balance + ? WHERE user_id = ?",
                (REF_BONUS, ref_id)
            )

        conn.commit()

    # старый пользователь, но пришёл по рефке → открыть доступ НАВСЕГДА
    elif ref_id:
        cursor.execute(
            "UPDATE users SET is_verified = 1 WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()

    if has_access(user_id):
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


# ================= BACK TO MENU =================
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

    balance = cursor.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (call.from_user.id,)
    ).fetchone()[0]

    if balance < VIDEO_PRICE:
        await call.answer("❌ Недостаточно конфет", show_alert=True)
        return

    video = cursor.execute("""
        SELECT id, file_id FROM videos
        WHERE id NOT IN (
            SELECT video_id FROM user_videos WHERE user_id = ?
        )
        ORDER BY id ASC
        LIMIT 1
    """, (call.from_user.id,)).fetchone()

    if not video:
        await call.answer("❌ Видео закончились", show_alert=True)
        return

    video_id, file_id = video

    cursor.execute(
        "UPDATE users SET balance = balance - 1 WHERE user_id = ?",
        (call.from_user.id,)
    )
    cursor.execute(
        "INSERT INTO user_videos (user_id, video_id) VALUES (?, ?)",
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
async def bonus(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    now = int(time.time())
    last = cursor.execute(
        "SELECT last_bonus FROM users WHERE user_id = ?",
        (call.from_user.id,)
    ).fetchone()[0]

    if now - last < BONUS_COOLDOWN:
        await call.answer("⏳ Бонус уже получен", show_alert=True)
        return

    cursor.execute("""
        UPDATE users
        SET balance = balance + ?, last_bonus = ?
        WHERE user_id = ?
    """, (BONUS_AMOUNT, now, call.from_user.id))
    conn.commit()

    await call.answer(f"🎁 +{BONUS_AMOUNT} конфеты", show_alert=True)


# ================= PROFILE =================
@router.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    balance = cursor.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (call.from_user.id,)
    ).fetchone()[0]

    ref_link = f"https://t.me/{BOT_USERNAME}?start={call.from_user.id}"

    await call.message.answer(
        f"👤 Профиль\n\n"
        f"🍬 Баланс: {balance}\n\n"
        f"🔗 Реферальная ссылка:\n{ref_link}\n\n"
        f"🎁 За каждого друга: +3 конфеты"
    )


# ================= SHOP =================
@router.callback_query(F.data == "shop")
async def shop(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return
    await call.message.answer(PAYMENT_TEXT)


# ================= PROMO BUTTON =================
@router.callback_query(F.data == "promo")
async def promo_button(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    cursor.execute(
        "UPDATE users SET waiting_promo = 1 WHERE user_id = ?",
        (call.from_user.id,)
    )
    conn.commit()

    await call.message.answer("🎟 Введите промокод:")


# ================= PROMO INPUT =================
@router.message(F.text)
async def promo_input(message: Message):
    if message.text.startswith("/"):
        return

    user_id = message.from_user.id

    row = cursor.execute(
        "SELECT waiting_promo FROM users WHERE user_id = ?",
        (user_id,)
    ).fetchone()

    if not row or row[0] != 1:
        return

    cursor.execute(
        "UPDATE users SET waiting_promo = 0 WHERE user_id = ?",
        (user_id,)
    )
    conn.commit()

    code = message.text.strip().upper()

    promo = cursor.execute(
        "SELECT reward, activations_left FROM promocodes WHERE code = ?",
        (code,)
    ).fetchone()

    if not promo:
        await message.answer("❌ Неверный промокод")
        return

    used = cursor.execute(
        "SELECT 1 FROM promo_uses WHERE user_id = ? AND code = ?",
        (user_id, code)
    ).fetchone()

    if used:
        await message.answer("❌ Вы уже использовали этот промокод")
        return

    reward, left = promo

    if left <= 0:
        await message.answer("❌ Лимит активаций исчерпан")
        return

    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (reward, user_id)
    )
    cursor.execute(
        "UPDATE promocodes SET activations_left = activations_left - 1 WHERE code = ?",
        (code,)
    )
    cursor.execute(
        "INSERT INTO promo_uses (user_id, code) VALUES (?, ?)",
        (user_id, code)
    )
    conn.commit()

    await message.answer(f"🎉 Промокод активирован! +{reward} 🍬")


# ================= ADMIN =================
@router.message(F.video)
async def upload_video(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    cursor.execute(
        "INSERT OR IGNORE INTO videos (file_id) VALUES (?)",
        (message.video.file_id,)
    )
    conn.commit()

    await message.answer("✅ Видео добавлено")


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

    cursor.execute("""
        INSERT OR REPLACE INTO promocodes (code, reward, activations_left)
        VALUES (?, ?, ?)
    """, (code.upper(), int(reward), int(count)))

    conn.commit()
    await message.answer("✅ Промокод добавлен")

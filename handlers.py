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
    cursor.execute(
        "SELECT is_verified FROM users WHERE user_id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    return bool(row and row[0] == 1)


# ================= START =================
@router.message(CommandStart())
async def start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username

    args = message.text.split()
    ref_id = int(args[1]) if len(args) > 1 and args[1].isdigit() else None

    cursor.execute(
        "SELECT user_id, is_verified FROM users WHERE user_id = ?",
        (user_id,)
    )
    user = cursor.fetchone()

    # --- новый пользователь ---
    if not user:
        cursor.execute(
            """
            INSERT INTO users (user_id, username, referrer, is_verified)
            VALUES (?, ?, ?, ?)
            """,
            (
                user_id,
                username,
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

    # --- старый пользователь, но пришёл по рефке ---
    elif ref_id and not user[1]:
        cursor.execute(
            "UPDATE users SET is_verified = 1 WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()

    # --- админ ---
    if user_id == ADMIN_ID:
        cursor.execute(
            "UPDATE users SET is_verified = 1 WHERE user_id = ?",
            (user_id,)
        )
        conn.commit()
        await message.answer("👑 Админ-доступ", reply_markup=main_menu)
        return

    # --- меню ---
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

    cursor.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,)
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
    """, (user_id,))
    video = cursor.fetchone()

    if not video:
        await call.answer("❌ Видео закончились", show_alert=True)
        return

    video_id, file_id = video

    cursor.execute(
        "UPDATE users SET balance = balance - 1 WHERE user_id = ?",
        (user_id,)
    )
    cursor.execute(
        "INSERT OR IGNORE INTO user_videos VALUES (?, ?)",
        (user_id, video_id)
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
    user_id = call.from_user.id

    if not has_access(user_id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    now = int(time.time())

    cursor.execute(
        "SELECT last_bonus FROM users WHERE user_id = ?",
        (user_id,)
    )
    last = cursor.fetchone()[0]

    if now - last < BONUS_COOLDOWN:
        await call.answer("⏳ Бонус уже получен", show_alert=True)
        return

    cursor.execute(
        """
        UPDATE users
        SET balance = balance + ?, last_bonus = ?
        WHERE user_id = ?
        """,
        (BONUS_AMOUNT, now, user_id)
    )
    conn.commit()

    await call.answer("🎁 +3 конфеты", show_alert=True)


# ================= PROFILE =================
@router.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    user_id = call.from_user.id

    if not has_access(user_id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    cursor.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (user_id,)
    )
    balance = cursor.fetchone()[0]

    ref_link = f"https://t.me/{BOT_USERNAME}?start={user_id}"

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


# ================= PROMO =================
waiting_promo = set()

@router.callback_query(F.data == "promo")
async def promo_button(call: CallbackQuery):
    if not has_access(call.from_user.id):
        await call.answer("❌ Нет доступа", show_alert=True)
        return

    waiting_promo.add(call.from_user.id)
    await call.message.answer("🎟 Введите промокод:")


@router.message()
async def promo_input(message: Message):
    user_id = message.from_user.id

    if user_id not in waiting_promo:
        return

    waiting_promo.discard(user_id)
    code = message.text.strip()

    cursor.execute(
        "SELECT reward FROM promocodes WHERE code = ?",
        (code,)
    )
    promo = cursor.fetchone()

    if not promo:
        await message.answer("❌ Неверный промокод")
        return

    cursor.execute(
        """
        INSERT OR IGNORE INTO promo_uses (code, user_id)
        VALUES (?, ?)
        """,
        (code, user_id)
    )

    if cursor.rowcount == 0:
        await message.answer("❌ Вы уже использовали этот промокод")
        return

    reward = promo[0]

    cursor.execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?",
        (reward, user_id)
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

    try:
        _, user_id, amount = message.text.split()
        cursor.execute(
            "UPDATE users SET balance = balance + ? WHERE user_id = ?",
            (int(amount), int(user_id))
        )
        conn.commit()
        await message.answer("✅ Баланс пополнен")
    except:
        await message.answer("❌ Формат: /add_balance user_id amount")


@router.message(Command("remove_balance"))
async def remove_balance(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        _, user_id, amount = message.text.split()
        cursor.execute(
            "UPDATE users SET balance = balance - ? WHERE user_id = ?",
            (int(amount), int(user_id))
        )
        conn.commit()
        await message.answer("✅ Баланс уменьшен")
    except:
        await message.answer("❌ Формат: /remove_balance user_id amount")


@router.message(Command("add_promo"))
async def add_promo(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        _, code, reward = message.text.split()
        cursor.execute(
            "INSERT OR IGNORE INTO promocodes (code, reward) VALUES (?, ?)",
            (code, int(reward))
        )
        conn.commit()
        await message.answer("✅ Промокод добавлен")
    except:
        await message.answer("❌ Формат: /add_promo CODE reward")


@router.message(Command("remove_promo"))
async def remove_promo(message: Message):
    if message.from_user.id != ADMIN_ID:
        return

    try:
        _, code = message.text.split()
        cursor.execute(
            "DELETE FROM promocodes WHERE code = ?",
            (code,)
        )
        conn.commit()
        await message.answer("✅ Промокод удалён")
    except:
        await message.answer("❌ Формат: /remove_promo CODE")

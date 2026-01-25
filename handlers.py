from aiogram import Router, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
import sqlite3
import time

router = Router()

conn = sqlite3.connect("database.db")
cursor = conn.cursor()

ADMINS = {5925859280}


# ================= FSM =================
class PromoState(StatesGroup):
    waiting_code = State()


# ================= KEYBOARDS =================
def fake_menu():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="🔗 Получить доступ")]],
        resize_keyboard=True
    )

def main_menu():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="👤 Профиль")],
            [KeyboardButton(text="🎁 Бонус"), KeyboardButton(text="🎟 Ввести промокод")]
        ],
        resize_keyboard=True
    )


# ================= ACCESS CHECK =================
def has_access(user_id: int) -> bool:
    cursor.execute(
        "SELECT referrer FROM users WHERE user_id = ?",
        (user_id,)
    )
    row = cursor.fetchone()
    return row and row[0] is not None


# ================= START =================
@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()

    user_id = message.from_user.id
    username = message.from_user.username
    args = message.text.split()

    cursor.execute(
        "INSERT OR IGNORE INTO users (user_id, username) VALUES (?, ?)",
        (user_id, username)
    )

    # -------- РЕФКА --------
    if len(args) > 1:
        ref_id = int(args[1])
        if ref_id != user_id:
            cursor.execute(
                "SELECT referrer FROM users WHERE user_id = ?",
                (user_id,)
            )
            if cursor.fetchone()[0] is None:
                cursor.execute(
                    "UPDATE users SET referrer = ? WHERE user_id = ?",
                    (ref_id, user_id)
                )

    conn.commit()

    if not has_access(user_id):
        await message.answer(
            "🔒 Доступ только по приглашению",
            reply_markup=fake_menu()
        )
        return

    await message.answer(
        "✅ Доступ открыт",
        reply_markup=main_menu()
    )


# ================= GATE =================
@router.message()
async def gate(message: Message, state: FSMContext):
    user_id = message.from_user.id

    if not has_access(user_id):
        await state.clear()
        await message.answer(
            "🔒 Доступ только по реферальной ссылке",
            reply_markup=fake_menu()
        )
        return

    await router.propagate_event(message, state)


# ================= PROFILE =================
@router.message(F.text == "👤 Профиль")
async def profile(message: Message):
    cursor.execute(
        "SELECT balance FROM users WHERE user_id = ?",
        (message.from_user.id,)
    )
    balance = cursor.fetchone()[0]
    await message.answer(f"👤 Профиль\n🍬 Баланс: {balance}")


# ================= BONUS =================
@router.message(F.text == "🎁 Бонус")
async def bonus(message: Message):
    user_id = message.from_user.id
    now = int(time.time())

    cursor.execute(
        "SELECT last_bonus FROM users WHERE user_id = ?",
        (user_id,)
    )
    last = cursor.fetchone()[0]

    if now - last < 3600:
        await message.answer("⏳ Бонус раз в час")
        return

    cursor.execute(
        "UPDATE users SET balance = balance + 3, last_bonus = ? WHERE user_id = ?",
        (now, user_id)
    )
    conn.commit()

    await message.answer("🎁 +3 конфеты 🍬")


# ================= PROMO =================
@router.message(F.text == "🎟 Ввести промокод")
async def promo_start(message: Message, state: FSMContext):
    await state.set_state(PromoState.waiting_code)
    await message.answer("✏️ Введите промокод:")


@router.message(PromoState.waiting_code)
async def promo_apply(message: Message, state: FSMContext):
    code = message.text.strip().upper()
    user_id = message.from_user.id

    cursor.execute(
        "SELECT reward, activations_left FROM promocodes WHERE code = ?",
        (code,)
    )
    promo = cursor.fetchone()

    if not promo:
        await message.answer("❌ Неверный промокод")
        await state.clear()
        return

    reward, left = promo

    cursor.execute(
        "SELECT 1 FROM promo_uses WHERE user_id = ? AND code = ?",
        (user_id, code)
    )
    if cursor.fetchone():
        await message.answer("❌ Уже использован")
        await state.clear()
        return

    if left <= 0:
        await message.answer("❌ Лимит исчерпан")
        await state.clear()
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

    await message.answer(f"✅ +{reward} 🍬")
    await state.clear()


# ================= ADMIN =================
@router.message(Command("add_promo"))
async def add_promo(message: Message):
    if message.from_user.id not in ADMINS:
        return
    try:
        _, code, reward, count = message.text.split()
        cursor.execute(
            "INSERT INTO promocodes VALUES (?, ?, ?)",
            (code.upper(), int(reward), int(count))
        )
        conn.commit()
        await message.answer("✅ Промокод добавлен")
    except:
        await message.answer("❌ /add_promo CODE REWARD COUNT")

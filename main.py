import asyncio
import time

from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message,
    CallbackQuery,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from aiogram.filters import Command

import db
from config import BOT_TOKEN, ADMIN_IDS, REF_BONUS, BONUS_AMOUNT, BONUS_COOLDOWN

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

db.init_db()

# ===================== КНОПКИ =====================

def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎥 Смотреть видео", callback_data="watch_video")],
        [InlineKeyboardButton(text="🍬 Шоп конфет", callback_data="shop")],
        [InlineKeyboardButton(text="👤 Профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🎁 Бонус", callback_data="bonus")],
        [InlineKeyboardButton(text="🎟 Промокод", callback_data="promo")],
        [InlineKeyboardButton(text="📢 Резервный канал", url="https://t.me/example")]
    ])


def fake_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📥 Скачать видео с YouTube", callback_data="fake_youtube")],
        [InlineKeyboardButton(text="💱 Узнать курс валют", callback_data="fake_rate")],
        [InlineKeyboardButton(text="🎲 Бросить кости", callback_data="fake_dice")]
    ])


# ===================== START =====================

@dp.message(Command("start"))
async def start(message: Message):
    user_id = message.from_user.id
    user = db.get_user(user_id)

    # Админ — сразу в основное меню
    if user_id in ADMIN_IDS:
        await message.answer("👮 Админ-доступ", reply_markup=main_menu())
        return

    # Проверка реферальной ссылки
    if message.text and " " in message.text:
        try:
            ref_id = int(message.text.split()[1])
        except ValueError:
            ref_id = None

        if ref_id and ref_id != user_id and user[2] == 0:
            db.set_ref_used(user_id)
            db.update_balance(ref_id, REF_BONUS)

            await message.answer(
                "🎉 Вы вошли по реферальной ссылке!\n"
                "Основное меню открыто навсегда.",
                reply_markup=main_menu()
            )
            return

    # Уже был по рефке
    if user[2] == 1:
        await message.answer("Главное меню", reply_markup=main_menu())
    else:
        await message.answer("❌ Доступ ограничен", reply_markup=fake_menu())


# ===================== ФЕЙК-МЕНЮ =====================

@dp.callback_query(F.data == "fake_youtube")
async def fake_youtube(call: CallbackQuery):
    await call.answer("Ошибка загрузки видео ❌", show_alert=True)


@dp.callback_query(F.data == "fake_rate")
async def fake_rate(call: CallbackQuery):
    rate = round(60 + (time.time() % 20), 2)
    await call.message.answer(f"💱 Текущий курс: {rate} RUB/USD")


@dp.callback_query(F.data == "fake_dice")
async def fake_dice(call: CallbackQuery):
    num = int(time.time()) % 6 + 1
    await call.message.answer(f"🎲 Выпало число: {num}")


# ===================== ПРОФИЛЬ (ФИКС РЕФКИ) =====================

@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    user = db.get_user(call.from_user.id)
    bot_username = (await bot.me()).username

    ref_link = (
        f"https://t.me/share/url?"
        f"url=https://t.me/{bot_username}?start={call.from_user.id}"
    )

    await call.message.answer(
        f"👤 Профиль\n\n"
        f"🍬 Баланс: {user[1]}\n\n"
        f"🔗 Реферальная ссылка:\n{ref_link}"
    )


# ===================== БОНУС =====================

@dp.callback_query(F.data == "bonus")
async def bonus(call: CallbackQuery):
    user_id = call.from_user.id

    if db.can_take_bonus(user_id):
        db.take_bonus(user_id)
        await call.message.answer(f"🎁 Вы получили {BONUS_AMOUNT} конфеты")
    else:
        await call.message.answer("⏳ Бонус можно получать раз в час")


# ===================== ШОП =====================

@dp.callback_query(F.data == "shop")
async def shop(call: CallbackQuery):
    await call.message.answer(
        "Курс 1$ = 299 конфет | 75 Звезд Telegram\n\n"
        "Если вам нужно больше, то умножайте свое число на 2\n\n"
        "Оплата принимается:\n"
        "CryptoBot ( Крипта ), Telegram stars.\n\n"
        "Для покупки обязательно напишите на этот аккаунт - @balikcyda\n\n"
        "✍️ Напишите количество конфет, которое хотите купить:"
    )


@dp.message(F.text.regexp(r"^\d+$"))
async def buy_request(message: Message):
    user_id = message.from_user.id
    amount = int(message.text)

    if amount <= 0:
        return

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                "💰 Запрос на покупку конфет\n\n"
                f"👤 Username: @{message.from_user.username}\n"
                f"🆔 ID: {user_id}\n"
                f"🍬 Количество: {amount}"
            )
        except:
            pass

    await message.answer("✅ Заявка отправлена администратору")


# ===================== ПРОМОКОД =====================

@dp.callback_query(F.data == "promo")
async def promo(call: CallbackQuery):
    await call.message.answer("🎟 Введите промокод:")


@dp.message(F.text)
async def activate_promo(message: Message):
    code = message.text.strip().upper()
    user_id = message.from_user.id

    promo = db.cursor.execute(
        "SELECT amount FROM promo_codes WHERE code=? AND active=1",
        (code,)
    ).fetchone()

    if not promo:
        return

    used = db.cursor.execute(
        "SELECT 1 FROM used_promos WHERE user_id=? AND code=?",
        (user_id, code)
    ).fetchone()

    if used:
        await message.answer("❌ Вы уже использовали этот промокод")
        return

    db.update_balance(user_id, promo[0])
    db.cursor.execute(
        "INSERT INTO used_promos (user_id, code) VALUES (?, ?)",
        (user_id, code)
    )
    db.conn.commit()

    await message.answer(f"🎉 Промокод активирован! +{promo[0]} конфет")


# ===================== АДМИН КОМАНДЫ =====================

@dp.message(Command("addbalance"))
async def add_balance(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    _, uid, amount = message.text.split()
    db.update_balance(int(uid), int(amount))
    await message.answer("✅ Баланс добавлен")


@dp.message(Command("delbalance"))
async def del_balance(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    _, uid, amount = message.text.split()
    db.update_balance(int(uid), -int(amount))
    await message.answer("✅ Баланс уменьшен")


@dp.message(Command("createpromo"))
async def create_promo(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    _, code, amount = message.text.split()
    db.cursor.execute(
        "INSERT OR REPLACE INTO promo_codes (code, amount, active) VALUES (?, ?, 1)",
        (code.upper(), int(amount))
    )
    db.conn.commit()
    await message.answer("🎟 Промокод создан")


@dp.message(Command("deletepromo"))
async def delete_promo(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    _, code = message.text.split()
    db.cursor.execute("DELETE FROM promo_codes WHERE code=?", (code.upper(),))
    db.conn.commit()
    await message.answer("❌ Промокод удалён")


# ===================== ЗАПУСК =====================

async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())

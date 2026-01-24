import asyncio
import time

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command

import db
from config import BOT_TOKEN, ADMIN_IDS, REF_BONUS, BONUS_AMOUNT, BONUS_COOLDOWN

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

db.init_db()

# ===================== МЕНЮ =====================

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
        [InlineKeyboardButton(text="📥 Скачать видео", callback_data="fake")],
        [InlineKeyboardButton(text="💱 Курс валют", callback_data="fake")],
        [InlineKeyboardButton(text="🎲 Рандом", callback_data="fake")]
    ])

# ===================== START =====================

@dp.message(Command("start"))
async def start(message: Message):
    user_id = message.from_user.id
    user = db.get_user(user_id)

    if user_id in ADMIN_IDS:
        await message.answer("👮 Админ-меню", reply_markup=main_menu())
        return

    if message.text and " " in message.text:
        try:
            ref_id = int(message.text.split()[1])
        except:
            ref_id = None

        if ref_id and ref_id != user_id and user[2] == 0:
            db.set_ref_used(user_id)
            db.update_balance(ref_id, REF_BONUS)
            await message.answer("🎉 Основное меню открыто!", reply_markup=main_menu())
            return

    if user[2] == 1:
        await message.answer("Главное меню", reply_markup=main_menu())
    else:
        await message.answer("❌ Доступ ограничен", reply_markup=fake_menu())

# ===================== ФЕЙК =====================

@dp.callback_query(F.data == "fake")
async def fake(call: CallbackQuery):
    await call.answer("❌ Недоступно", show_alert=True)

# ===================== ПРОФИЛЬ =====================

@dp.callback_query(F.data == "profile")
async def profile(call: CallbackQuery):
    user = db.get_user(call.from_user.id)

    await call.message.edit_text(
        f"👤 Профиль\n\n"
        f"🍬 Баланс: {user[1]}\n\n"
        f"🔗 Реферальная система активна",
        reply_markup=main_menu()
    )

# ===================== БОНУС =====================

@dp.callback_query(F.data == "bonus")
async def bonus(call: CallbackQuery):
    uid = call.from_user.id

    if db.can_take_bonus(uid):
        db.take_bonus(uid)
        await call.message.edit_text(
            f"🎁 Вы получили {BONUS_AMOUNT} конфет",
            reply_markup=main_menu()
        )
    else:
        await call.answer("⏳ Бонус раз в час", show_alert=True)

# ===================== ШОП =====================

user_in_shop = set()

@dp.callback_query(F.data == "shop")
async def shop(call: CallbackQuery):
    user_in_shop.add(call.from_user.id)

    await call.message.edit_text(
        "Курс 1$ = 299 конфет | 75 ⭐ Telegram\n\n"
        "Если нужно больше — умножайте на 2\n\n"
        "Оплата:\nCryptoBot, Telegram Stars\n\n"
        "✍️ Напишите количество конфет:",
        reply_markup=main_menu()
    )

@dp.message(F.text.regexp(r"^\d+$"))
async def buy_request(message: Message):
    uid = message.from_user.id

    if uid not in user_in_shop:
        return

    amount = int(message.text)
    user_in_shop.discard(uid)

    for admin in ADMIN_IDS:
        await bot.send_message(
            admin,
            f"💰 Заявка на пополнение\n\n"
            f"👤 ID: {uid}\n"
            f"🍬 Количество: {amount}"
        )

    await message.answer("✅ Администратор уведомлён")

# ===================== ВИДЕО =====================

@dp.callback_query(F.data == "watch_video")
async def watch_video(call: CallbackQuery):
    video = db.get_unwatched_video(call.from_user.id)

    if not video:
        await call.answer("❌ Видео закончились", show_alert=True)
        return

    await bot.send_video(
        call.from_user.id,
        video[0]
    )

    db.mark_video_watched(call.from_user.id, video[1])

# ===================== АДМИН: ЗАГРУЗКА ВИДЕО =====================

@dp.message(F.video)
async def upload_video(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    file_id = message.video.file_id
    db.add_video(file_id)

    await message.answer("✅ Видео добавлено в базу")

# ===================== ПРОМО =====================

@dp.callback_query(F.data == "promo")
async def promo(call: CallbackQuery):
    await call.message.edit_text("🎟 Введите промокод:")

@dp.message(F.text)
async def promo_activate(message: Message):
    code = message.text.upper()
    uid = message.from_user.id

    promo = db.get_promo(code)
    if not promo:
        return

    if db.is_promo_used(uid, code):
        await message.answer("❌ Уже использован")
        return

    db.use_promo(uid, code, promo)
    await message.answer(f"🎉 +{promo} конфет")

# ===================== АДМИН КОМАНДЫ =====================

@dp.message(Command("addbalance"))
async def add_balance(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    _, uid, amount = message.text.split()
    db.update_balance(int(uid), int(amount))
    await message.answer("✅ Готово")

@dp.message(Command("delbalance"))
async def del_balance(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    _, uid, amount = message.text.split()
    db.update_balance(int(uid), -int(amount))
    await message.answer("✅ Готово")

@dp.message(Command("createpromo"))
async def create_promo(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    _, code, amount = message.text.split()
    db.create_promo(code, int(amount))
    await message.answer("🎟 Промокод создан")

@dp.message(Command("deletepromo"))
async def delete_promo(message: Message):
    if message.from_user.id not in ADMIN_IDS:
        return

    _, code = message.text.split()
    db.delete_promo(code)
    await message.answer("❌ Удалён")

# ===================== RUN =====================

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

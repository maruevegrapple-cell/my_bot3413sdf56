import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.types import Message
from aiogram.filters import Command

from config import BOT_TOKEN_MODERATOR, CHANNEL_ID
from db import cursor, conn, get_user, update_user_balance

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN_MODERATOR)
dp = Dispatcher()

# ID вашего канала (из config.py)
TARGET_CHANNEL_ID = CHANNEL_ID


@dp.message(Command("start"))
async def start_command(message: Message):
    user_id = message.from_user.id
    
    # Проверяем, является ли пользователь админом основного бота
    cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user or not user["is_admin"]:
        await message.answer("❌ У вас нет доступа к этому боту. Только для администраторов.")
        return
    
    await message.answer(
        "🤖 <b>Бот-модератор работает в АВТОМАТИЧЕСКОМ режиме</b>\n\n"
        "Все заявки на вступление в канал проверяются автоматически.\n\n"
        "✅ <b>Пользователь принимается, если:</b>\n"
        "• Зарегистрирован в основном боте\n"
        "• Прошёл верификацию (капча + математический пример)\n\n"
        "❌ <b>Отклоняется, если:</b>\n"
        "• Не зарегистрирован в боте\n"
        "• Не прошёл верификацию\n\n"
        f"📊 Статистика: /stats\n"
        f"ℹ️ Статус: /status\n\n"
        f"👤 Username: @ZAYAVKABOTPRIEM1bot"
    )


@dp.message(Command("stats"))
async def stats_command(message: Message):
    user_id = message.from_user.id
    
    cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user or not user["is_admin"]:
        await message.answer("❌ Нет доступа")
        return
    
    cursor.execute("SELECT COUNT(*) as count FROM users")
    total = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_verified = 1")
    verified = cursor.fetchone()
    
    cursor.execute("SELECT COUNT(*) as count FROM users WHERE is_verified = 0")
    not_verified = cursor.fetchone()
    
    await message.answer(
        f"📊 <b>СТАТИСТИКА БОТА-МОДЕРАТОРА</b>\n\n"
        f"👥 Всего пользователей в БД: {total['count']}\n"
        f"✅ Верифицировано: {verified['count']}\n"
        f"❌ Не верифицировано: {not_verified['count']}\n\n"
        f"🤖 Режим: Автоматический\n"
        f"✅ Все заявки обрабатываются автоматически!\n\n"
        f"📌 Бот активен и ждёт заявки в канал."
    )


@dp.message(Command("status"))
async def status_command(message: Message):
    user_id = message.from_user.id
    
    cursor.execute("SELECT is_admin FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    
    if not user or not user["is_admin"]:
        await message.answer("❌ Нет доступа")
        return
    
    await message.answer(
        "✅ <b>Бот-модератор работает!</b>\n\n"
        f"📢 Канал: {TARGET_CHANNEL_ID}\n"
        f"🤖 Режим: Автоматический\n"
        f"👤 Username: @ZAYAVKABOTPRIEM1bot\n\n"
        f"🟢 Бот готов принимать заявки!"
    )


# Автоматический обработчик заявок на вступление
@dp.chat_join_request()
async def auto_handle_join_request(update: types.ChatJoinRequest):
    user_id = update.from_user.id
    username = update.from_user.username or "нет username"
    first_name = update.from_user.first_name or ""
    
    logger.info(f"📥 Новая заявка от @{username} (ID: {user_id})")
    
    # Проверяем пользователя в базе данных
    user = get_user(user_id)
    
    # Условия для автоматического принятия
    can_auto_approve = False
    reason = ""
    
    if user:
        if user.get("is_verified", 0) == 1:
            can_auto_approve = True
            reason = "✅ Пользователь верифицирован"
        else:
            reason = "❌ Пользователь не прошёл верификацию"
    else:
        reason = "❌ Пользователь не зарегистрирован в боте"
    
    if can_auto_approve:
        # Автоматически принимаем заявку
        try:
            await bot.approve_chat_join_request(chat_id=TARGET_CHANNEL_ID, user_id=user_id)
            
            # Начисляем бонус за вступление
            update_user_balance(user_id, 10)
            
            # Отправляем приветственное сообщение
            try:
                await bot.send_message(
                    user_id,
                    "🎉 <b>Добро пожаловать в канал!</b>\n\n"
                    "✅ Ваша заявка автоматически одобрена!\n"
                    "🎁 Вам начислено +10 🍬 за вступление!\n\n"
                    "Приятного общения! 🎬"
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            
            logger.info(f"✅ Автоматически принята заявка {user_id} - {reason}")
            
            # Уведомляем админов о новом участнике (опционально)
            cursor.execute("SELECT user_id FROM admins")
            admins = cursor.fetchall()
            for admin in admins:
                try:
                    await bot.send_message(
                        admin["user_id"],
                        f"✅ <b>Новый участник в канале!</b>\n\n"
                        f"👤 @{username}\n"
                        f"🆔 ID: {user_id}\n"
                        f"📝 {reason}\n"
                        f"🎁 Начислено +10 🍬"
                    )
                except Exception as e:
                    pass
                    
        except Exception as e:
            logger.error(f"Ошибка при принятии заявки {user_id}: {e}")
    
    else:
        # Автоматически отклоняем заявку
        try:
            await bot.decline_chat_join_request(chat_id=TARGET_CHANNEL_ID, user_id=user_id)
            
            # Отправляем сообщение с инструкцией
            try:
                await bot.send_message(
                    user_id,
                    "❌ <b>Заявка отклонена</b>\n\n"
                    f"📌 <b>Причина:</b> {reason}\n\n"
                    "📋 <b>Чтобы получить доступ в канал:</b>\n\n"
                    "1️⃣ Перейдите в нашего бота\n"
                    "2️⃣ Пройдите верификацию (капча + математический пример)\n"
                    "3️⃣ После верификации отправьте заявку заново\n\n"
                    f"🔗 <b>Ссылка на бота:</b> https://t.me/AnonkaBot34bot\n\n"
                    "После выполнения всех условий вы будете автоматически приняты в канал!"
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            
            logger.info(f"❌ Автоматически отклонена заявка {user_id} - {reason}")
            
        except Exception as e:
            logger.error(f"Ошибка при отклонении заявки {user_id}: {e}")


async def main():
    logger.info("🚀 Запуск бота-модератора в АВТОМАТИЧЕСКОМ режиме...")
    logger.info(f"📢 Канал для приёма заявок: {TARGET_CHANNEL_ID}")
    logger.info(f"🤖 Username: @ZAYAVKABOTPRIEM1bot")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
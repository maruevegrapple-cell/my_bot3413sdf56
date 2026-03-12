import asyncio
import logging
import os
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

# ========== ДИАГНОСТИКА ==========
print("="*50)
print("ДИАГНОСТИКА ПЕРЕМЕННЫХ")
print("="*50)
print(f"BOT_TOKEN из os.environ: {os.getenv('BOT_TOKEN', 'НЕ НАЙДЕН!')}")
print(f"BOT_TOKEN длина: {len(os.getenv('BOT_TOKEN', ''))}")
print(f"Все переменные окружения:")
for key in os.environ.keys():
    if "TOKEN" in key or "BOT" in key:
        print(f"  {key}: {os.environ[key][:10]}...")
print("="*50)

from config import BOT_TOKEN
from handlers import router
from db import init_db

logging.basicConfig(level=logging.INFO)

async def main():
    # Инициализируем БД
    init_db()
    
    # Создаем директорию для временных видео
    TEMP_DIR = "temp_videos"
    os.makedirs(TEMP_DIR, exist_ok=True)

    print(f"✅ Используется токен: {BOT_TOKEN[:10]}...")

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML,
            protect_content=True
        )
    )

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    
    dp.include_router(router)

    @dp.message(F.forward_from | F.forward_from_chat)
    async def block_forward(message: Message):
        await message.delete()

    print("✅ Бот запущен и готов к работе!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 Бот остановлен пользователем")
    except Exception as e:
        print(f"❌ Критическая ошибка: {e}")
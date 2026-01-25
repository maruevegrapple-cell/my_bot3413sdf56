import asyncio

from aiogram import Bot, Dispatcher

from config import BOT_TOKEN
from handlers import router
from db import init_db   # ❗ ВАЖНО

async def main():
    # ✅ инициализация базы ДО запуска бота
    init_db()

    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(router)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

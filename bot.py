input("BOT FILE EXECUTED. PRESS ENTER")
import asyncio
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from db import init_db
from handlers import router

async def main():
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    init_db()
    dp.include_router(router)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

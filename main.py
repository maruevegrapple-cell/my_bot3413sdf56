import asyncio
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from db import init_db
from handlers import start, fake_menu, main_menu, video, profile, bonus, payment, admin

async def main():
    bot = Bot(BOT_TOKEN)
    dp = Dispatcher()

    init_db()

    dp.include_router(start.router)
    dp.include_router(fake_menu.router)
    dp.include_router(main_menu.router)
    dp.include_router(video.router)
    dp.include_router(profile.router)
    dp.include_router(bonus.router)
    dp.include_router(payment.router)
    dp.include_router(admin.router)

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

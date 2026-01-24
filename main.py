import asyncio
from aiogram import Bot, Dispatcher
from config import BOT_TOKEN
from db import init_db

from handlers.start import router as start_router
from handlers.fake_menu import router as fake_router
from handlers.main_menu import router as main_router
from handlers.video import router as video_router
from handlers.bonus import router as bonus_router
from handlers.payment import router as payment_router
from handlers.admin import router as admin_router


async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()

    init_db()

    dp.include_router(start_router)
    dp.include_router(fake_router)
    dp.include_router(main_router)
    dp.include_router(video_router)
    dp.include_router(bonus_router)
    dp.include_router(payment_router)
    dp.include_router(admin_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


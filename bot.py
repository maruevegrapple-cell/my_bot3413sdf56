import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from config import BOT_TOKEN
from handlers import router
from db import init_db

async def main():
    init_db()
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher()
    dp.include_router(router)

    @dp.message(F.forward_from | F.forward_from_chat)
    async def block_forward(message: Message):
        await message.delete()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())

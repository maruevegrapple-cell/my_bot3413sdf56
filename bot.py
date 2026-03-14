import asyncio
import logging
import os
import sys
import traceback
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession

# ========== МАКСИМАЛЬНОЕ ЛОГИРОВАНИЕ ==========
print("="*60, file=sys.stderr)
print("🚀 БОТ ЗАПУСКАЕТСЯ С МАКСИМАЛЬНЫМ ЛОГИРОВАНИЕМ", file=sys.stderr)
print("="*60, file=sys.stderr)
sys.stderr.flush()

# Перехват всех исключений
def global_exception_handler(exc_type, exc_value, exc_traceback):
    print("🔥 ГЛОБАЛЬНОЕ ИСКЛЮЧЕНИЕ:", file=sys.stderr)
    print("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)), file=sys.stderr)
    sys.stderr.flush()

sys.excepthook = global_exception_handler

# ========== ДИАГНОСТИКА ПЕРЕМЕННЫХ ==========
print("="*50, file=sys.stderr)
print("ДИАГНОСТИКА ПЕРЕМЕННЫХ", file=sys.stderr)
print("="*50, file=sys.stderr)
print(f"BOT_TOKEN из os.environ: {os.getenv('BOT_TOKEN', 'НЕ НАЙДЕН!')}", file=sys.stderr)
print(f"BOT_TOKEN длина: {len(os.getenv('BOT_TOKEN', ''))}", file=sys.stderr)
print(f"Все переменные окружения:", file=sys.stderr)
for key in os.environ.keys():
    if "TOKEN" in key or "BOT" in key:
        print(f"  {key}: {os.environ[key][:10]}...", file=sys.stderr)
print("="*50, file=sys.stderr)
sys.stderr.flush()

from config import BOT_TOKEN
from handlers import router
from db import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ========== ВЕБ-СЕРВЕР ДЛЯ HEALTHCHECK ==========
from aiohttp import web

async def healthcheck(request):
    return web.Response(text="OK")

async def run_web():
    try:
        app = web.Application()
        app.router.add_get('/', healthcheck)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()
        print("✅ Web server for healthcheck started on port 8080", file=sys.stderr)
        sys.stderr.flush()
    except Exception as e:
        print(f"❌ Failed to start web server: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()

async def main():
    try:
        print("🔵 Запускаем main()...", file=sys.stderr)
        sys.stderr.flush()
        
        # Инициализируем БД
        print("🟡 Инициализация БД...", file=sys.stderr)
        init_db()
        print("✅ БД инициализирована", file=sys.stderr)
        
        # Создаем директорию для временных видео
        TEMP_DIR = "temp_videos"
        os.makedirs(TEMP_DIR, exist_ok=True)
        print(f"✅ Директория {TEMP_DIR} создана", file=sys.stderr)

        print(f"✅ Используется токен: {BOT_TOKEN[:10]}...", file=sys.stderr)
        sys.stderr.flush()

        # Запускаем веб-сервер для healthcheck
        asyncio.create_task(run_web())

        # Создаем сессию с увеличенным таймаутом
        session = AiohttpSession(timeout=60)
        
        bot = Bot(
            token=BOT_TOKEN,
            session=session,
            default=DefaultBotProperties(
                parse_mode=ParseMode.HTML,
                protect_content=True
            )
        )
        print("✅ Bot instance created", file=sys.stderr)

        storage = MemoryStorage()
        dp = Dispatcher(storage=storage)
        print("✅ Dispatcher created", file=sys.stderr)
        
        dp.include_router(router)
        print("✅ Router included", file=sys.stderr)

        @dp.message(F.forward_from | F.forward_from_chat)
        async def block_forward(message: Message):
            await message.delete()

        print("✅ Бот запущен и готов к работе!", file=sys.stderr)
        sys.stderr.flush()
        
        await dp.start_polling(bot)
        
    except Exception as e:
        print(f"❌ ОШИБКА В MAIN: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        raise

if __name__ == "__main__":
    try:
        print("🔵 Запускаем asyncio.run(main())...", file=sys.stderr)
        sys.stderr.flush()
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 Бот остановлен пользователем", file=sys.stderr)
        sys.stderr.flush()
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        raise
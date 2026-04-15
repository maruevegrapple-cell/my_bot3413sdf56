import asyncio
import logging
import os
import sys
import traceback
import json
from io import BytesIO
from datetime import datetime
from dotenv import load_dotenv

# Загружаем переменные окружения из .env файла
load_dotenv()

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession
from aiohttp import web

print("="*60, file=sys.stderr)
print("🚀 БОТ ЗАПУСКАЕТСЯ (PostgreSQL)", file=sys.stderr)
print("="*60, file=sys.stderr)
sys.stderr.flush()


def global_exception_handler(exc_type, exc_value, exc_traceback):
    print("🔥 ГЛОБАЛЬНОЕ ИСКЛЮЧЕНИЕ:", file=sys.stderr)
    print("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)), file=sys.stderr)
    sys.stderr.flush()


sys.excepthook = global_exception_handler

from config import BOT_TOKEN, MAIN_ADMIN_ID, BOT_USERNAME
from db import init_db_pool, close_db_pool, fetch, fetchrow, fetchval, execute
from handlers import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


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
        print("✅ Web server started on port 8080", file=sys.stderr)
    except Exception as e:
        print(f"❌ Failed to start web server: {e}", file=sys.stderr)


async def restore_db_handler(message: Message):
    user_id = message.from_user.id
    if user_id != MAIN_ADMIN_ID:
        await message.answer("❌ Нет доступа")
        return
    await message.answer("📤 Отправь JSON файл с бэкапом")


async def restore_from_json_handler(message: Message):
    user_id = message.from_user.id
    if user_id != MAIN_ADMIN_ID:
        return
    if not message.document.file_name.endswith('.json'):
        await message.answer("❌ Отправьте JSON файл")
        return
    status_msg = await message.answer("🔄 Восстанавливаю базу данных...")
    try:
        file = await message.bot.get_file(message.document.file_id)
        file_bytes = await message.bot.download_file(file.file_path)
        data = json.loads(file_bytes.read().decode('utf-8'))
        
        restored_tables = []
        for table_name, table_data in data.items():
            if table_name == "sqlite_sequence":
                continue
            columns = table_data.get("columns", [])
            rows = table_data.get("data", [])
            if not rows or not columns:
                continue
            
            await execute(f"DELETE FROM {table_name}")
            
            placeholders = ','.join([f"${i+1}" for i in range(len(columns))])
            for row in rows:
                values = [row.get(col) for col in columns]
                await execute(f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})", *values)
            
            restored_tables.append(f"{table_name}: {len(rows)} записей")
        
        users_count = await fetchval("SELECT COUNT(*) FROM users") or 0
        await status_msg.edit_text(f"✅ База данных восстановлена!\n\n👥 Пользователей: {users_count}")
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {e}")


async def backup_db_command_handler(message: Message):
    user_id = message.from_user.id
    if user_id != MAIN_ADMIN_ID:
        await message.answer("❌ Нет доступа")
        return
    status_msg = await message.answer("🔄 Создаю бэкап...")
    try:
        rows = await fetch("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
        tables = [row["tablename"] for row in rows]
        
        backup_data = {}
        for table in tables:
            columns_row = await fetchrow("""
                SELECT array_agg(column_name) as columns 
                FROM information_schema.columns 
                WHERE table_name = $1
            """, table)
            columns = columns_row["columns"] if columns_row else []
            
            rows_data = await fetch(f"SELECT * FROM {table}")
            data = [dict(row) for row in rows_data]
            
            backup_data[table] = {"columns": columns, "data": data}
        
        backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2, default=str)
        filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        await status_msg.delete()
        await message.answer_document(
            document=BytesIO(backup_json.encode('utf-8')),
            filename=filename,
            caption=f"✅ Бэкап базы данных"
        )
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {e}")


async def main():
    try:
        print("🔵 Запускаем main()...", file=sys.stderr)
        sys.stderr.flush()
        
        # Инициализируем пул соединений с PostgreSQL
        if not await init_db_pool():
            print("❌ Не удалось подключиться к PostgreSQL", file=sys.stderr)
            return
        print("✅ PostgreSQL пул соединений создан", file=sys.stderr)
        
        TEMP_DIR = "temp_videos"
        os.makedirs(TEMP_DIR, exist_ok=True)
        print(f"✅ Директория {TEMP_DIR} создана", file=sys.stderr)

        # Запускаем web сервер для healthcheck
        asyncio.create_task(run_web())

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
        
        dp.message.register(restore_db_handler, Command("restore"))
        dp.message.register(restore_from_json_handler, F.document)
        dp.message.register(backup_db_command_handler, Command("backup_db"))
        
        @dp.message(F.forward_from | F.forward_from_chat)
        async def block_forward(message: Message):
            await message.delete()

        print("✅ Бот запущен!", file=sys.stderr)
        sys.stderr.flush()
        
        await dp.start_polling(bot)
        
    except Exception as e:
        print(f"❌ ОШИБКА В MAIN: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        sys.stderr.flush()
        raise
    finally:
        await close_db_pool()
        print("👋 Пул соединений закрыт", file=sys.stderr)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 Бот остановлен", file=sys.stderr)
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise
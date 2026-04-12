import asyncio
import logging
import os
import sys
import traceback
import json
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.client.session.aiohttp import AiohttpSession

print("="*60, file=sys.stderr)
print("🚀 БОТ ЗАПУСКАЕТСЯ", file=sys.stderr)
print("="*60, file=sys.stderr)
sys.stderr.flush()

def global_exception_handler(exc_type, exc_value, exc_traceback):
    print("🔥 ГЛОБАЛЬНОЕ ИСКЛЮЧЕНИЕ:", file=sys.stderr)
    print("".join(traceback.format_exception(exc_type, exc_value, exc_traceback)), file=sys.stderr)
    sys.stderr.flush()

sys.excepthook = global_exception_handler

from config import BOT_TOKEN, MAIN_ADMIN_ID, BOT_USERNAME
from db import init_db
from handlers import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        return
    status_msg = await message.answer("🔄 Восстанавливаю базу данных...")
    try:
        from db import cursor, conn
        file = await message.bot.get_file(message.document.file_id)
        file_bytes = await message.bot.download_file(file.file_path)
        data = json.loads(file_bytes.read().decode('utf-8'))
        restored_tables = []
        for table_name, table_data in data.items():
            if table_name == "sqlite_sequence":
                continue
            columns = table_data["columns"]
            rows = table_data["data"]
            if not rows:
                continue
            cursor.execute(f"DELETE FROM {table_name}")
            placeholders = ','.join(['?'] * len(columns))
            for row in rows:
                values = [row.get(col) for col in columns]
                cursor.execute(f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})", values)
            restored_tables.append(f"{table_name}: {len(rows)} записей")
        conn.commit()
        cursor.execute("SELECT COUNT(*) FROM users")
        users_count = cursor.fetchone()[0]
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
        from db import cursor
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall() if row[0] != 'sqlite_sequence']
        backup_data = {}
        for table in tables:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in cursor.fetchall()]
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            data = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    row_dict[col] = row[i]
                data.append(row_dict)
            backup_data[table] = {"columns": columns, "data": data}
        from datetime import datetime
        backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2, default=str)
        from io import BytesIO
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
        
        init_db()
        print("✅ БД инициализирована", file=sys.stderr)
        
        TEMP_DIR = "temp_videos"
        os.makedirs(TEMP_DIR, exist_ok=True)
        print(f"✅ Директория {TEMP_DIR} создана", file=sys.stderr)

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

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("👋 Бот остановлен", file=sys.stderr)
    except Exception as e:
        print(f"❌ КРИТИЧЕСКАЯ ОШИБКА: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
        raise
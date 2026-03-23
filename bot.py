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

from config import BOT_TOKEN, MAIN_ADMIN_ID
from handlers import router
from db import cursor, conn, init_db

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

# ================= ВОССТАНОВЛЕНИЕ БАЗЫ ИЗ JSON =================
@router.message(Command("restore"))
async def restore_db(message: Message):
    user_id = message.from_user.id
    
    # Проверка на админа
    if user_id != MAIN_ADMIN_ID:
        await message.answer("❌ Нет доступа")
        return
    
    await message.answer("📤 Отправь JSON файл с бэкапом")

@router.message(F.document)
async def restore_from_json(message: Message):
    user_id = message.from_user.id
    
    # Проверка на админа
    if user_id != MAIN_ADMIN_ID:
        return
    
    if not message.document.file_name.endswith('.json'):
        return
    
    status_msg = await message.answer("🔄 Восстанавливаю базу данных...")
    
    try:
        # Скачиваем файл
        file = await message.bot.get_file(message.document.file_id)
        file_bytes = await message.bot.download_file(file.file_path)
        
        data = json.loads(file_bytes.read().decode('utf-8'))
        
        # Восстанавливаем базу
        restored_tables = []
        for table_name, table_data in data.items():
            if table_name == "sqlite_sequence":
                continue
            
            columns = table_data["columns"]
            rows = table_data["data"]
            
            if not rows:
                continue
            
            # Очищаем таблицу
            cursor.execute(f"DELETE FROM {table_name}")
            
            # Вставляем данные
            placeholders = ','.join(['?'] * len(columns))
            for row in rows:
                values = [row.get(col) for col in columns]
                cursor.execute(f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})", values)
            
            restored_tables.append(f"{table_name}: {len(rows)} записей")
        
        conn.commit()
        
        # Проверяем результат
        cursor.execute("SELECT COUNT(*) FROM users")
        users_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM videos")
        videos_count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM user_videos")
        watched_count = cursor.fetchone()[0]
        
        await status_msg.edit_text(
            f"✅ <b>База данных восстановлена!</b>\n\n"
            f"👥 Пользователей: {users_count}\n"
            f"🎥 Видео: {videos_count}\n"
            f"👀 Просмотров: {watched_count}\n\n"
            f"📊 Восстановлено таблиц: {len(restored_tables)}"
        )
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка при восстановлении: {e}")
        traceback.print_exc(file=sys.stderr)

# ================= ЭКСПОРТ БАЗЫ В JSON =================
@router.message(Command("backup_db"))
async def backup_db_command(message: Message):
    user_id = message.from_user.id
    
    # Проверка на админа
    if user_id != MAIN_ADMIN_ID:
        await message.answer("❌ Нет доступа")
        return
    
    status_msg = await message.answer("🔄 Создаю бэкап...")
    
    try:
        # Получаем все таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall() if row[0] != 'sqlite_sequence']
        
        backup_data = {}
        
        for table in tables:
            # Получаем структуру таблицы
            cursor.execute(f"PRAGMA table_info({table})")
            columns = [col[1] for col in cursor.fetchall()]
            
            # Получаем данные
            cursor.execute(f"SELECT * FROM {table}")
            rows = cursor.fetchall()
            
            # Преобразуем в словари
            data = []
            for row in rows:
                row_dict = {}
                for i, col in enumerate(columns):
                    row_dict[col] = row[i]
                data.append(row_dict)
            
            backup_data[table] = {
                "columns": columns,
                "data": data
            }
        
        # Сохраняем в JSON
        from datetime import datetime
        backup_json = json.dumps(backup_data, ensure_ascii=False, indent=2, default=str)
        
        from io import BytesIO
        filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        await status_msg.delete()
        await message.answer_document(
            document=BytesIO(backup_json.encode('utf-8')),
            filename=filename,
            caption=f"✅ Бэкап базы данных\n📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n👥 Пользователей: {len(backup_data.get('users', {}).get('data', []))}"
        )
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Ошибка: {e}")

# ================= ОСТАЛЬНЫЕ ХЭНДЛЕРЫ =================
# Здесь у тебя остальные хэндлеры из handlers.py

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
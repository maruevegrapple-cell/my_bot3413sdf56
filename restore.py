# restore.py
import json
import sqlite3
import asyncio
from aiogram import Router, F
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command

from db import cursor, conn
from config import MAIN_ADMIN_ID

router = Router()

@router.message(Command("restore"))
async def restore_db(message: Message):
    user_id = message.from_user.id
    
    # Проверяем админа
    if user_id != MAIN_ADMIN_ID:
        await message.answer("❌ Нет доступа")
        return
    
    await message.answer("📤 Отправь JSON файл с бэкапом")

@router.message(F.document)
async def restore_from_json(message: Message):
    user_id = message.from_user.id
    
    if user_id != MAIN_ADMIN_ID:
        return
    
    if not message.document.file_name.endswith('.json'):
        return
    
    status_msg = await message.answer("🔄 Восстанавливаю базу данных...")
    
    # Скачиваем файл
    file = await message.bot.get_file(message.document.file_id)
    file_bytes = await message.bot.download_file(file.file_path)
    
    data = json.loads(file_bytes.read().decode('utf-8'))
    
    # Восстанавливаем базу
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
    
    conn.commit()
    
    # Проверяем
    cursor.execute("SELECT COUNT(*) FROM users")
    users_count = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM videos")
    videos_count = cursor.fetchone()[0]
    
    await status_msg.edit_text(
        f"✅ База восстановлена!\n\n"
        f"👥 Пользователей: {users_count}\n"
        f"🎥 Видео: {videos_count}\n"
        f"📊 Просмотры сохранены"
    )
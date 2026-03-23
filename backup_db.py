import sqlite3
import os
import requests
import json
from datetime import datetime

# Путь к текущей базе данных
if os.environ.get('RAILWAY_ENVIRONMENT'):
    DB_PATH = "/data/database.db"
else:
    DB_PATH = "database.db"

print(f"🔍 Подключаюсь к базе: {DB_PATH}")

# Подключаемся к базе
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Получаем все таблицы
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()

print(f"📋 Найдено таблиц: {len(tables)}")

# Создаем дамп всех таблиц
backup_data = {}

for table in tables:
    table_name = table[0]
    print(f"📥 Читаю таблицу: {table_name}")
    
    # Получаем структуру таблицы
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = cursor.fetchall()
    column_names = [col[1] for col in columns]
    
    # Получаем данные
    cursor.execute(f"SELECT * FROM {table_name}")
    rows = cursor.fetchall()
    
    backup_data[table_name] = {
        "columns": column_names,
        "data": [list(row) for row in rows]
    }
    print(f"   ✅ {len(rows)} записей")

# Сохраняем дамп в файл
backup_file = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(backup_file, 'w', encoding='utf-8') as f:
    json.dump(backup_data, f, ensure_ascii=False, indent=2)

print(f"\n✅ Бэкап сохранен в: {backup_file}")
print(f"📦 Размер файла: {os.path.getsize(backup_file)} байт")

conn.close()
print("✅ Готово!")
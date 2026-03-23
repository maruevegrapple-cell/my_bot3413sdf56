import sqlite3
import json
import os

# Путь к базе на новом сервере
if os.environ.get('RAILWAY_ENVIRONMENT'):
    DB_PATH = "/data/database.db"
else:
    DB_PATH = "database.db"

print(f"🔍 Буду восстанавливать в: {DB_PATH}")

# Находим последний бэкап
import glob
backup_files = glob.glob("backup_*.json")
if not backup_files:
    print("❌ Нет файлов бэкапа!")
    exit()

backup_file = sorted(backup_files)[-1]
print(f"📂 Использую бэкап: {backup_file}")

# Загружаем дамп
with open(backup_file, 'r', encoding='utf-8') as f:
    backup_data = json.load(f)

# Подключаемся к базе
conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Восстанавливаем каждую таблицу
for table_name, table_data in backup_data.items():
    print(f"📤 Восстанавливаю таблицу: {table_name}")
    
    # Удаляем старую таблицу (если есть)
    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
    
    # Создаем таблицу заново
    columns = table_data["columns"]
    columns_sql = ", ".join([f'"{col}" TEXT' for col in columns])
    cursor.execute(f"CREATE TABLE {table_name} ({columns_sql})")
    
    # Вставляем данные
    data = table_data["data"]
    if data:
        placeholders = ",".join(["?"] * len(columns))
        for row in data:
            cursor.execute(f"INSERT INTO {table_name} VALUES ({placeholders})", row)
    
    print(f"   ✅ Восстановлено {len(data)} записей")

conn.commit()
conn.close()

print("\n✅ Восстановление завершено!")
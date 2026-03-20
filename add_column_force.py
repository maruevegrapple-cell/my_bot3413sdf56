import sqlite3
import os

if os.environ.get('RAILWAY_ENVIRONMENT'):
    DB_PATH = "/data/database.db"
else:
    DB_PATH = "database.db"

print(f"🔍 Подключаюсь к базе: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Проверяем, есть ли колонка
cursor.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()
has_column = any(col[1] == "pending_referrer_bonus" for col in columns)

if has_column:
    print("✅ Колонка pending_referrer_bonus уже существует")
else:
    print("⚠️ Добавляю колонку pending_referrer_bonus...")
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN pending_referrer_bonus INTEGER DEFAULT NULL")
        conn.commit()
        print("✅ Колонка успешно добавлена!")
    except Exception as e:
        print(f"❌ Ошибка: {e}")

conn.close()
print("Готово!")
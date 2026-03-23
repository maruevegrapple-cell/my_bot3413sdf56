import sqlite3
import os

# Определяем путь к базе данных
if os.environ.get('RAILWAY_ENVIRONMENT'):
    DB_PATH = "/data/database.db"
else:
    DB_PATH = "database.db"

print(f"🔍 Подключаюсь к базе: {DB_PATH}")

# Подключаемся к базе
conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

def delete_first_200_videos():
    """Удаляет первые 200 видео и связанные просмотры"""
    try:
        # Начинаем транзакцию
        cursor.execute("BEGIN TRANSACTION")
        
        # Получаем ID первых 200 видео
        cursor.execute("SELECT id FROM videos ORDER BY id ASC LIMIT 200")
        videos = cursor.fetchall()
        
        if not videos:
            print("❌ Нет видео для удаления")
            return
        
        video_ids = [v["id"] for v in videos]
        print(f"📋 Найдено видео для удаления: {len(video_ids)}")
        print(f"🆔 ID видео: {video_ids}")
        
        # Создаем строку с плейсхолдерами (?,?,?...)
        placeholders = ','.join(['?'] * len(video_ids))
        
        # 1. Сначала удаляем все просмотры этих видео
        cursor.execute(f"DELETE FROM user_videos WHERE video_id IN ({placeholders})", video_ids)
        deleted_views = cursor.rowcount
        print(f"✅ Удалено записей просмотров: {deleted_views}")
        
        # 2. Потом удаляем сами видео
        cursor.execute(f"DELETE FROM videos WHERE id IN ({placeholders})", video_ids)
        deleted_videos = cursor.rowcount
        print(f"✅ Удалено видео: {deleted_videos}")
        
        # 3. Опционально: сбрасываем счетчик автоинкремента
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='videos'")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='user_videos'")
        
        # Подтверждаем транзакцию
        conn.commit()
        print("✅ Транзакция подтверждена")
        
        # Проверяем остаток
        cursor.execute("SELECT COUNT(*) as count FROM videos")
        remaining = cursor.fetchone()["count"]
        print(f"📊 Осталось видео в базе: {remaining}")
        
    except Exception as e:
        # Если ошибка - откатываем все изменения
        conn.rollback()
        print(f"❌ ОШИБКА: {e}")
        print("🔄 Транзакция отка
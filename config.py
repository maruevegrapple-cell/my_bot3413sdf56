import os

# Просто берем токен из окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found!")

print(f"✅ Токен загружен: {BOT_TOKEN[:10]}...")
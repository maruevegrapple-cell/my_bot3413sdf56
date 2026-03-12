import os
from dotenv import load_dotenv
from db import get_main_admin_id

load_dotenv(override=True)

# ПРИНУДИТЕЛЬНАЯ ОЧИСТКА
os.environ.pop("BOT_TOKEN", None)
BOT_TOKEN = os.getenv("BOT_TOKEN")

print(f"!!! ИТОГОВЫЙ ТОКЕН: {BOT_TOKEN}")

# ================= BOT =================
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = os.getenv("BOT_USERNAME", "AnonkaBot34bot")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not found in environment variables")

# ================= ADMIN =================
MAIN_ADMIN_ID = get_main_admin_id()

# ================= CRYPTOBOT =================
CRYPTOBOT_API = os.getenv("CRYPTOBOT_API", "https://pay.crypt.bot/api")
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN", "543615:AAEUVnLPOYGnEc0gR93BpjsaDiql8TkSY6G")

# ================= ECONOMY =================
VIDEO_PRICE = int(os.getenv("VIDEO_PRICE", "1"))
BONUS_AMOUNT = int(os.getenv("BONUS_AMOUNT", "3"))
BONUS_COOLDOWN = int(os.getenv("BONUS_COOLDOWN", "3600"))
REF_BONUS = int(os.getenv("REF_BONUS", "6"))
REF_PERCENT = int(os.getenv("REF_PERCENT", "10"))
SUBSCRIBE_BONUS = int(os.getenv("SUBSCRIBE_BONUS", "6"))

# ================= CHANNEL =================
CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/+Dn7pNdHVYPM4ODgx")
CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003707313473"))
ANON_CHAT_LINK = os.getenv("ANON_CHAT_LINK", "https://t.me/anonaskbot?start=f21rnoq")

# ================= SPAM PROTECTION =================
SPAM_COOLDOWN = int(os.getenv("SPAM_COOLDOWN", "3"))

print("✅ Конфигурация загружена!")
print(f"🤖 BOT_TOKEN: {BOT_TOKEN[:10]}...")
print(f"👑 Главный админ: {MAIN_ADMIN_ID}")
print(f"📢 Канал: {CHANNEL_LINK}")
import os
from db import get_main_admin_id

# ================= BOT =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "AnonkaBot34bot")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables!")

# ================= ADMIN =================
MAIN_ADMIN_ID = get_main_admin_id()

# ================= CRYPTOBOT =================
CRYPTOBOT_API = os.environ.get("CRYPTOBOT_API", "https://pay.crypt.bot/api")
CRYPTOBOT_TOKEN = os.environ.get("CRYPTOBOT_TOKEN", "543615:AAEUVnLPOYGnEc0gR93BpjsaDiql8TkSY6G")

# ================= ECONOMY =================
VIDEO_PRICE = int(os.environ.get("VIDEO_PRICE", "1"))
BONUS_AMOUNT = int(os.environ.get("BONUS_AMOUNT", "3"))
BONUS_COOLDOWN = int(os.environ.get("BONUS_COOLDOWN", "3600"))
REF_BONUS = int(os.environ.get("REF_BONUS", "6"))
REF_PERCENT = int(os.environ.get("REF_PERCENT", "10"))
SUBSCRIBE_BONUS = int(os.environ.get("SUBSCRIBE_BONUS", "6"))

# ================= CHANNEL =================
CHANNEL_LINK = os.environ.get("CHANNEL_LINK", "https://t.me/+Dn7pNdHVYPM4ODgx")
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003707313473"))
ANON_CHAT_LINK = os.environ.get("ANON_CHAT_LINK", "https://t.me/anonaskbot?start=f21rnoq")

# ================= PRIVATE =================
PRIVATE_PRICE_USD = float(os.environ.get("PRIVATE_PRICE_USD", "5"))

# ================= SPAM PROTECTION =================
SPAM_COOLDOWN = int(os.environ.get("SPAM_COOLDOWN", "3"))

print("✅ Конфигурация загружена!")
print(f"🤖 BOT_TOKEN: {BOT_TOKEN[:10]}...")
print(f"👑 MAIN_ADMIN_ID: {MAIN_ADMIN_ID}")
print(f"📢 Канал: {CHANNEL_LINK}")
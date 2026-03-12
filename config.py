echo import os > config.py
echo from dotenv import load_dotenv >> config.py
echo from db import get_main_admin_id >> config.py
echo. >> config.py
echo load_dotenv(override=True) >> config.py
echo. >> config.py
echo # ================= BOT ================= >> config.py
echo BOT_TOKEN = os.getenv("BOT_TOKEN") >> config.py
echo BOT_USERNAME = os.getenv("BOT_USERNAME", "AnonkaBot34bot") >> config.py
echo. >> config.py
echo if not BOT_TOKEN: >> config.py
echo     raise RuntimeError("BOT_TOKEN not found in environment variables") >> config.py
echo. >> config.py
echo # ================= ADMIN ================= >> config.py
echo MAIN_ADMIN_ID = get_main_admin_id() >> config.py
echo. >> config.py
echo # ================= CRYPTOBOT ================= >> config.py
echo CRYPTOBOT_API = os.getenv("CRYPTOBOT_API", "https://pay.crypt.bot/api") >> config.py
echo CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN", "543615:AAEUVnLPOYGnEc0gR93BpjsaDiql8TkSY6G") >> config.py
echo. >> config.py
echo # ================= ECONOMY ================= >> config.py
echo VIDEO_PRICE = int(os.getenv("VIDEO_PRICE", "1")) >> config.py
echo BONUS_AMOUNT = int(os.getenv("BONUS_AMOUNT", "3")) >> config.py
echo BONUS_COOLDOWN = int(os.getenv("BONUS_COOLDOWN", "3600")) >> config.py
echo REF_BONUS = int(os.getenv("REF_BONUS", "6")) >> config.py
echo REF_PERCENT = int(os.getenv("REF_PERCENT", "10")) >> config.py
echo SUBSCRIBE_BONUS = int(os.getenv("SUBSCRIBE_BONUS", "6")) >> config.py
echo. >> config.py
echo # ================= CHANNEL ================= >> config.py
echo CHANNEL_LINK = os.getenv("CHANNEL_LINK", "https://t.me/+Dn7pNdHVYPM4ODgx") >> config.py
echo CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1003707313473")) >> config.py
echo ANON_CHAT_LINK = os.getenv("ANON_CHAT_LINK", "https://t.me/anonaskbot?start=f21rnoq") >> config.py
echo. >> config.py
echo # ================= SPAM PROTECTION ================= >> config.py
echo SPAM_COOLDOWN = int(os.getenv("SPAM_COOLDOWN", "3")) >> config.py
echo. >> config.py
echo print("✅ Конфигурация загружена!") >> config.py
echo print(f"🤖 BOT_TOKEN: {BOT_TOKEN[:10]}...") >> config.py
echo print(f"👑 Главный админ: {MAIN_ADMIN_ID}") >> config.py
echo print(f"📢 Канал: {CHANNEL_LINK}") >> config.py
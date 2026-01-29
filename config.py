import os

# ================= BOT =================
# токен берётся из Railway / env
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_USERNAME = "CandyStorm_bot"   # без @

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN not found in environment variables")


# ================= ADMIN =================
ADMIN_ID = 6067817907   # твой Telegram ID


# ================= CRYPTOBOT =================
# ❗ API URL НЕ МЕНЯЕТСЯ
CRYPTOBOT_API = "https://pay.crypt.bot/api"

# токен из env
CRYPTOBOT_TOKEN = os.getenv("CRYPTOBOT_TOKEN")

if not CRYPTOBOT_TOKEN:
    raise RuntimeError("CRYPTOBOT_TOKEN not found in environment variables")


# ================= ECONOMY =================
VIDEO_PRICE = 1        # цена видео в 🍬
BONUS_AMOUNT = 3       # бонус
BONUS_COOLDOWN = 3600  # сек
REF_BONUS = 3          # реф бонус


# ================= CHANNEL =================
RESERVE_CHANNEL = "https://t.me/+SI1UQQWZix1hZmEx"


# ================= PAY PACKS =================
# 🍬 начисления (функционал НЕ менялся)
PAY_TEST = 1     # 0.1 USDT → 1 🍬 (тест для админа)
PAY_10 = 10      # 1 USDT
PAY_50 = 50      # 5 USDT
PAY_100 = 100    # 10 USDT

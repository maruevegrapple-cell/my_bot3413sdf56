import os
from db import get_main_admin_id

# ================= BOT =================
BOT_TOKEN = os.environ.get("BOT_TOKEN")
BOT_USERNAME = os.environ.get("BOT_USERNAME", "Anonym315robot")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not found in environment variables!")

# ================= МОДЕРАТОР БОТ (АВТО-ПРИЁМ ЗАЯВОК) =================
BOT_TOKEN_MODERATOR = os.environ.get("BOT_TOKEN_MODERATOR", "8726714611:AAHsvM5h_cPI6l9-DOTe9DwGGGS0H6_qd68")

# ================= ADMIN =================
MAIN_ADMIN_ID = 951269458  # Твой ID

# ================= CRYPTOBOT =================
CRYPTOBOT_API = os.environ.get("CRYPTOBOT_API", "https://pay.crypt.bot/api")
CRYPTOBOT_TOKEN = os.environ.get("CRYPTOBOT_TOKEN", "567651:AAe2kYwaRB2CWYnWWjw5PumiCaESFq09erq")

# ================= XROCKET =================
XROCKET_API_KEY = os.environ.get("XROCKET_API_KEY", "b520de38f72563abe3bb14caa")
XROCKET_API_URL = os.environ.get("XROCKET_API_URL", "https://pay.xrocket.exchange")

# ================= LOLZ MARKET (СБП) =================
LOLZ_MERCHANT_SECRET_KEY = os.environ.get("LOLZ_MERCHANT_SECRET_KEY", "03e806e30159c90648e3fae47db6e95d8827e656715e87a7456b83b85796462d")
LOLZ_MERCHANT_ID = int(os.environ.get("LOLZ_MERCHANT_ID", "2321"))
LOLZ_API_URL = os.environ.get("LOLZ_API_URL", "https://prod-api.lzt.market/invoice")

# ================= ECONOMY =================
VIDEO_PRICE = int(os.environ.get("VIDEO_PRICE", "1"))
BONUS_AMOUNT = int(os.environ.get("BONUS_AMOUNT", "3"))
BONUS_COOLDOWN = 10800  # 3 часа
REF_BONUS = int(os.environ.get("REF_BONUS", "6"))
REF_PERCENT = int(os.environ.get("REF_PERCENT", "10"))
SUBSCRIBE_BONUS = int(os.environ.get("SUBSCRIBE_BONUS", "6"))

# ================= CHANNEL (ССЫЛКА НА КАНАЛ) =================
CHANNEL_LINK = "https://t.me/+gx5QzOgi-Ro3Nzdl"
CHANNEL_ID = int(os.environ.get("CHANNEL_ID", "-1003597249274"))
ANON_CHAT_LINK = os.environ.get("ANON_CHAT_LINK", "https://t.me/anonaskbot?start=f21rnoq")

# ================= PRIVATE (ПРИВАТКА) =================
PRIVATE_PRICE_USD = 15.0
PRIVATE_PRICE_STARS = 999

# ================= ПОДПИСКИ =================
SUBSCRIPTIONS = {
    "op": {
        "id": "op",
        "name": "💎 OP Статус",
        "stars": 350,
        "usd": 5.0,
        "days": 9,
        "candies_daily": 0,
        "benefits": "Безлимитный просмотр видео, приоритет на видео с высоким рейтингом, не будет низкорейтинговых видео"
    },
    "base": {
        "id": "base",
        "name": "🚀 Base Статус",
        "stars": 250,
        "usd": 3.7,
        "days": 9,
        "candies_daily": 70,
        "benefits": "70 Конфеток начисляются каждый день, 5 высокорейтинговых видео ежедневно"
    },
    "newbie": {
        "id": "newbie",
        "name": "😊 Newbie Статус",
        "stars": 150,
        "usd": 2.2,
        "days": 9,
        "candies_daily": 50,
        "benefits": "50 Конфеток начисляются каждый день"
    }
}

# ================= ЦЕНЫ НА КОНФЕТЫ =================
CANDY_PACKS = {
    20: {"usd": 0.20, "stars": 15},
    35: {"usd": 0.30, "stars": 25},
    70: {"usd": 0.50, "stars": 50},
    180: {"usd": 2.00, "stars": 100}
}

# ================= ИГРЫ (КАЗИНО) =================
GAMES = {
    "dice": {
        "name": "🎲 Кости",
        "emoji": "🎲",
        "min_bet": 1,
        "max_bet": 1000,
        "multiplier": 2,
        "win_chance": 1/6,
        "description": "Угадай число от 1 до 6!\nВыигрыш: x2 от ставки!"
    },
    "basketball": {
        "name": "🏀 Баскетбол",
        "emoji": "🏀",
        "min_bet": 1,
        "max_bet": 1000,
        "multiplier": 2,
        "win_chance": 0.3,
        "description": "Забрось мяч в корзину!\nВыигрыш: x2 от ставки!"
    },
    "football": {
        "name": "⚽️ Футбол",
        "emoji": "⚽️",
        "min_bet": 1,
        "max_bet": 1000,
        "multiplier": 2,
        "win_chance": 0.3,
        "description": "Забей гол!\nВыигрыш: x2 от ставки!"
    },
    "bowling": {
        "name": "🎳 Боулинг",
        "emoji": "🎳",
        "min_bet": 1,
        "max_bet": 1000,
        "multiplier": 2,
        "win_chance": 0.25,
        "description": "Собери страйк!\nВыигрыш: x2 от ставки!"
    }
}

# ================= СПОСОБЫ ОПЛАТЫ =================
PAYMENT_METHODS = {
    "sbp": {"name": "🏦 СБП (Lolz)", "enabled": False, "callback": "pay_sbp"},
    "cryptobot": {"name": "🪙 CryptoBot", "enabled": True, "callback": "pay_cryptobot"},
    "xrocket": {"name": "💎 xRocket", "enabled": True, "callback": "pay_xrocket"},
    "stars": {"name": "⭐️ Telegram Stars", "enabled": True, "callback": "pay_stars"}
}

# ================= СПАМ ЗАЩИТА =================
SPAM_COOLDOWN = int(os.environ.get("SPAM_COOLDOWN", "3"))

print("✅ Конфигурация загружена!")
print(f"🤖 BOT_TOKEN: {BOT_TOKEN[:10]}...")
print(f"🤖 MODERATOR_BOT_TOKEN: {BOT_TOKEN_MODERATOR[:10]}...")
print(f"👑 MAIN_ADMIN_ID: {MAIN_ADMIN_ID}")
print(f"📢 Ссылка на канал: {CHANNEL_LINK}")
print(f"📢 ID канала для проверки: {CHANNEL_ID}")
print(f"🎁 Бонус за подписку: {SUBSCRIBE_BONUS} 🍬")
print(f"⭐️ Оплата звездами: через {ANON_CHAT_LINK}")
print(f"💰 Оплата криптовалютой: через CryptoBot (токен обновлён)")
print(f"💎 Оплата xRocket: {'включена' if XROCKET_API_KEY else 'выключена'}")
print(f"🏦 Оплата СБП (Lolz): {'включена' if LOLZ_MERCHANT_SECRET_KEY else 'выключена'}")
print(f"🎮 Игры: загружено {len(GAMES)} игр")
print(f"⏱ Бонус кулдаун: 3 часа")
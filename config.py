import os

# ===== BOT =====
BOT_TOKEN = os.getenv("8405907915:AAHG8r-Dg0hrucmMe0G3rdQnpUQIXDJJFSc")

# ===== ADMINS =====
# Пример в Railway:
# ADMIN_IDS = 5925859280,987654321
ADMIN_IDS = list(
    map(
        int,
        os.getenv("ADMIN_IDS", "").split(",")
    )
)

# ===== ECONOMY =====
REF_BONUS = 3          # бонус за реферала
BONUS_AMOUNT = 3       # бонус по кнопке
BONUS_COOLDOWN = 3600  # 1 час (в секундах)

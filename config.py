import os

# === BOT ===
BOT_TOKEN = os.getenv("8405907915:AAHG8r-Dg0hrucmMe0G3rdQnpUQIXDJJFSc")

if not BOT_TOKEN:
    raise RuntimeError("❌ BOT_TOKEN is not set in Railway variables")

# === ADMINS ===
_raw_admins = os.getenv("5925859280", "8221665807")
ADMIN_IDS = [int(x) for x in _raw_admins.split(",") if x.strip().isdigit()]

# === REF SYSTEM ===
REF_BONUS = int(os.getenv("REF_BONUS", 3))
BONUS_AMOUNT = int(os.getenv("BONUS_AMOUNT", 3))
BONUS_COOLDOWN = int(os.getenv("BONUS_COOLDOWN", 3600))  # 24h

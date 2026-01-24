import os
from dotenv import load_dotenv

load_dotenv()

def get_env(name: str, default=None):
    value = os.getenv(name, default)
    if value is None:
        raise RuntimeError(f"❌ {name} is not set (.env or Railway Variables)")
    return value

# === REQUIRED ===
BOT_TOKEN = get_env("BOT_TOKEN")

# === ADMINS ===
ADMIN_IDS = [
    int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip().isdigit()
]

# === REF / BONUS ===
REF_BONUS = int(os.getenv("REF_BONUS", 3))
BONUS_AMOUNT = int(os.getenv("BONUS_AMOUNT", 3))
BONUS_COOLDOWN = int(os.getenv("BONUS_COOLDOWN", 3600))

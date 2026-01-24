import os
from dotenv import load_dotenv

# Загружаем .env если он есть
load_dotenv()

def get_env(name: str, required=True, default=None):
    value = os.getenv(name, default)
    if required and not value:
        raise RuntimeError(f"❌ {name} is not set (.env or Railway Variables)")
    return value

BOT_TOKEN = get_env("8405907915:AAHG8r-Dg0hrucmMe0G3rdQnpUQlXDJFSc")

# ADMIN_IDS = "5925859280,456,789"
_raw_admins = get_env("ADMIN_IDS", required=False, default="")
ADMIN_IDS = [
    int(x) for x in _raw_admins.split(",") if x.strip().isdigit()
]

# бонусы
REF_BONUS = 3
BONUS_AMOUNT = 3
BONUS_COOLDOWN = 3600  # 1 час

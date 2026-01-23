import os

BOT_TOKEN = os.getenv("8405907915:AAHG8r-Dg0hrucmMe0G3rdQnpUQIXDJJFSc")

ADMIN_IDS = [
    int(x) for x in os.getenv("5925859280", "987654321").split(",") if x.strip().isdigit()
]

REF_BONUS = int(os.getenv("REF_BONUS", 2))
BONUS_AMOUNT = int(os.getenv("BONUS_AMOUNT", 1))
BONUS_COOLDOWN = int(os.getenv("BONUS_COOLDOWN", 3600))

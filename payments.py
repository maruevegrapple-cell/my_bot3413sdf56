import requests
from config import CRYPTOBOT_API, CRYPTOBOT_TOKEN

HEADERS = {
    "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN,
    "Content-Type": "application/json"
}

def create_invoice(amount: float):
    """
    Создание инвойса CryptoBot
    amount — сумма в USDT
    """
    r = requests.post(
        f"{CRYPTOBOT_API}/createInvoice",
        headers=HEADERS,
        json={
            "asset": "USDT",
            "amount": amount,
            "description": "Покупка конфет",
            "allow_comments": False,
            "allow_anonymous": False
        },
        timeout=15
    )
    r.raise_for_status()
    return r.json()["result"]

def check_invoice(invoice_id: str) -> bool:
    """
    Проверка оплаты
    """
    r = requests.post(
        f"{CRYPTOBOT_API}/getInvoices",
        headers=HEADERS,
        json={
            "invoice_ids": [invoice_id]
        },
        timeout=15
    )
    r.raise_for_status()

    items = r.json()["result"]["items"]
    return bool(items) and items[0]["status"] == "paid"

import requests
from config import CRYPTOBOT_API, CRYPTOBOT_TOKEN
import logging

# Ссылка на бота
BOT_LINK = "https://t.me/AnonkaBot34bot"

HEADERS = {
    "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN,
    "Content-Type": "application/json"
}

def create_invoice(amount: float):
    """Создание счета для оплаты"""
    try:
        if not CRYPTOBOT_TOKEN:
            return {
                "invoice_id": f"test_{amount}",
                "pay_url": BOT_LINK,
                "status": "active"
            }
            
        r = requests.post(
            f"{CRYPTOBOT_API}/createInvoice",
            headers=HEADERS,
            json={
                "asset": "USDT",
                "amount": str(amount),
                "description": "Покупка конфет",
                "allow_comments": False,
                "allow_anonymous": False
            },
            timeout=15
        )
        r.raise_for_status()
        return r.json()["result"]
    except Exception as e:
        logging.error(f"Error creating invoice: {e}")
        return {
            "invoice_id": f"error_{amount}",
            "pay_url": BOT_LINK,
            "status": "error"
        }

def check_invoice(invoice_id: str) -> bool:
    """Проверка статуса оплаты"""
    try:
        if not CRYPTOBOT_TOKEN or invoice_id.startswith(("test_", "error_")):
            return True
            
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
    except Exception as e:
        logging.error(f"Error checking invoice: {e}")
        return True
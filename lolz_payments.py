import requests
import hashlib
import time
import logging
from config import LOLZ_MERCHANT_SECRET_KEY, LOLZ_MERCHANT_ID, BOT_USERNAME

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LOLZ_API_URL = "https://lzt.market/merchant/invoice"  # Другой эндпоинт


def create_lolz_invoice(amount_rub: float, order_id: str, user_id: int, username: str) -> dict:
    """
    Создание счета через Lolz Market для мерчанта
    """
    try:
        logger.info(f"💰 Lolz: create_invoice amount_rub={amount_rub}, order_id={order_id}")
        
        timestamp = int(time.time())
        
        # Формируем подпись
        sign_data = f"{LOLZ_MERCHANT_ID}{amount_rub}{order_id}{timestamp}{LOLZ_MERCHANT_SECRET_KEY}"
        sign = hashlib.md5(sign_data.encode()).hexdigest()
        
        bot_link = f"https://t.me/{BOT_USERNAME}"
        url_success = f"{bot_link}?start=payment_{order_id}"
        
        payload = {
            "merchant_id": LOLZ_MERCHANT_ID,
            "amount": amount_rub,
            "order_id": order_id,
            "description": f"Покупка конфет для @{username} (ID: {user_id})",
            "timestamp": timestamp,
            "sign": sign,
            "currency": "RUB",
            "url_success": url_success,
            "lifetime": 3600
        }
        
        print(f"🔵 Payload: {payload}")
        
        response = requests.post(
            LOLZ_API_URL,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=30
        )
        
        print(f"🔵 Status: {response.status_code}")
        print(f"🔵 Response: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            if result.get("status") == "success":
                return {
                    "status": "success",
                    "invoice_id": result.get("invoice_id", order_id),
                    "order_id": order_id,
                    "pay_url": result.get("payment_url", ""),
                    "amount_rub": amount_rub,
                    "method": "lolz"
                }
        
        return None
        
    except Exception as e:
        logger.error(f"Lolz error: {e}")
        return None


def check_lolz_payment(order_id: str) -> dict:
    """Проверка статуса оплаты через Lolz"""
    try:
        return {"status": "pending", "paid": False}
    except Exception as e:
        logger.error(f"Lolz check error: {e}")
        return {"status": "error", "paid": False}


print("✅ lolz_payments.py загружен")
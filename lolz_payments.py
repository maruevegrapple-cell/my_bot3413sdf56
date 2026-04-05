import requests
import logging
from datetime import datetime
from config import LOLZ_MERCHANT_SECRET_KEY, LOLZ_MERCHANT_ID, BOT_USERNAME

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LOLZ_API_URL = "https://prod-api.lzt.market/invoice"


def create_lolz_invoice(amount_rub: float, order_id: str, user_id: int, username: str) -> dict:
    """
    Создание счета через Lolz Market (СБП)
    Документация: https://lzt-market.readme.io/reference/paymentsinvoicecreate
    """
    try:
        logger.info(f"💰 Lolz: create_invoice amount_rub={amount_rub}, order_id={order_id}")
        
        if not LOLZ_MERCHANT_SECRET_KEY:
            logger.warning("⚠️ LOLZ_MERCHANT_SECRET_KEY не задан")
            return None
        
        if not LOLZ_MERCHANT_ID:
            logger.warning("⚠️ LOLZ_MERCHANT_ID не задан")
            return None
        
        bot_link = f"https://t.me/{BOT_USERNAME}"
        url_success = f"{bot_link}?start=payment_{order_id}"
        
        payload = {
            "currency": "rub",
            "amount": amount_rub,
            "payment_id": order_id,
            "comment": f"Покупка конфет для @{username} (ID: {user_id})",
            "url_success": url_success,
            "merchant_id": LOLZ_MERCHANT_ID,
            "telegram_id": user_id,
            "telegram_username": f"@{username}" if username else None,
            "lifetime": 3600
        }
        
        payload = {k: v for k, v in payload.items() if v is not None}
        
        headers = {
            "Authorization": f"Bearer {LOLZ_MERCHANT_SECRET_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        response = requests.post(
            LOLZ_API_URL,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            result = response.json()
            
            invoice_data = result.get("data", result) if isinstance(result, dict) else {}
            invoice_id = invoice_data.get("id")
            pay_url = invoice_data.get("url")
            
            if not pay_url and invoice_id:
                pay_url = f"https://lzt.market/invoice/{invoice_id}"
            
            if pay_url:
                return {
                    "status": "success",
                    "invoice_id": str(invoice_id) if invoice_id else order_id,
                    "order_id": order_id,
                    "pay_url": pay_url,
                    "amount_rub": amount_rub,
                    "expires_at": invoice_data.get("expires_at"),
                    "method": "lolz"
                }
        
        logger.error(f"Lolz error: {response.text if hasattr(response, 'text') else 'No response'}")
        return None
        
    except Exception as e:
        logger.error(f"Lolz create invoice error: {e}")
        return None


def check_lolz_payment(order_id: str) -> dict:
    """Проверка статуса оплаты через Lolz"""
    try:
        if not LOLZ_MERCHANT_SECRET_KEY:
            return {"status": "error", "paid": False}
        
        return {"status": "pending", "paid": False}
        
    except Exception as e:
        logger.error(f"Lolz check payment error: {e}")
        return {"status": "error", "paid": False}


print("✅ lolz_payments.py загружен")
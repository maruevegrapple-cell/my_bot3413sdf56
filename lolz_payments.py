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
        
        print(f"🔵 LOLZ_MERCHANT_SECRET_KEY = {LOLZ_MERCHANT_SECRET_KEY[:20] if LOLZ_MERCHANT_SECRET_KEY else 'None'}...")
        print(f"🔵 LOLZ_MERCHANT_ID = {LOLZ_MERCHANT_ID}")
        
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
        
        # Убираем None значения
        payload = {k: v for k, v in payload.items() if v is not None}
        
        # Пробуем разные варианты авторизации
        
        # ВАРИАНТ 1: Bearer (стандартный)
        headers = {
            "Authorization": f"Bearer {LOLZ_MERCHANT_SECRET_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # ВАРИАНТ 2: API-Key (раскомментировать и закомментировать вариант 1)
        # headers = {
        #     "API-Key": LOLZ_MERCHANT_SECRET_KEY,
        #     "Content-Type": "application/json",
        #     "Accept": "application/json"
        # }
        
        # ВАРИАНТ 3: X-API-Key (раскомментировать и закомментировать вариант 1)
        # headers = {
        #     "X-API-Key": LOLZ_MERCHANT_SECRET_KEY,
        #     "Content-Type": "application/json",
        #     "Accept": "application/json"
        # }
        
        # ВАРИАНТ 4: Только токен (без Bearer)
        # headers = {
        #     "Authorization": LOLZ_MERCHANT_SECRET_KEY,
        #     "Content-Type": "application/json",
        #     "Accept": "application/json"
        # }
        
        print(f"🔵 headers: {headers}")
        print(f"🔵 payload: {payload}")
        
        response = requests.post(
            LOLZ_API_URL,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        print(f"🔵 response status: {response.status_code}")
        print(f"🔵 response text: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"🔵 result: {result}")
            
            # API может вернуть данные в поле "data" или прямо в корне
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
            else:
                # Если нет pay_url, но есть invoice_id, возвращаем его
                if invoice_id:
                    return {
                        "status": "success",
                        "invoice_id": str(invoice_id),
                        "order_id": order_id,
                        "pay_url": f"https://lzt.market/invoice/{invoice_id}",
                        "amount_rub": amount_rub,
                        "method": "lolz"
                    }
        
        # Если ответ не 200, пробуем прочитать ошибку
        error_text = response.text if hasattr(response, 'text') else 'No response'
        logger.error(f"Lolz error: {error_text}")
        
        # Пробуем распарсить ошибку
        try:
            error_json = response.json()
            print(f"🔵 error_json: {error_json}")
        except:
            pass
        
        return None
        
    except Exception as e:
        logger.error(f"Lolz create invoice error: {e}")
        print(f"🔵 Exception: {e}")
        import traceback
        traceback.print_exc()
        return None


def check_lolz_payment(order_id: str) -> dict:
    """
    Проверка статуса оплаты через Lolz
    Документация: https://lzt-market.readme.io/reference/paymentsinvoiceget
    """
    try:
        if not LOLZ_MERCHANT_SECRET_KEY:
            return {"status": "error", "paid": False}
        
        headers = {
            "Authorization": f"Bearer {LOLZ_MERCHANT_SECRET_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Получаем инвойс по payment_id
        response = requests.get(
            f"{LOLZ_API_URL}?payment_id={order_id}",
            headers=headers,
            timeout=15
        )
        
        print(f"🔵 check response status: {response.status_code}")
        print(f"🔵 check response text: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            if result:
                status = result.get("status", "")
                is_paid = status == "paid"
                return {
                    "status": "paid" if is_paid else "pending",
                    "paid": is_paid,
                    "invoice_id": result.get("id"),
                    "amount": result.get("amount")
                }
        
        return {"status": "pending", "paid": False}
        
    except Exception as e:
        logger.error(f"Lolz check payment error: {e}")
        print(f"🔵 check Exception: {e}")
        return {"status": "error", "paid": False}


print("✅ lolz_payments.py загружен")
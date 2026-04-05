import requests
import logging
from config import LOLZ_MERCHANT_SECRET_KEY, LOLZ_MERCHANT_ID, BOT_USERNAME

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Правильный эндпоинт из документации
LOLZ_API_URL = "https://prod-api.lzt.market/invoice"


def create_lolz_invoice(amount_rub: float, order_id: str, user_id: int, username: str) -> dict:
    """
    Создание счета через Lolz Market API
    Документация: https://lzt-market.readme.io/reference/paymentsinvoicecreate
    """
    try:
        logger.info(f"💰 Lolz: create_invoice amount_rub={amount_rub}, order_id={order_id}")
        
        if not LOLZ_MERCHANT_SECRET_KEY or not LOLZ_MERCHANT_ID:
            logger.error("❌ LOLZ_MERCHANT_SECRET_KEY или LOLZ_MERCHANT_ID не заданы")
            return None
        
        bot_link = f"https://t.me/{BOT_USERNAME}"
        url_success = f"{bot_link}?start=payment_{order_id}"
        
        # Формируем payload строго по документации
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
        
        # ПРАВИЛЬНЫЙ заголовок авторизации
        headers = {
            "Authorization": f"Bearer {LOLZ_MERCHANT_SECRET_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        print(f"🔵 Отправка запроса на {LOLZ_API_URL}")
        print(f"🔵 Headers: Authorization: Bearer {LOLZ_MERCHANT_SECRET_KEY[:10]}...")
        print(f"🔵 Payload: {payload}")
        
        response = requests.post(
            LOLZ_API_URL,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        print(f"🔵 Статус ответа: {response.status_code}")
        print(f"🔵 Тело ответа: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            
            # В ответе может быть поле "data" или сам объект
            invoice_data = result.get("data", result)
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
                    "method": "lolz"
                }
            else:
                logger.error(f"Не удалось получить pay_url из ответа: {result}")
                return None
        
        # Обработка ошибок
        if response.status_code == 401:
            logger.error("❌ Ошибка авторизации: неверный токен. Проверьте LOLZ_MERCHANT_SECRET_KEY")
        elif response.status_code == 422:
            logger.error(f"❌ Ошибка валидации данных: {response.text}")
        else:
            logger.error(f"❌ Ошибка Lolz API: {response.status_code} - {response.text}")
        
        return None
        
    except Exception as e:
        logger.error(f"❌ Исключение при создании инвойса Lolz: {e}")
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
            "Accept": "application/json"
        }
        
        # Получаем инвойс по payment_id
        response = requests.get(
            f"{LOLZ_API_URL}?payment_id={order_id}",
            headers=headers,
            timeout=15
        )
        
        print(f"🔵 Проверка статуса: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            status = result.get("status", "")
            is_paid = status == "paid"
            return {
                "status": "paid" if is_paid else "pending",
                "paid": is_paid,
                "invoice_data": result
            }
        
        return {"status": "pending", "paid": False}
        
    except Exception as e:
        logger.error(f"❌ Ошибка проверки платежа Lolz: {e}")
        return {"status": "error", "paid": False}


print("✅ lolz_payments.py загружен")
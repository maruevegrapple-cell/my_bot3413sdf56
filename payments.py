import requests
import logging
from datetime import datetime
from config import CRYPTOBOT_API, CRYPTOBOT_TOKEN, XROCKET_API_KEY, LOLZ_MERCHANT_SECRET_KEY, LOLZ_MERCHANT_ID

# Ссылка на бота
BOT_LINK = "https://t.me/AnonkaBot34bot"

# CryptoBot headers
CRYPTOBOT_HEADERS = {
    "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN,
    "Content-Type": "application/json"
}

# xRocket headers
XROCKET_API_URL = "https://pay.xrocket.tg"
XROCKET_HEADERS = {
    "Rocket-Pay-Key": XROCKET_API_KEY,
    "Content-Type": "application/json"
}

# Lolz Market API
LOLZ_API_URL = "https://prod-api.lzt.market/invoice"
LOLZ_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json"
}

# ДОСТУПНЫЕ ВАЛЮТЫ ДЛЯ CRYPTOBOT
CRYPTOBOT_ASSETS = ["BTC", "TON", "ETH", "USDT", "USDC", "BNB", "TRX", "LTC", "SOL"]

# ДОСТУПНЫЕ ВАЛЮТЫ ДЛЯ XROCKET
XROCKET_ASSETS = ["USDT", "TONCOIN"]

# Курсы для xRocket
XROCKET_RATES = {
    "USDT": 1.0,
    "TONCOIN": 5.5
}

# Общий список для выбора пользователем
AVAILABLE_ASSETS = ["BTC", "TON", "ETH", "USDT", "USDC", "BNB", "TRX", "LTC", "SOL"]


def get_asset_icon(asset: str) -> str:
    """Иконки для валют"""
    icons = {
        "BTC": "₿",
        "TON": "💎", 
        "TONCOIN": "💎",
        "ETH": "Ξ",
        "USDT": "💵",
        "USDC": "💲", 
        "BNB": "🔶",
        "TRX": "🌞",
        "SOL": "◎",
        "LTC": "🟣",
        "RUB": "₽"
    }
    return icons.get(asset, "🪙")


def get_exchange_rates():
    """Получение актуальных курсов валют к USD через CryptoBot API"""
    try:
        logging.info("🔍 get_exchange_rates: Запрашиваем курсы...")
        
        if not CRYPTOBOT_TOKEN:
            logging.warning("⚠️ CRYPTOBOT_TOKEN не задан, использую тестовые курсы")
            return _get_fallback_rates()
        
        r = requests.post(
            f"{CRYPTOBOT_API}/getExchangeRates",
            headers=CRYPTOBOT_HEADERS,
            json={},
            timeout=15
        )
        
        logging.info(f"🔍 Статус ответа: {r.status_code}")
        r.raise_for_status()
        data = r.json()
        
        rates = {}
        for item in data["result"]:
            if item["is_valid"] and item["is_crypto"] and not item["is_fiat"]:
                if item["target"] == "USD":
                    crypto = item["source"]
                    rate = float(item["rate"])
                    rates[crypto] = rate
                    logging.info(f"🔍 Курс: 1 {crypto} = ${rate}")
        
        logging.info(f"🔍 Итоговые курсы: {rates}")
        return rates
    except Exception as e:
        logging.error(f"❌ Error getting exchange rates: {e}")
        return _get_fallback_rates()


def _get_fallback_rates():
    """Fallback курсы при ошибке API"""
    return {
        "BTC": 65000.0,
        "TON": 5.5,
        "ETH": 3200.0,
        "USDT": 1.0,
        "USDC": 1.0,
        "BNB": 580.0,
        "TRX": 0.11,
        "SOL": 150.0,
        "LTC": 85.0
    }


def convert_usd_to_crypto(amount_usd: float, asset: str, rates: dict = None) -> tuple:
    """Конвертирует USD в криптовалюту, возвращает (crypto_amount, rate)"""
    if rates is None:
        rates = get_exchange_rates()
    
    if asset == "USDT" or asset == "USDC":
        return amount_usd, 1.0
    
    rate = rates.get(asset)
    if not rate:
        fallback = _get_fallback_rates()
        rate = fallback.get(asset, 1.0)
    
    crypto_amount = amount_usd / rate
    
    # Округление
    if asset in ["BTC", "ETH", "BNB", "SOL"]:
        crypto_amount = round(crypto_amount, 8)
    elif asset in ["TON"]:
        crypto_amount = round(crypto_amount, 4)
    else:
        crypto_amount = round(crypto_amount, 2)
    
    return crypto_amount, rate


# ================= CRYPTOBOT =================
def create_cryptobot_invoice(amount_usd: float, asset: str = "USDT"):
    """Создание счета через CryptoBot"""
    try:
        logging.info(f"💰 CryptoBot: create_invoice amount_usd={amount_usd}, asset={asset}")
        
        if not CRYPTOBOT_TOKEN:
            logging.warning("⚠️ CRYPTOBOT_TOKEN не задан, возвращаю тестовый инвойс")
            return {
                "invoice_id": f"test_{amount_usd}_{asset}",
                "pay_url": BOT_LINK,
                "status": "active",
                "asset": asset,
                "amount": str(amount_usd),
                "crypto_amount": amount_usd,
                "usd_amount": amount_usd,
                "rate": None,
                "method": "cryptobot"
            }
        
        rates = get_exchange_rates()
        crypto_amount, rate = convert_usd_to_crypto(amount_usd, asset, rates)
        
        payload = {
            "asset": asset,
            "amount": str(crypto_amount),
            "description": f"Покупка конфет",
            "allow_comments": False,
            "allow_anonymous": False,
            "expires_in": 3600
        }
        logging.info(f"💰 CryptoBot payload: {payload}")
        
        r = requests.post(
            f"{CRYPTOBOT_API}/createInvoice",
            headers=CRYPTOBOT_HEADERS,
            json=payload,
            timeout=15
        )
        
        r.raise_for_status()
        result = r.json()["result"]
        
        result["asset"] = asset
        result["crypto_amount"] = crypto_amount
        result["usd_amount"] = amount_usd
        result["rate"] = rate
        result["method"] = "cryptobot"
        
        return result
    except Exception as e:
        logging.error(f"❌ CryptoBot create_invoice error: {e}")
        return {
            "invoice_id": f"error_{amount_usd}_{asset}",
            "pay_url": BOT_LINK,
            "status": "error",
            "asset": asset,
            "amount": str(amount_usd),
            "crypto_amount": amount_usd,
            "usd_amount": amount_usd,
            "rate": None,
            "method": "cryptobot"
        }


def check_cryptobot_invoice(invoice_id: str) -> dict:
    """Проверка статуса оплаты через CryptoBot"""
    try:
        if not CRYPTOBOT_TOKEN:
            if invoice_id.startswith("test_"):
                return {"status": "paid", "paid": True}
            return {"status": "error", "paid": False}
        
        if invoice_id.startswith("error_"):
            return {"status": "error", "paid": False}
        
        r = requests.post(
            f"{CRYPTOBOT_API}/getInvoices",
            headers=CRYPTOBOT_HEADERS,
            json={"invoice_ids": [invoice_id]},
            timeout=15
        )
        r.raise_for_status()
        items = r.json()["result"]["items"]
        if items and items[0]["status"] == "paid":
            return {
                "status": "paid",
                "paid": True,
                "asset": items[0].get("asset"),
                "amount": float(items[0].get("amount", 0))
            }
        return {"status": "active", "paid": False}
    except Exception as e:
        logging.error(f"Error checking CryptoBot invoice: {e}")
        return {"status": "error", "paid": False}


# ================= XROCKET =================
def create_xrocket_invoice(amount_usd: float, currency: str = "USDT"):
    """Создание счета через xRocket"""
    try:
        logging.info(f"💰 xRocket: create_invoice amount_usd={amount_usd}, currency={currency}")
        
        if not XROCKET_API_KEY:
            logging.warning("⚠️ XROCKET_API_KEY не задан")
            return None
        
        # Конвертируем USD в выбранную валюту
        if currency == "USDT":
            crypto_amount = amount_usd
        elif currency == "TONCOIN":
            rate = XROCKET_RATES.get("TONCOIN", 5.5)
            crypto_amount = amount_usd / rate
            crypto_amount = round(crypto_amount, 4)
        else:
            crypto_amount = amount_usd
        
        payload = {
            "amount": crypto_amount,
            "currency": currency,
            "numPayments": 1,
            "expiredIn": 3600
        }
        
        logging.info(f"💰 xRocket payload: {payload}")
        
        response = requests.post(
            f"{XROCKET_API_URL}/tg-invoices",
            headers=XROCKET_HEADERS,
            json=payload,
            timeout=15
        )
        
        logging.info(f"💰 xRocket response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logging.info(f"💰 xRocket response: {result}")
            
            if result.get("id"):
                return {
                    "invoice_id": str(result["id"]),
                    "pay_url": result.get("link") or f"https://t.me/xrocket?start=inv_{result['id']}",
                    "status": "active",
                    "asset": currency,
                    "crypto_amount": crypto_amount,
                    "usd_amount": amount_usd,
                    "method": "xrocket"
                }
        
        logging.error(f"xRocket error: {response.text}")
        return None
        
    except Exception as e:
        logging.error(f"xRocket error: {e}")
        return None


def check_xrocket_invoice(invoice_id: str) -> dict:
    """Проверка статуса оплаты через xRocket"""
    try:
        if not XROCKET_API_KEY:
            return {"status": "error", "paid": False}
        
        response = requests.get(
            f"{XROCKET_API_URL}/tg-invoices/{invoice_id}",
            headers=XROCKET_HEADERS,
            timeout=15
        )
        
        if response.status_code == 200:
            result = response.json()
            
            status = result.get("status", "")
            is_paid = status == "paid"
            
            payments = result.get("payments", [])
            for payment in payments:
                if payment.get("paid"):
                    is_paid = True
                    break
            
            return {
                "status": "paid" if is_paid else "active",
                "paid": is_paid,
                "asset": result.get("currency"),
                "amount": float(result.get("amount", 0))
            }
        
        return {"status": "active", "paid": False}
    except Exception as e:
        logging.error(f"Error checking xRocket invoice: {e}")
        return {"status": "error", "paid": False}


# ================= LOLZ MARKET (СБП) =================
def create_lolz_invoice(amount_rub: float, order_id: str, user_id: int, username: str) -> dict:
    """
    Создание счета через Lolz Market (СБП)
    Документация: https://lzt-market.readme.io/reference/paymentsinvoicecreate
    """
    try:
        logging.info(f"💰 Lolz: create_invoice amount_rub={amount_rub}, order_id={order_id}")
        
        if not LOLZ_MERCHANT_SECRET_KEY:
            logging.warning("⚠️ LOLZ_MERCHANT_SECRET_KEY не задан")
            return None
        
        if not LOLZ_MERCHANT_ID:
            logging.warning("⚠️ LOLZ_MERCHANT_ID не задан")
            return None
        
        # Формируем URL для редиректа после оплаты
        url_success = f"{BOT_LINK}?start=payment_{order_id}"
        
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
        
        headers = {
            "Authorization": f"Bearer {LOLZ_MERCHANT_SECRET_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        logging.info(f"💰 Lolz payload: {payload}")
        
        response = requests.post(
            LOLZ_API_URL,
            json=payload,
            headers=headers,
            timeout=30
        )
        
        logging.info(f"💰 Lolz response status: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logging.info(f"💰 Lolz response: {result}")
            
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
        
        logging.error(f"Lolz error: {response.text if hasattr(response, 'text') else 'No response'}")
        return None
        
    except Exception as e:
        logging.error(f"Lolz create invoice error: {e}")
        return None


def check_lolz_invoice(order_id: str) -> dict:
    """
    Проверка статуса оплаты через Lolz
    Для полной проверки нужен webhook, пока возвращаем pending
    """
    try:
        if not LOLZ_MERCHANT_SECRET_KEY:
            return {"status": "error", "paid": False}
        
        # TODO: Реализовать полноценную проверку через API Lolz
        # Пока возвращаем pending - пользователь должен нажать кнопку проверки
        return {"status": "pending", "paid": False}
        
    except Exception as e:
        logging.error(f"Lolz check payment error: {e}")
        return {"status": "error", "paid": False}


# ================= УНИВЕРСАЛЬНЫЕ ФУНКЦИИ =================
def create_invoice(amount_usd: float, asset: str = "USDT", method: str = "cryptobot"):
    """Универсальная функция создания инвойса"""
    if method == "cryptobot":
        return create_cryptobot_invoice(amount_usd, asset)
    elif method == "xrocket":
        return create_xrocket_invoice(amount_usd, asset)
    else:
        return None


def check_invoice(invoice_id: str, method: str = "cryptobot") -> dict:
    """Универсальная функция проверки инвойса"""
    if method == "cryptobot":
        return check_cryptobot_invoice(invoice_id)
    elif method == "xrocket":
        return check_xrocket_invoice(invoice_id)
    else:
        return {"status": "error", "paid": False}


# ================= ЦЕНЫ НА ПАКИ =================
PACKS = {
    20: {"usd": 0.20, "stars": 15},
    35: {"usd": 0.30, "stars": 25},
    70: {"usd": 0.50, "stars": 50},
    180: {"usd": 2.00, "stars": 100}
}

def get_pack_info(amount: int):
    """Возвращает информацию о паке"""
    return PACKS.get(amount)


# ================= ЗАЯВКИ НА ОПЛАТУ ЗВЕЗДАМИ =================
stars_payment_requests = {}
_stars_request_counter = 0

def add_stars_payment_request(user_id: int, username: str, pack_amount: int, stars_amount: int, message_id: int = None):
    """Добавить заявку на оплату звездами"""
    global _stars_request_counter
    _stars_request_counter += 1
    request_id = _stars_request_counter
    stars_payment_requests[request_id] = {
        "user_id": user_id,
        "username": username,
        "pack_amount": pack_amount,
        "stars_amount": stars_amount,
        "message_id": message_id,
        "status": "pending",
        "created_at": datetime.now()
    }
    return request_id

def get_stars_payment_request(request_id: int):
    """Получить заявку по ID"""
    return stars_payment_requests.get(request_id)

def approve_stars_payment(request_id: int) -> bool:
    """Одобрить заявку"""
    if request_id in stars_payment_requests:
        stars_payment_requests[request_id]["status"] = "approved"
        return True
    return False

def reject_stars_payment(request_id: int) -> bool:
    """Отклонить заявку"""
    if request_id in stars_payment_requests:
        stars_payment_requests[request_id]["status"] = "rejected"
        return True
    return False


print("✅ payments.py загружен")
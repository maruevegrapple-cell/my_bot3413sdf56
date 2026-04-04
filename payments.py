import requests
import logging
from datetime import datetime
from config import CRYPTOBOT_API, CRYPTOBOT_TOKEN, XROCKET_API_KEY

# Ссылка на бота
BOT_LINK = "https://t.me/AnonkaBot34bot"

# CryptoBot headers
CRYPTOBOT_HEADERS = {
    "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN,
    "Content-Type": "application/json"
}

# xRocket headers
XROCKET_API_URL = "https://pay.xrocket.exchange"
XROCKET_HEADERS = {
    "Rocket-Pay-Key": XROCKET_API_KEY,
    "Content-Type": "application/json"
}

# ДОСТУПНЫЕ ВАЛЮТЫ ДЛЯ CRYPTOBOT
CRYPTOBOT_ASSETS = ["BTC", "TON", "ETH", "USDT", "USDC", "BNB", "TRX", "LTC", "SOL"]

# ДОСТУПНЫЕ ВАЛЮТЫ ДЛЯ XROCKET (только ходовые)
XROCKET_ASSETS = ["USDT", "TON"]

# Курсы для xRocket
XROCKET_RATES = {
    "USDT": 1.0,
    "TON": 5.5
}

# Общий список для выбора пользователем
AVAILABLE_ASSETS = ["BTC", "TON", "ETH", "USDT", "USDC", "BNB", "TRX", "LTC", "SOL"]

def get_asset_icon(asset: str) -> str:
    """Иконки для валют"""
    icons = {
        "BTC": "₿",
        "TON": "💎", 
        "ETH": "Ξ",
        "USDT": "💵",
        "USDC": "💲", 
        "BNB": "🔶",
        "TRX": "🌞",
        "SOL": "◎",
        "LTC": "🟣"
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
def create_xrocket_invoice(amount_usd: float, asset: str = "USDT"):
    """Создание счета через xRocket"""
    try:
        logging.info(f"💰 xRocket: create_invoice amount_usd={amount_usd}, asset={asset}")
        
        if not XROCKET_API_KEY:
            logging.warning("⚠️ XROCKET_API_KEY не задан, возвращаю тестовый инвойс")
            return {
                "invoice_id": f"xr_test_{amount_usd}_{asset}",
                "pay_url": BOT_LINK,
                "status": "active",
                "asset": asset,
                "crypto_amount": amount_usd,
                "usd_amount": amount_usd,
                "method": "xrocket"
            }
        
        # Конвертируем USD в выбранную валюту
        if asset == "USDT":
            crypto_amount = amount_usd
            rate = 1.0
        elif asset == "TON":
            rate = XROCKET_RATES.get("TON", 5.5)
            crypto_amount = amount_usd / rate
            crypto_amount = round(crypto_amount, 4)
        else:
            crypto_amount = amount_usd
            rate = 1.0
        
        payload = {
            "amount": str(crypto_amount),
            "asset": asset,
            "numPayments": 1
        }
        logging.info(f"💰 xRocket payload: {payload}")
        
        r = requests.post(
            f"{XROCKET_API_URL}/tg-invoices",
            headers=XROCKET_HEADERS,
            json=payload,
            timeout=15
        )
        
        logging.info(f"💰 xRocket response status: {r.status_code}")
        result = r.json()
        logging.info(f"💰 xRocket response: {result}")
        
        if result.get("id"):
            return {
                "invoice_id": str(result["id"]),
                "pay_url": result["link"],
                "status": result.get("status", "active"),
                "asset": asset,
                "crypto_amount": crypto_amount,
                "usd_amount": amount_usd,
                "rate": rate,
                "method": "xrocket"
            }
        else:
            logging.error(f"xRocket error: {result}")
            return {
                "invoice_id": f"xr_error_{amount_usd}_{asset}",
                "pay_url": BOT_LINK,
                "status": "error",
                "asset": asset,
                "crypto_amount": crypto_amount,
                "usd_amount": amount_usd,
                "rate": rate,
                "method": "xrocket"
            }
    except Exception as e:
        logging.error(f"❌ xRocket create_invoice error: {e}")
        return {
            "invoice_id": f"xr_error_{amount_usd}_{asset}",
            "pay_url": BOT_LINK,
            "status": "error",
            "asset": asset,
            "crypto_amount": amount_usd,
            "usd_amount": amount_usd,
            "rate": None,
            "method": "xrocket"
        }


def check_xrocket_invoice(invoice_id: str) -> dict:
    """Проверка статуса оплаты через xRocket"""
    try:
        if not XROCKET_API_KEY:
            if invoice_id.startswith("xr_test_"):
                return {"status": "paid", "paid": True}
            return {"status": "error", "paid": False}
        
        if invoice_id.startswith("xr_error_"):
            return {"status": "error", "paid": False}
        
        r = requests.get(
            f"{XROCKET_API_URL}/tg-invoices/{invoice_id}",
            headers=XROCKET_HEADERS,
            timeout=15
        )
        r.raise_for_status()
        result = r.json()
        
        if result.get("id"):
            payments = result.get("payments", [])
            is_paid = any(p.get("paid", False) for p in payments)
            return {
                "status": "paid" if is_paid else "active",
                "paid": is_paid,
                "asset": result.get("asset"),
                "amount": float(result.get("amount", 0))
            }
        return {"status": "active", "paid": False}
    except Exception as e:
        logging.error(f"Error checking xRocket invoice: {e}")
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


# ================= ЗАЯВКИ НА ОПЛАТУ ЗВЕЗДАМИ (ВРЕМЕННОЕ ХРАНИЛИЩЕ) =================
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


print("✅ payments.py загручен")
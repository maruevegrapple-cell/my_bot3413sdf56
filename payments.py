import requests
from config import CRYPTOBOT_API, CRYPTOBOT_TOKEN
import logging

# Ссылка на бота
BOT_LINK = "https://t.me/AnonkaBot34bot"

HEADERS = {
    "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN,
    "Content-Type": "application/json"
}

# ДОСТУПНЫЕ ВАЛЮТЫ (BUSD удалён)
AVAILABLE_ASSETS = ["BTC", "TON", "ETH", "USDT", "USDC", "BNB", "TRX", "SOL"]

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
        "SOL": "◎"
    }
    return icons.get(asset, "🪙")

def get_exchange_rates():
    """Получение актуальных курсов валют к USD"""
    try:
        logging.info("🔍 get_exchange_rates: Запрашиваем курсы...")
        
        if not CRYPTOBOT_TOKEN:
            logging.warning("⚠️ CRYPTOBOT_TOKEN не задан, использую тестовые курсы")
            return {
                "BTC": 65000.0,
                "TON": 5.5,
                "ETH": 3500.0,
                "USDT": 1.0,
                "USDC": 1.0,
                "BNB": 500.0,
                "TRX": 0.12,
                "SOL": 150.0
            }
        
        logging.info(f"🔍 Отправляем запрос к {CRYPTOBOT_API}/getExchangeRates")
        
        r = requests.post(
            f"{CRYPTOBOT_API}/getExchangeRates",
            headers=HEADERS,
            json={},
            timeout=15
        )
        
        logging.info(f"🔍 Статус ответа: {r.status_code}")
        
        r.raise_for_status()
        data = r.json()
        
        rates = {}
        
        # ПРОХОДИМ ПО ВСЕМ ЭЛЕМЕНТАМ И СОБИРАЕМ КУРСЫ КРИПТОВАЛЮТ К USD
        for item in data["result"]:
            if item["is_valid"] and item["is_crypto"] and not item["is_fiat"]:
                # Для каждой криптовалюты ищем пару с USD
                if item["target"] == "USD":
                    # Это курс: 1 source = X USD
                    crypto = item["source"]
                    rate = float(item["rate"])
                    rates[crypto] = rate
                    logging.info(f"🔍 Курс: 1 {crypto} = ${rate}")
        
        logging.info(f"🔍 Итоговые курсы: {rates}")
        return rates
    except Exception as e:
        logging.error(f"❌ Error getting exchange rates: {e}")
        import traceback
        logging.error(traceback.format_exc())
        # Возвращаем заглушку, чтобы бот не падал
        return {
            "BTC": 65000.0,
            "TON": 5.5,
            "ETH": 3500.0,
            "USDT": 1.0,
            "USDC": 1.0,
            "BNB": 500.0,
            "TRX": 0.12,
            "SOL": 150.0
        }

def create_invoice(amount_usd: float, asset: str = "USDT"):
    """Создание счета для оплаты в указанной криптовалюте"""
    try:
        logging.info(f"💰 create_invoice: amount_usd={amount_usd}, asset={asset}")
        
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
                "rate": None
            }
        
        rates = get_exchange_rates()
        logging.info(f"💰 Получены курсы: {rates}")
        
        # Конвертируем USD в выбранную криптовалюту
        crypto_amount = amount_usd
        rate = None
        
        if asset != "USDT" and rates and asset in rates:
            rate = rates[asset]
            crypto_amount = amount_usd / rate
            logging.info(f"💰 Конвертация: {amount_usd} USD / {rate} = {crypto_amount} {asset}")
            
            # Округляем
            if asset in ["BTC", "ETH", "BNB", "SOL"]:
                crypto_amount = round(crypto_amount, 8)
            elif asset in ["TON"]:
                crypto_amount = round(crypto_amount, 4)
            else:
                crypto_amount = round(crypto_amount, 2)
            
            logging.info(f"💰 После округления: {crypto_amount} {asset}")
        elif asset == "USDT":
            # USDT всегда 1:1 с USD
            rate = 1.0
            crypto_amount = amount_usd
            logging.info(f"💰 USDT без конвертации: {crypto_amount}")
        else:
            logging.warning(f"⚠️ Курс для {asset} не найден! Использую заглушку")
            # Используем заглушку если API не дал курс
            fallback_rates = {
                "BTC": 65000.0,
                "TON": 5.5,
                "ETH": 3500.0,
                "USDT": 1.0,
                "USDC": 1.0,
                "BNB": 500.0,
                "TRX": 0.12,
                "SOL": 150.0
            }
            if asset in fallback_rates:
                rate = fallback_rates[asset]
                crypto_amount = amount_usd / rate
                logging.info(f"💰 Использую заглушку: {amount_usd} USD / {rate} = {crypto_amount} {asset}")
                
                if asset in ["BTC", "ETH", "BNB", "SOL"]:
                    crypto_amount = round(crypto_amount, 8)
                elif asset in ["TON"]:
                    crypto_amount = round(crypto_amount, 4)
                else:
                    crypto_amount = round(crypto_amount, 2)
        
        # Создаем инвойс в CryptoBot
        payload = {
            "asset": asset,
            "amount": str(crypto_amount),
            "description": f"Покупка конфет",
            "allow_comments": False,
            "allow_anonymous": False,
            "expires_in": 3600
        }
        logging.info(f"💰 Отправляем в CryptoBot: {payload}")
        
        r = requests.post(
            f"{CRYPTOBOT_API}/createInvoice",
            headers=HEADERS,
            json=payload,
            timeout=15
        )
        
        logging.info(f"💰 Статус ответа от CryptoBot: {r.status_code}")
        r.raise_for_status()
        result = r.json()["result"]
        logging.info(f"💰 Ответ от CryptoBot: {result}")
        
        # Добавляем наши поля в результат
        result["asset"] = asset
        result["crypto_amount"] = crypto_amount
        result["usd_amount"] = amount_usd
        result["rate"] = rate
        
        logging.info(f"💰 Итоговый результат: {result}")
        return result
    except Exception as e:
        logging.error(f"❌ Error creating invoice: {e}")
        import traceback
        logging.error(traceback.format_exc())
        return {
            "invoice_id": f"error_{amount_usd}_{asset}",
            "pay_url": BOT_LINK,
            "status": "error",
            "asset": asset,
            "amount": str(amount_usd),
            "crypto_amount": amount_usd,
            "usd_amount": amount_usd,
            "rate": None
        }

def check_invoice(invoice_id: str) -> dict:
    """Проверка статуса оплаты"""
    try:
        if not CRYPTOBOT_TOKEN:
            if invoice_id.startswith("test_"):
                return {"status": "paid", "paid": True}
            return {"status": "error", "paid": False}
        
        if invoice_id.startswith("error_"):
            return {"status": "error", "paid": False}
            
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
        if items and items[0]["status"] == "paid":
            return {
                "status": "paid",
                "paid": True,
                "asset": items[0].get("asset"),
                "amount": float(items[0].get("amount", 0))
            }
        return {"status": "active", "paid": False}
    except Exception as e:
        logging.error(f"Error checking invoice: {e}")
        return {"status": "error", "paid": False}
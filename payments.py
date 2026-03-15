import requests
from config import CRYPTOBOT_API, CRYPTOBOT_TOKEN
import logging

# Ссылка на бота
BOT_LINK = "https://t.me/AnonkaBot34bot"

HEADERS = {
    "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN,
    "Content-Type": "application/json"
}

# ДОСТУПНЫЕ ВАЛЮТЫ (БЕЗ ADA)
AVAILABLE_ASSETS = ["BTC", "TON", "ETH", "USDT", "USDC", "BUSD", "BNB", "TRX", "SOL"]

def get_asset_icon(asset: str) -> str:
    icons = {
        "BTC": "₿",
        "TON": "💎", 
        "ETH": "Ξ",
        "USDT": "💵",
        "USDC": "💲", 
        "BUSD": "🪙",
        "BNB": "🔶",
        "TRX": "🌞",
        "SOL": "◎"
    }
    return icons.get(asset, "🪙")

def get_exchange_rates():
    """Получение актуальных курсов валют к USD"""
    try:
        if not CRYPTOBOT_TOKEN:
            return {
                "BTC": 65000.0,
                "TON": 5.5,
                "ETH": 3500.0,
                "USDT": 1.0,
                "USDC": 1.0,
                "BUSD": 1.0,
                "BNB": 500.0,
                "TRX": 0.12,
                "SOL": 150.0
            }
        
        r = requests.post(
            f"{CRYPTOBOT_API}/getExchangeRates",
            headers=HEADERS,
            json={},
            timeout=15
        )
        r.raise_for_status()
        rates = {}
        for item in r.json()["result"]:
            if item["is_valid"] and item["source"] == "USD":
                rates[item["target"]] = float(item["rate"])
        return rates
    except Exception as e:
        logging.error(f"Error getting exchange rates: {e}")
        return {
            "BTC": 65000.0,
            "TON": 5.5,
            "ETH": 3500.0,
            "USDT": 1.0,
            "USDC": 1.0,
            "BUSD": 1.0,
            "BNB": 500.0,
            "TRX": 0.12,
            "SOL": 150.0
        }

def create_invoice(amount_usd: float, asset: str = "USDT"):
    """Создание счета для оплаты в указанной криптовалюте"""
    try:
        if not CRYPTOBOT_TOKEN:
            return {
                "invoice_id": f"test_{amount_usd}_{asset}",
                "pay_url": BOT_LINK,
                "status": "active",
                "asset": asset,
                "amount": amount_usd
            }
        
        rates = get_exchange_rates()
        
        crypto_amount = amount_usd
        if asset != "USDT" and rates and asset in rates:
            rate = rates[asset]
            crypto_amount = amount_usd / rate
            if asset in ["BTC", "ETH", "BNB", "SOL"]:
                crypto_amount = round(crypto_amount, 8)
            elif asset in ["TON"]:
                crypto_amount = round(crypto_amount, 4)
            else:
                crypto_amount = round(crypto_amount, 2)
        
        r = requests.post(
            f"{CRYPTOBOT_API}/createInvoice",
            headers=HEADERS,
            json={
                "asset": asset,
                "amount": str(crypto_amount),
                "description": f"Покупка конфет",
                "allow_comments": False,
                "allow_anonymous": False,
                "expires_in": 3600
            },
            timeout=15
        )
        r.raise_for_status()
        result = r.json()["result"]
        result["asset"] = asset
        result["crypto_amount"] = crypto_amount
        result["usd_amount"] = amount_usd
        return result
    except Exception as e:
        logging.error(f"Error creating invoice: {e}")
        return {
            "invoice_id": f"error_{amount_usd}_{asset}",
            "pay_url": BOT_LINK,
            "status": "error",
            "asset": asset,
            "amount": amount_usd
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
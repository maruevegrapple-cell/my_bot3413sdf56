import requests
from config import CRYPTOBOT_API, CRYPTOBOT_TOKEN

HEADERS = {
    "Crypto-Pay-API-Token": CRYPTOBOT_TOKEN
}

def create_invoice(amount: float):
    r = requests.post(
        f"{CRYPTOBOT_API}/createInvoice",
        headers=HEADERS,
        json={
            "asset": "USDT",
            "amount": amount
        }
    )
    return r.json()["result"]

def check_invoice(invoice_id: str) -> bool:
    r = requests.post(
        f"{CRYPTOBOT_API}/getInvoices",
        headers=HEADERS,
        json={"invoice_ids": [invoice_id]}
    )
    items = r.json()["result"]["items"]
    return items and items[0]["status"] == "paid"

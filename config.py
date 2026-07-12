# Crypto Signal Bot Config
import os

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
TELEGRAM_CHANNEL = os.environ.get("TELEGRAM_CHANNEL", "-1004369003536")

BINGX_API_KEY = os.environ.get("BINGX_API_KEY", "")
BINGX_SECRET = os.environ.get("BINGX_SECRET", "")

CMC_API_KEY = os.environ.get("CMC_API_KEY", "")

VIRTUAL_DEPOSIT = 100.0
RISK_PER_TRADE = 1.0
SCAN_INTERVAL = 300
PRICE_CHECK_INTERVAL = 10
MORNING_DIGEST_TIME = "08:00"

COINS = [
        "BTC-USDT", "ETH-USDT", "SOL-USDT", "BNB-USDT", "XRP-USDT",
        "DOGE-USDT", "ADA-USDT", "AVAX-USDT", "DOT-USDT", "MATIC-USDT",
        "LTC-USDT", "LINK-USDT", "UNI-USDT", "ATOM-USDT", "ETC-USDT",
        "TRX-USDT", "NEAR-USDT", "FTM-USDT", "OP-USDT", "ARB-USDT",
        "SUI-USDT", "INJ-USDT", "WIF-USDT", "PEPE-USDT", "SHIB-USDT",
]

CONFIDENCE_MATRIX = [
        (50, 60, 20, 5),
        (60, 70, 40, 10),
        (70, 80, 60, 15),
        (80, 90, 80, 20),
        (90, 101, 100, 30),
]

BINGX_FEE = 0.00075

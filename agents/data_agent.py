import requests
import time
from typing import List, Dict, Optional

BINGX_BASE = "https://open-api.bingx.com"

def get_candles(symbol: str, interval: str = "1h", limit: int = 100) -> List[Dict]:
    try:
        url = BINGX_BASE + "/openApi/swap/v2/quote/klines"
        params = {"symbol": symbol, "interval": interval, "limit": limit}
        r = requests.get(url, params=params, timeout=10)
        data = r.json()
        if data.get("code") == 0:
            candles = []
            for c in data["data"]:
                candles.append({"time":int(c["time"]),"open":float(c["open"]),"high":float(c["high"]),"low":float(c["low"]),"close":float(c["close"]),"volume":float(c["volume"])})
            return candles
        return []
    except Exception as e:
        print("BingX candles error:", symbol, e)
        return []

def get_price(symbol: str) -> Optional[float]:
    try:
        url = BINGX_BASE + "/openApi/swap/v2/quote/price"
        r = requests.get(url, params={"symbol": symbol}, timeout=5)
        data = r.json()
        if data.get("code") == 0:
            return float(data["data"]["price"])
        return None
    except Exception as e:
        return None

def get_all_prices(symbols: List[str]) -> Dict[str, float]:
    prices = {}
    for symbol in symbols:
        price = get_price(symbol)
        if price:
            prices[symbol] = price
        time.sleep(0.1)
    return prices

def get_24h_stats(symbol: str) -> Dict:
    try:
        url = BINGX_BASE + "/openApi/swap/v2/quote/ticker"
        r = requests.get(url, params={"symbol": symbol}, timeout=5)
        data = r.json()
        if data.get("code") == 0:
            d = data["data"]
            return {"symbol":symbol,"price":float(d.get("lastPrice",0)),"change":float(d.get("priceChangePercent",0))}
        return {}
    except:
        return {}

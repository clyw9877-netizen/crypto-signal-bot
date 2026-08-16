import requests
import time
from typing import List, Dict, Optional


BINGX_BASE = "https://open-api.bingx.com"
TIMEOUT = 6

SYMBOL_ALIASES = {
    "MATIC-USDT": "POL-USDT",
    "FTM-USDT": "S-USDT",
    "PEPE-USDT": "1000PEPE-USDT",
    "SHIB-USDT": "1000SHIB-USDT",
    "GOLD-USDT": "PAXG-USDT",
    "NASDAQ100-USDT": "NCSINASDAQ1002USD-USDT",
    "SP500-USDT": "NCSISP5002USD-USDT",
    "US30-USDT": "NCSIDOWJONES2USD-USDT",
}
PRICE_DIVISORS = {
    "PEPE-USDT": 1000,
    "SHIB-USDT": 1000,
}


def _resolve(symbol: str) -> str:
    return SYMBOL_ALIASES.get(symbol, symbol)


def _divisor(symbol: str) -> float:
    return PRICE_DIVISORS.get(symbol, 1)


def get_candles(symbol: str, interval: str = "1h", limit: int = 100) -> List[Dict]:
    api_symbol = _resolve(symbol)
    div = _divisor(symbol)
    try:
        url = BINGX_BASE + "/openApi/swap/v2/quote/klines"
        params = {"symbol": api_symbol, "interval": interval, "limit": limit}
        r = requests.get(url, params=params, timeout=TIMEOUT)
        data = r.json()
        if data.get("code") == 0:
            candles = []
            for c in data["data"]:
                candles.append({"time":int(c["time"]),"open":float(c["open"])/div,"high":float(c["high"])/div,"low":float(c["low"])/div,"close":float(c["close"])/div,"volume":float(c["volume"])})
            return candles
        return []
    except Exception as e:
        print("BingX candles error:", symbol, e)
        return []


def get_price(symbol: str) -> Optional[float]:
    # Use ticker endpoint (lastPrice) instead of /quote/price (can be stale/mark price)
    api_symbol = _resolve(symbol)
    div = _divisor(symbol)
    try:
        url = BINGX_BASE + "/openApi/swap/v2/quote/ticker"
        r = requests.get(url, params={"symbol": api_symbol}, timeout=TIMEOUT)
        data = r.json()
        if data.get("code") == 0:
            d = data["data"]
            last_price = d.get("lastPrice")
            if last_price is not None:
                return float(last_price) / div
        return None
    except Exception as e:
        print("BingX price error:", symbol, e)
        return None


def get_all_prices(symbols: List[str]) -> Dict[str, float]:
    prices = {}
    for symbol in symbols:
        price = get_price(symbol)
        if price:
            prices[symbol] = price
        time.sleep(0.05)
    return prices


def get_24h_stats(symbol: str) -> Dict:
    api_symbol = _resolve(symbol)
    div = _divisor(symbol)
    try:
        url = BINGX_BASE + "/openApi/swap/v2/quote/ticker"
        r = requests.get(url, params={"symbol": api_symbol}, timeout=TIMEOUT)
        data = r.json()
        if data.get("code") == 0:
            d = data["data"]
            return {"symbol":symbol,"price":float(d.get("lastPrice",0))/div,"change":float(d.get("priceChangePercent",0))}
        return {}
    except Exception as e:
        print("BingX stats error:", symbol, e)
        return {}

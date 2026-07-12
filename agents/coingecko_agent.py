import requests

TIMEOUT = 8
URL = "https://api.coingecko.com/api/v3/coins/markets"


def get_top_movers(limit=5):
    try:
        r = requests.get(URL, params={
            "vs_currency": "usd",
            "order": "market_cap_desc",
            "per_page": 250,
            "page": 1,
            "price_change_percentage": "24h",
        }, timeout=TIMEOUT)
        if r.status_code == 200:
            data = r.json()
            valid = [c for c in data if c.get("price_change_percentage_24h") is not None]
            sorted_coins = sorted(valid, key=lambda c: c["price_change_percentage_24h"], reverse=True)
            gainers = sorted_coins[:limit]
            losers = sorted_coins[-limit:][::-1]
            return {"gainers": gainers, "losers": losers}
        print(f"CoinGecko API error: status {r.status_code}")
    except Exception as e:
        print("CoinGecko error:", e)
    return None


def format_top_movers(data):
    if not data:
        return None
    gainers = data.get("gainers") or []
    losers = data.get("losers") or []
    if not gainers or not losers:
        return None
    lines = ["📊 <b>Топ движения за 24ч (CoinGecko)</b>", ""]
    lines.append("🟢 Растут:")
    for c in gainers:
        lines.append(f"  {c['symbol'].upper()}: +{c['price_change_percentage_24h']:.1f}%")
    lines.append("")
    lines.append("🔴 Падают:")
    for c in losers:
        lines.append(f"  {c['symbol'].upper()}: {c['price_change_percentage_24h']:.1f}%")
    return "\n".join(lines)

import requests

BASE_URL = "https://pro-api.coinmarketcap.com/v1"
TIMEOUT = 8


def get_global_metrics(api_key):
    if not api_key:
        return None
    try:
        r = requests.get(
            f"{BASE_URL}/global-metrics/quotes/latest",
            headers={"X-CMC_PRO_API_KEY": api_key, "Accept": "application/json"},
            timeout=TIMEOUT
        )
        if r.status_code == 200:
            d = r.json().get("data", {})
            q = d.get("quote", {}).get("USD", {})
            return {
                "total_market_cap": q.get("total_market_cap"),
                "market_cap_change_24h": q.get("total_market_cap_yesterday_percentage_change"),
                "total_volume_24h": q.get("total_volume_24h"),
                "btc_dominance": d.get("btc_dominance"),
                "eth_dominance": d.get("eth_dominance"),
            }
        print(f"CoinMarketCap API error: status {r.status_code}")
    except Exception as e:
        print("CoinMarketCap error:", e)
    return None


def format_market_overview(metrics):
    if not metrics:
        return None
    required = ["total_market_cap", "market_cap_change_24h", "total_volume_24h", "btc_dominance", "eth_dominance"]
    if any(metrics.get(k) is None for k in required):
        return None
    mc = metrics["total_market_cap"] / 1e9
    change = metrics["market_cap_change_24h"]
    vol = metrics["total_volume_24h"] / 1e9
    btc_dom = metrics["btc_dominance"]
    eth_dom = metrics["eth_dominance"]
    arrow = "🟢" if change >= 0 else "🔴"
    return (
        f"🌍 <b>Обзор рынка (CoinMarketCap)</b>\n\n"
        f"Капитализация: ${mc:,.1f}B {arrow} {change:+.2f}% (24ч)\n"
        f"Объём торгов (24ч): ${vol:,.1f}B\n"
        f"Доминация BTC: {btc_dom:.1f}%\n"
        f"Доминация ETH: {eth_dom:.1f}%"
    )

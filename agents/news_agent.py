import requests
from datetime import datetime, date
from typing import List, Dict

TIMEOUT = 6
FF_URLS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://cdn-nfs.faireconomy.media/ff_calendar_thisweek.json",
]

def get_crypto_news() -> List[Dict]:
    try:
        r = requests.get("https://cryptopanic.com/api/v1/posts/", params={"auth_token":"free","public":"true","kind":"news","filter":"hot"}, timeout=TIMEOUT)
        news = []
        for item in r.json().get("results", [])[:10]:
            news.append({"title":item.get("title",""),"source":item.get("source",{}).get("title",""),"votes_positive":item.get("votes",{}).get("positive",0),"currencies":[c["code"] for c in item.get("currencies",[])]})
        return news
    except Exception as e:
        print("get_crypto_news error:", e)
        return []

def get_forex_factory_events() -> List[Dict]:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    raw = None
    for url in FF_URLS:
        try:
            r = requests.get(url, timeout=TIMEOUT, headers=headers)
            print(f"FF fetch {url} -> status {r.status_code}, len {len(r.text)}")
            if r.status_code == 200 and r.text.strip().startswith("["):
                raw = r.json()
                break
            else:
                print(f"FF response not JSON array. First 200 chars: {r.text[:200]}")
        except Exception as e:
            print(f"FF fetch error {url}: {e}")
    if raw is None:
        return []
    try:
        today = date.today().strftime("%m-%d-%Y")
        events = []
        for event in raw:
            if event.get("date","") == today and event.get("impact","") in ["High","Medium"]:
                events.append({"time":event.get("time",""),"currency":event.get("country",""),"title":event.get("title",""),"impact":event.get("impact","")})
        print(f"FF events parsed: {len(events)} (total entries this week: {len(raw)})")
        return sorted(events, key=lambda x: x["time"])
    except Exception as e:
        print("FF parse error:", e)
        return []

def check_high_impact_now() -> bool:
    try:
        events = get_forex_factory_events()
        now = datetime.now()
        for event in events:
            if event["impact"] != "High": continue
            try:
                event_time = datetime.strptime(str(date.today()) + " " + event["time"], "%Y-%m-%d %I:%M%p")
                if abs((event_time - now).total_seconds() / 60) <= 30:
                    return True
            except:
                continue
    except Exception as e:
        print("check_high_impact_now error:", e)
    return False

def get_fear_greed() -> Dict:
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=TIMEOUT)
        d = r.json()["data"][0]
        return {"value":int(d["value"]),"classification":d["value_classification"]}
    except Exception as e:
        print("get_fear_greed error:", e)
        return {"value":50,"classification":"Neutral"}

def get_btc_dominance() -> float:
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=TIMEOUT)
        return r.json()["data"]["market_cap_percentage"]["btc"]
    except Exception as e:
        print("get_btc_dominance error:", e)
        return 0.0

def format_morning_digest(prices, events, news) -> str:
    fg = get_fear_greed()
    btc = prices.get("BTC-USDT", 0)
    eth = prices.get("ETH-USDT", 0)
    sol = prices.get("SOL-USDT", 0)
    text = "Morning Digest " + datetime.now().strftime("%d.%m.%Y") + "\n\nMarket:\nBTC: $" + str(round(btc)) + "\nETH: $" + str(round(eth,2)) + "\nSOL: $" + str(round(sol,2)) + "\nFear&Greed: " + str(fg["value"]) + " " + fg["classification"] + "\n\n"
    if events:
        text += "Events today:\n"
        for e in events[:5]:
            text += ("RED " if e["impact"]=="High" else "YEL ") + e["time"] + " " + e["currency"] + " - " + e["title"] + "\n"
    else:
        text += "No major events found today (or calendar source unavailable).\n"
    if news:
        text += "\nTop news:\n"
        for n in news[:3]:
            text += "- " + n["title"][:80] + "\n"
    text += "\nBot scanning market every 5 min..."
    return text

def format_signal_news(signal, related_news) -> str:
    if not related_news: return ""
    text = "\nNews context:\n"
    for n in related_news[:2]:
        sentiment = "Positive" if n.get("votes_positive",0) > 0 else "Neutral"
        text += "- " + sentiment + ": " + n["title"][:70] + "\n"
    return text

import requests
from datetime import datetime, date
from typing import List, Dict

def get_crypto_news() -> List[Dict]:
    try:
        r = requests.get("https://cryptopanic.com/api/v1/posts/", params={"auth_token":"free","public":"true","kind":"news","filter":"hot"}, timeout=10)
        news = []
        for item in r.json().get("results", [])[:10]:
            news.append({"title":item.get("title",""),"source":item.get("source",{}).get("title",""),"votes_positive":item.get("votes",{}).get("positive",0),"currencies":[c["code"] for c in item.get("currencies",[])]})
        return news
    except:
        return []

def get_forex_factory_events() -> List[Dict]:
    try:
        r = requests.get("https://nfs.faireconomy.media/ff_calendar_thisweek.json", timeout=10)
        today = date.today().strftime("%m-%d-%Y")
        events = []
        for event in r.json():
            if event.get("date","") == today and event.get("impact","") in ["High","Medium"]:
                events.append({"time":event.get("time",""),"currency":event.get("country",""),"title":event.get("title",""),"impact":event.get("impact","")})
        return sorted(events, key=lambda x: x["time"])
    except:
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
    except:
        pass
    return False

def get_fear_greed() -> Dict:
    try:
        r = requests.get("https://api.alternative.me/fng/?limit=1", timeout=10)
        d = r.json()["data"][0]
        return {"value":int(d["value"]),"classification":d["value_classification"]}
    except:
        return {"value":50,"classification":"Neutral"}

def get_btc_dominance() -> float:
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=10)
        return r.json()["data"]["market_cap_percentage"]["btc"]
    except:
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

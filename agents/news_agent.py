"""
news_agent.py -- парсит макроэкономические и крипто-новости.
Forex Factory (HIGH impact события), CryptoPanic (горячие крипто-новости).
"""
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
_cache = {"ff": None, "ff_ts": 0, "cp": None, "cp_ts": 0}
CACHE_TTL = 60 * 30


def get_forex_factory_events():
    now = datetime.now(timezone.utc).timestamp()
    if _cache["ff"] is not None and now - _cache["ff_ts"] < CACHE_TTL:
        return _cache["ff"]
    try:
        r = requests.get("https://www.forexfactory.com/calendar", headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        events = []
        for row in soup.select("tr.calendar__row"):
            impact = row.select_one(".calendar__impact span")
            if not impact or not any("high" in c for c in impact.get("class", [])):
                continue
            time_el = row.select_one(".calendar__time")
            title_el = row.select_one(".calendar__event-title")
            currency_el = row.select_one(".calendar__currency")
            events.append({
                "time": time_el.text.strip() if time_el else "?",
                "currency": currency_el.text.strip() if currency_el else "?",
                "title": title_el.text.strip() if title_el else "?"
            })
        _cache["ff"] = events
        _cache["ff_ts"] = now
        return events
    except Exception as e:
        print(f"ForexFactory error: {e}")
        return []


def get_crypto_news():
    now = datetime.now(timezone.utc).timestamp()
    if _cache["cp"] is not None and now - _cache["cp_ts"] < CACHE_TTL:
        return _cache["cp"]
    try:
        url = "https://cryptopanic.com/api/v1/posts/?auth_token=public&filter=hot&public=true"
        r = requests.get(url, timeout=10)
        news = []
        for item in r.json().get("results", [])[:10]:
            votes = item.get("votes", {})
            panic = votes.get("negative", 0)
            positive = votes.get("positive", 0)
            if panic < 3 and positive < 3:
                continue
            sentiment = "ПАНИКА" if panic > positive else "ПОЗИТИВ"
            news.append(f"[{sentiment}] {item.get('title','')}")
        _cache["cp"] = news
        _cache["cp_ts"] = now
        return news
    except Exception as e:
        print(f"CryptoPanic error: {e}")
        return []


def get_news_context():
    lines = []
    ff = get_forex_factory_events()
    if ff:
        lines.append("MACRO EVENTS TODAY (Forex Factory, HIGH impact):")
        for e in ff[:5]:
            lines.append(f"  {e['time']} UTC [{e['currency']}] {e['title']}")
        lines.append("WARNING: High volatility possible around these times!")
    else:
        lines.append("No major macro events today (Forex Factory).")
    lines.append("")
    cp = get_crypto_news()
    if cp:
        lines.append("CRYPTO NEWS (CryptoPanic hot):")
        for n in cp[:5]:
            lines.append(f"  {n}")
    else:
        lines.append("No hot crypto news.")
    return "\n".join(lines)

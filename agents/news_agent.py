"""
news_agent.py -- макро и крипто новости для бота.
Forex Factory (HIGH impact), CryptoPanic (горячие), digest и signal news.
"""
import requests
from datetime import datetime, timezone, timedelta
from bs4 import BeautifulSoup

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
_cache = {"ff": None, "ff_ts": 0, "cp": None, "cp_ts": 0}
CACHE_TTL = 60 * 30  # 30 минут


def get_forex_factory_events():
    """Парсит Forex Factory — HIGH impact события на сегодня."""
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
    """Парсит CryptoPanic — горячие крипто-новости."""
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
            news.append({"title": item.get("title", ""), "sentiment": sentiment, "panic": panic, "positive": positive})
        _cache["cp"] = news
        _cache["cp_ts"] = now
        return news
    except Exception as e:
        print(f"CryptoPanic error: {e}")
        return []


def check_high_impact_now():
    """Проверяет есть ли HIGH impact события в ближайший час."""
    try:
        events = get_forex_factory_events()
        if not events:
            return False
        # Если есть хоть одно HIGH событие сегодня — считаем опасным
        return len(events) > 0
    except Exception:
        return False


def get_news_context():
    """Контекст для ИИ перед входом в сделку."""
    lines = []
    ff = get_forex_factory_events()
    if ff:
        lines.append("MACRO EVENTS TODAY (Forex Factory, HIGH impact):")
        for e in ff[:5]:
            lines.append(f"  {e['time']} UTC [{e['currency']}] {e['title']}")
        lines.append("WARNING: High volatility possible around these times!")
    else:
        lines.append("No major macro events today.")
    lines.append("")
    cp = get_crypto_news()
    if cp:
        lines.append("CRYPTO NEWS (CryptoPanic hot):")
        for n in cp[:5]:
            lines.append(f"  [{n['sentiment']}] {n['title']}")
    else:
        lines.append("No hot crypto news.")
    return "\n".join(lines)


def format_signal_news(signal, related_news):
    """Форматирует новости связанные с монетой для сообщения о сигнале."""
    if not related_news:
        return ""
    lines = ["\n📰 <b>Связанные новости:</b>"]
    for n in related_news[:3]:
        title = n.get("title", "") if isinstance(n, dict) else str(n)
        lines.append(f"• {title[:100]}")
    return "\n".join(lines)


def format_morning_digest():
    """Утренний дайджест — макро события и крипто новости."""
    lines = ["🌅 <b>Утренний дайджест</b>\n"]
    ff = get_forex_factory_events()
    if ff:
        lines.append("📅 <b>Важные события сегодня:</b>")
        for e in ff[:5]:
            lines.append(f"  • {e['time']} [{e['currency']}] {e['title']}")
    else:
        lines.append("📅 Важных макро-событий сегодня нет")
    lines.append("")
    cp = get_crypto_news()
    if cp:
        lines.append("📰 <b>Горячие крипто-новости:</b>")
        for n in cp[:3]:
            lines.append(f"  • [{n['sentiment']}] {n['title'][:80]}")
    return "\n".join(lines)


def format_evening_digest():
    """Вечерний дайджест."""
    lines = ["🌙 <b>Вечерний дайджест</b>\n"]
    cp = get_crypto_news()
    if cp:
        lines.append("📰 <b>Главные новости дня:</b>")
        for n in cp[:5]:
            lines.append(f"  • [{n['sentiment']}] {n['title'][:80]}")
    else:
        lines.append("📰 Значимых новостей за день не было")
    return "\n".join(lines)


def format_digest(kind="morning"):
    """Алиас для совместимости — вызывается из chat_agent."""
    if kind == "evening":
        return format_evening_digest()
    return format_morning_digest()

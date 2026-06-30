import requests
from datetime import datetime, date
from dateutil import parser as dateparser
from typing import List, Dict
from agents.polymarket_agent import get_crypto_markets, format_polymarket_section

TIMEOUT = 6
FF_URLS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://cdn-nfs.faireconomy.media/ff_calendar_thisweek.json",
]

CRYPTO_RELEVANT_CURRENCIES = {"USD"}

EVENT_EXPLANATIONS = [
    (["fomc", "interest rate", "fed funds rate", "rate decision"],
     "Решение ФРС по ставке. Самое важное событие для всех рынков. Снижают ставку → деньги дешевлеют → обычно растёт крипта и акции. Повышают ставку → обычно падает рынок риска."),
    (["cpi", "consumer price index", "inflation"],
     "Инфляция в США. Если выше прогноза — рынок ждёт повышения ставки ФРС, крипта обычно падает. Если ниже — ожидают снижения ставок, крипта обычно растёт."),
    (["non farm", "nonfarm", "employment", "unemployment", "jobless claims", "jolts", "payroll"],
     "Данные по рынку труда США. Сильный рынок труда → ФРС держит ставки высокими → плохо для крипты. Слабый рынок труда → ждут снижения ставок → хорошо для крипты."),
    (["gdp"],
     "Валовой внутренний продукт США — показывает состояние экономики. Слабый рост может вызвать снижение ставок и рост крипты, сильный рост — наоборот."),
    (["powell", "fed chair", "fomc statement", "press conference"],
     "Выступление главы ФРС. Часто двигает рынок сильнее самих данных — трейдеры реагируют на тон речи. Не входи за 30 мин до и после."),
    (["retail sales"],
     "Розничные продажи США — показывает силу потребителя. Сильные данные могут усилить опасения по инфляции и давление на рисковые активы."),
    (["consumer confidence", "consumer sentiment"],
     "Индекс доверия потребителей США. Косвенно влияет на рынок через ожидания по расходам и инфляции."),
    (["ppi", "producer price"],
     "Индекс цен производителей США — опережающий индикатор инфляции. Влияет на ожидания по CPI и ставке ФРС."),
]

def _explain_event(title: str) -> str:
    t = title.lower()
    for keywords, explanation in EVENT_EXPLANATIONS:
        if any(k in t for k in keywords):
            return explanation
    return ""

def is_crypto_relevant(event: dict) -> bool:
    if event.get("currency") not in CRYPTO_RELEVANT_CURRENCIES:
        return False
    title = event.get("title", "").lower()
    relevant_keywords = ["fomc", "interest rate", "fed funds", "rate decision", "cpi", "inflation",
                         "non farm", "nonfarm", "employment", "unemployment", "jobless", "jolts",
                         "payroll", "gdp", "powell", "retail sales", "consumer confidence",
                         "consumer sentiment", "ppi", "producer price"]
    return any(k in title for k in relevant_keywords)

def get_crypto_news() -> List[Dict]:
    try:
        r = requests.get("https://cryptopanic.com/api/v1/posts/", params={"auth_token":"free","public":"true","kind":"news","filter":"hot"}, timeout=TIMEOUT)
        news = []
        for item in r.json().get("results", [])[:10]:
            news.append({
                "title": item.get("title",""),
                "source": item.get("source",{}).get("title",""),
                "url": item.get("url",""),
                "votes_positive": item.get("votes",{}).get("positive",0),
                "currencies": [c["code"] for c in item.get("currencies",[])]
            })
        return news
    except Exception as e:
        print("get_crypto_news error:", e)
        return []

def _parse_event_date(raw_date: str):
    try:
        return dateparser.parse(raw_date)
    except Exception:
        return None

def get_forex_factory_events(target_date=None, crypto_only=True) -> List[Dict]:
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    raw = None
    for url in FF_URLS:
        try:
            r = requests.get(url, timeout=TIMEOUT, headers=headers)
            if r.status_code == 200 and r.text.strip().startswith("["):
                raw = r.json()
                break
        except Exception as e:
            print(f"FF fetch error {url}: {e}")
    if raw is None:
        return []
    try:
        target = target_date or date.today()
        events = []
        for event in raw:
            parsed = _parse_event_date(event.get("date", ""))
            if parsed is None:
                continue
            if parsed.date() != target or event.get("impact","") not in ["High","Medium"]:
                continue
            ev = {
                "time": event.get("time",""),
                "currency": event.get("country",""),
                "title": event.get("title",""),
                "impact": event.get("impact",""),
                "url": "https://www.forexfactory.com/calendar"
            }
            if crypto_only and not is_crypto_relevant(ev):
                continue
            ev["explanation"] = _explain_event(ev["title"])
            events.append(ev)
        return sorted(events, key=lambda x: x["time"])
    except Exception as e:
        print("FF parse error:", e)
        return []

def check_high_impact_now() -> bool:
    try:
        events = get_forex_factory_events(crypto_only=True)
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
        return {"value": int(d["value"]), "classification": d["value_classification"]}
    except Exception as e:
        print("get_fear_greed error:", e)
        return {"value": 50, "classification": "Neutral"}

def get_btc_dominance() -> float:
    try:
        r = requests.get("https://api.coingecko.com/api/v3/global", timeout=TIMEOUT)
        return r.json()["data"]["market_cap_percentage"]["btc"]
    except Exception as e:
        print("get_btc_dominance error:", e)
        return 0.0

CLASS_RU = {
    "Extreme Fear": "Экстремальный страх",
    "Fear": "Страх",
    "Neutral": "Нейтрально",
    "Greed": "Жадность",
    "Extreme Greed": "Экстремальная жадность",
}

def format_digest(prices, events, news, title="Утренний дайджест", period_label="Сегодня") -> str:
    fg = get_fear_greed()
    btc = prices.get("BTC-USDT", 0)
    eth = prices.get("ETH-USDT", 0)
    sol = prices.get("SOL-USDT", 0)
    fg_class_ru = CLASS_RU.get(fg["classification"], fg["classification"])

    text = f"📊 <b>{title}</b>\n"
    text += f"{datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n"
    text += f"<b>💰 Рынок:</b>\n"
    text += f"BTC: ${btc:,.0f}\n"
    text += f"ETH: ${eth:,.2f}\n"
    text += f"SOL: ${sol:,.2f}\n"
    text += f"Индекс страха/жадности: {fg['value']} ({fg_class_ru})\n\n"

    if events:
        text += f"<b>📅 Важные события для крипты ({period_label}):</b>\n"
        for e in events[:5]:
            mark = "🔴" if e["impact"]=="High" else "🟡"
            text += f'{mark} {e["time"]} — <b>{e["title"]}</b>\n'
            if e.get("explanation"):
                text += f"   <i>{e['explanation']}</i>\n"
        text += f'\n<a href="https://www.forexfactory.com/calendar">🔗 Полный календарь событий</a>\n\n'
    else:
        text += f"Сегодня нет важных событий, влияющих на крипторынок.\n\n"

    poly_markets = []
    try:
        poly_markets = get_crypto_markets()
    except Exception as e:
        print("Polymarket fetch error in digest:", e)
    poly_section = format_polymarket_section(poly_markets)
    if poly_section:
        text += poly_section

    if news:
        text += "<b>📰 Новости:</b>\n"
        for n in news[:4]:
            link = n.get("url","")
            title_n = n["title"][:90]
            if link:
                text += f'• <a href="{link}">{title_n}</a>\n'
            else:
                text += f"• {title_n}\n"
        text += "\n"

    text += "🤖 <i>Бот сканирует рынок каждые 5 минут...</i>"
    return text

def format_morning_digest(prices, events, news) -> str:
    return format_digest(prices, events, news, title="🌅 Утренний дайджест", period_label="сегодня")

def format_evening_digest(prices, events, news) -> str:
    return format_digest(prices, events, news, title="🌙 Вечерний итог", period_label="завтра")

def format_signal_news(signal, related_news) -> str:
    if not related_news: return ""
    text = "\n<b>📰 Новостной контекст:</b>\n"
    for n in related_news[:2]:
        sentiment = "🟢 Позитив" if n.get("votes_positive",0) > 0 else "⚪ Нейтрально"
        link = n.get("url","")
        title_n = n["title"][:70]
        if link:
            text += f'• {sentiment}: <a href="{link}">{title_n}</a>\n'
        else:
            text += f"• {sentiment}: {title_n}\n"
    return text

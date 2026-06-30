import requests
import json
from typing import List, Dict

TIMEOUT = 6
GAMMA_BASE = "https://gamma-api.polymarket.com"

# Официальные ID тегов Polymarket
TAG_CRYPTO = 21
TAG_GEOPOLITICS = 100265
TAG_FINANCE = 120

# Строгий белый список тем, которые реально интересны для крипто-трейдера:
# 1) цены BTC/ETH/SOL и других монет
# 2) ставка ФРС / инфляция / рецессия
# 3) войны и крупные геополитические события (Иран, Израиль, Россия-Украина), т.к. они двигают риск-аппетит и крипто
INCLUDE_PATTERNS = [
    "bitcoin", "btc", "ethereum", "eth", "solana", "xrp", "dogecoin", "crypto",
    "fed ", "fomc", "interest rate", "rate cut", "rate hike", "recession",
    "inflation", "cpi",
    "iran", "israel", "war", "ceasefire", "russia", "ukraine", "middle east",
]

# Чёрный список — это точно мусор (спорт, выборы премьеров, футбол)
EXCLUDE_PATTERNS = [
    "win on", "world cup", "vs.", " vs ", "premier league", "champions league",
    "fifa", "nba", "nfl", "tennis", "golf", "olympics", "election of", "prime minister",
    "mayor", "governor of", "senate race", "house race",
]

def _parse_json_field(value):
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except Exception:
        return []

def _matches(question: str) -> bool:
    q = question.lower()
    if any(bad in q for bad in EXCLUDE_PATTERNS):
        return False
    return any(good in q for good in INCLUDE_PATTERNS)

def _verify_url(url: str) -> bool:
    try:
        r = requests.head(url, timeout=4, allow_redirects=True)
        return r.status_code < 400
    except Exception:
        try:
            r = requests.get(url, timeout=4, allow_redirects=True)
            return r.status_code < 400
        except Exception:
            return False

def _fetch_by_tag(tag_id: int, limit: int = 100):
    try:
        r = requests.get(
            f"{GAMMA_BASE}/markets",
            params={"active": "true", "closed": "false", "limit": limit, "order": "volume24hr", "ascending": "false", "tag_id": tag_id},
            timeout=TIMEOUT
        )
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"Polymarket tag {tag_id} fetch error:", e)
    return []

def get_crypto_markets(limit: int = 6) -> List[Dict]:
    """Получить релевантные для крипто-трейдера рынки Polymarket: цены, ФРС, геополитика"""
    all_markets = []
    for tag_id in [TAG_CRYPTO, TAG_FINANCE, TAG_GEOPOLITICS]:
        all_markets.extend(_fetch_by_tag(tag_id))

    seen_ids = set()
    results = []
    for m in all_markets:
        mid = m.get("id")
        if mid in seen_ids:
            continue
        seen_ids.add(mid)

        question = m.get("question", "")
        if not _matches(question):
            continue

        outcomes = _parse_json_field(m.get("outcomes", "[]"))
        prices = _parse_json_field(m.get("outcomePrices", "[]"))
        if not outcomes or not prices:
            continue

        try:
            volume24h = float(m.get("volume24hr", 0) or 0)
        except Exception:
            volume24h = 0
        if volume24h < 500:
            continue

        outcome_data = []
        for o, p in zip(outcomes, prices):
            try:
                pct = round(float(p) * 100, 1)
            except Exception:
                pct = 0
            outcome_data.append({"name": o, "probability": pct})

        slug = m.get("slug", "")
        url = f"https://polymarket.com/event/{slug}" if slug else ""

        results.append({
            "question": question,
            "outcomes": outcome_data,
            "volume24h": volume24h,
            "url": url
        })

    results.sort(key=lambda x: -x["volume24h"])

    # Проверяем ссылки только для топ-кандидатов, чтобы не делать множество запросов
    final = []
    for m in results:
        if len(final) >= limit:
            break
        if m["url"] and not _verify_url(m["url"]):
            print(f"Polymarket dead link skipped: {m['url']}")
            continue
        final.append(m)
    return final

# Простой словарь для перевода часто встречающихся фраз на русский
TRANSLATIONS = [
    ("Will the Fed cut interest rates", "Снизит ли ФРС ставку"),
    ("Will the Fed raise interest rates", "Повысит ли ФРС ставку"),
    ("How many times will the Fed cut rates", "Сколько раз ФРС снизит ставку"),
    ("Will Bitcoin reach", "Достигнет ли Bitcoin отметки"),
    ("Will Ethereum reach", "Достигнет ли Ethereum отметки"),
    ("Will there be a recession", "Будет ли рецессия"),
    ("ceasefire", "прекращение огня"),
    ("Will Israel", "Будет ли Израиль"),
    ("Will Iran", "Будет ли Иран"),
    ("Will Russia", "Будет ли Россия"),
    ("end the war", "закончится война"),
]

def _translate_hint(question: str) -> str:
    """Возвращает короткую подсказку на русском, если вопрос совпадает с известным шаблоном"""
    for eng, rus in TRANSLATIONS:
        if eng.lower() in question.lower():
            return rus
    return ""

def format_polymarket_section(markets: List[Dict], max_items: int = 5) -> str:
    if not markets:
        return ""
    text = "<b>🎲 Polymarket — мнение толпы (финансы/крипта/геополитика):</b>\n"
    for m in markets[:max_items]:
        q = m["question"][:100]
        hint = _translate_hint(m["question"])
        top_outcomes = sorted(m["outcomes"], key=lambda x: -x["probability"])[:2]
        outcomes_str = " / ".join(f"{o['name']}: {o['probability']}%" for o in top_outcomes)
        if m["url"]:
            text += f'• <a href="{m["url"]}">{q}</a>\n'
        else:
            text += f"• {q}\n"
        if hint:
            text += f"  ({hint})\n"
        text += f"  {outcomes_str}\n"
    text += "\n"
    return text

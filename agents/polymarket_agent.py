import requests
import json
import re
from typing import List, Dict

TIMEOUT = 6
GAMMA_BASE = "https://gamma-api.polymarket.com"

TAG_CRYPTO = 21
TAG_GEOPOLITICS = 100265
TAG_FINANCE = 120

PRIORITY_PATTERNS = [
    "fed ", "fomc", "interest rate", "rate cut", "rate hike", "federal reserve",
    "bitcoin", "btc", "ethereum", "eth ", "solana", "xrp", "dogecoin",
    "recession", "inflation", "cpi",
    "iran", "israel", "ceasefire", "nuclear", "uranium",
    "russia", "ukraine", "putin", "war",
]

# Мусор — краткосрочные микро-рынки и спорт/выборы
EXCLUDE_PATTERNS = [
    "win on", "world cup", "vs.", " vs ", "premier league", "champions league",
    "fifa", "nba", "nfl", "tennis", "golf", "olympics", "election of", "prime minister",
    "mayor", "governor of", "senate race", "house race", "grammy", "oscar",
    "up or down", "et$", " pm et", " am et", "satoshi move",
]

def _parse_json_field(value):
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except Exception:
        return []

def _priority_score(question: str) -> int:
    q = question.lower()
    if any(bad in q for bad in EXCLUDE_PATTERNS):
        return -1
    for i, pat in enumerate(PRIORITY_PATTERNS):
        if pat in q:
            return len(PRIORITY_PATTERNS) - i
    return 0

def _verify_url(url: str) -> bool:
    try:
        r = requests.head(url, timeout=4, allow_redirects=True)
        if r.status_code < 400:
            return True
    except Exception:
        pass
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

def _search_keyword(keyword: str, limit: int = 30):
    """Дополнительный поиск по ключевому слову в вопросе, чтобы найти конкретные темы вроде Fed rate cuts in 2026"""
    try:
        r = requests.get(
            f"{GAMMA_BASE}/markets",
            params={"active": "true", "closed": "false", "limit": limit, "order": "volume24hr", "ascending": "false"},
            timeout=TIMEOUT
        )
        if r.status_code == 200:
            all_m = r.json()
            return [m for m in all_m if keyword.lower() in m.get("question", "").lower()]
    except Exception as e:
        print(f"Polymarket keyword search error '{keyword}':", e)
    return []

def get_crypto_markets(limit: int = 5) -> List[Dict]:
    all_markets = []
    for tag_id in [TAG_CRYPTO, TAG_FINANCE, TAG_GEOPOLITICS]:
        all_markets.extend(_fetch_by_tag(tag_id))
    # Явно добавляем рынки про ставку ФРС, т.к. они могут быть вне этих тегов
    all_markets.extend(_search_keyword("fed rate"))
    all_markets.extend(_search_keyword("rate cuts in 2026"))

    seen_ids = set()
    scored = []
    for m in all_markets:
        mid = m.get("id")
        if mid in seen_ids:
            continue
        seen_ids.add(mid)

        question = m.get("question", "")
        score = _priority_score(question)
        if score <= 0:
            continue

        outcomes = _parse_json_field(m.get("outcomes", "[]"))
        prices = _parse_json_field(m.get("outcomePrices", "[]"))
        if not outcomes or not prices:
            continue

        try:
            volume24h = float(m.get("volume24hr", 0) or 0)
        except Exception:
            volume24h = 0
        if volume24h < 300:
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

        scored.append({
            "question": question,
            "outcomes": outcome_data,
            "volume24h": volume24h,
            "score": score,
            "url": url
        })

    scored.sort(key=lambda x: (-x["score"], -x["volume24h"]))

    final = []
    for m in scored:
        if len(final) >= limit:
            break
        if m["url"] and not _verify_url(m["url"]):
            print(f"Polymarket dead link skipped: {m['url']}")
            continue
        final.append(m)
    return final

REPLACEMENTS = [
    (r"how many (fed )?rate cuts in (\d{4})", r"Сколько раз ФРС снизит ставку в \2 году?"),
    (r"will the fed cut (interest )?rates?", "Снизит ли ФРС ставку?"),
    (r"will the fed raise (interest )?rates?", "Повысит ли ФРС ставку?"),
    (r"will bitcoin (reach|hit|exceed|surpass) \$?([\d,]+)k?", r"Достигнет ли Bitcoin \$\2?"),
    (r"will ethereum (reach|hit|exceed|surpass) \$?([\d,]+)k?", r"Достигнет ли Ethereum \$\2?"),
    (r"will there be a (us )?recession in (\d{4})", r"Будет ли рецессия в США в \2 году?"),
    (r"will israel and iran reach a ceasefire", "Договорятся ли Израиль и Иран о прекращении огня?"),
    (r"iran agrees to end enrichment of uranium", "Согласится ли Иран прекратить обогащение урана?"),
    (r"will (the )?us(a)? strike iran", "Атакуют ли США Иран?"),
    (r"putin out as president of russia by (.+)", r"Уйдёт ли Путин с поста президента России до \1?"),
    (r"will ukraine recapture crimean? territory by (.+)", r"Вернёт ли Украина территорию Крыма до \1?"),
    (r"u\.?s\.? agrees to give ukraine security guarantee by (.+)", r"Согласится ли США дать Украине гарантии безопасности до \1?"),
    (r"will microstrategy announce a bitcoin purchase (.+)", r"Объявит ли MicroStrategy о покупке Bitcoin (\1)?"),
]

def _translate_question(question: str) -> str:
    q_lower = question.lower()
    for pattern, replacement in REPLACEMENTS:
        try:
            if re.search(pattern, q_lower):
                return re.sub(pattern, replacement, q_lower, flags=re.IGNORECASE).capitalize()
        except Exception:
            continue
    return question

def format_polymarket_section(markets: List[Dict], max_items: int = 5) -> str:
    if not markets:
        return ""
    text = "<b>🎲 Polymarket — мнение толпы (ФРС/крипта/войны):</b>\n"
    for m in markets[:max_items]:
        question_ru = _translate_question(m["question"])
        top_outcomes = sorted(m["outcomes"], key=lambda x: -x["probability"])[:2]
        outcomes_str = " / ".join(f"{o['name']}: {o['probability']}%" for o in top_outcomes)
        if m["url"]:
            text += f'• <a href="{m["url"]}">{question_ru}</a>\n'
        else:
            text += f"• {question_ru}\n"
        text += f"  {outcomes_str}\n"
    text += "\n"
    return text

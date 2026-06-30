import requests
import json
from typing import List, Dict

TIMEOUT = 6
GAMMA_BASE = "https://gamma-api.polymarket.com"

# Строгие ключевые слова — только явные крипто-активы, чтобы не ловить случайные совпадения
CRYPTO_KEYWORDS = [
    "bitcoin", "btc ", "btc?", "btc,", "btc.", "ethereum", "eth ", "eth?", "eth.",
    "solana", "sol ", "sol?", "sol.", "dogecoin", "xrp ", "xrp?", "ripple",
    "crypto market", "cryptocurrency", "altcoin", "memecoin"
]

def _parse_json_field(value):
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except Exception:
        return []

def _is_crypto_question(question: str) -> bool:
    q = " " + question.lower() + " "
    return any(k in q for k in CRYPTO_KEYWORDS)

def get_crypto_markets(limit: int = 15) -> List[Dict]:
    """Получить активные крипто-рынки с Polymarket через официальный тег 'Crypto'"""
    try:
        # Сначала пробуем фильтр по тегу crypto
        r = requests.get(
            f"{GAMMA_BASE}/markets",
            params={"active": "true", "closed": "false", "limit": 100, "order": "volume24hr", "ascending": "false", "tag": "crypto"},
            timeout=TIMEOUT
        )
        markets = []
        if r.status_code == 200:
            markets = r.json()
        if not markets:
            # fallback: без тега, фильтруем по ключевым словам вручную
            r2 = requests.get(
                f"{GAMMA_BASE}/markets",
                params={"active": "true", "closed": "false", "limit": 200, "order": "volume24hr", "ascending": "false"},
                timeout=TIMEOUT
            )
            if r2.status_code == 200:
                markets = r2.json()

        results = []
        for m in markets:
            question = m.get("question", "")
            if not _is_crypto_question(question):
                continue
            outcomes = _parse_json_field(m.get("outcomes", "[]"))
            prices = _parse_json_field(m.get("outcomePrices", "[]"))
            if not outcomes or not prices:
                continue
            try:
                volume24h = float(m.get("volume24hr", 0) or 0)
            except Exception:
                volume24h = 0
            if volume24h < 1000:
                continue
            outcome_data = []
            for o, p in zip(outcomes, prices):
                try:
                    pct = round(float(p) * 100, 1)
                except Exception:
                    pct = 0
                outcome_data.append({"name": o, "probability": pct})
            results.append({
                "question": question,
                "outcomes": outcome_data,
                "volume24h": volume24h,
                "url": f"https://polymarket.com/event/{m.get('slug','')}"
            })
            if len(results) >= limit:
                break
        return results
    except Exception as e:
        print("Polymarket error:", e)
        return []

def format_polymarket_section(markets: List[Dict], max_items: int = 5) -> str:
    if not markets:
        return ""
    text = "<b>🎲 Polymarket — мнение толпы по крипте:</b>\n"
    for m in markets[:max_items]:
        q = m["question"][:90]
        top_outcomes = sorted(m["outcomes"], key=lambda x: -x["probability"])[:2]
        outcomes_str = " / ".join(f"{o['name']}: {o['probability']}%" for o in top_outcomes)
        text += f'• <a href="{m["url"]}">{q}</a>\n   {outcomes_str}\n'
    text += "\n"
    return text

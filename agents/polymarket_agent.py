import requests
import json
from typing import List, Dict

TIMEOUT = 6
GAMMA_BASE = "https://gamma-api.polymarket.com"

# Ключевые слова для поиска крипто-рынков на Polymarket
CRYPTO_KEYWORDS = ["bitcoin", "btc", "ethereum", "eth", "solana", "sol ", "crypto", "dogecoin", "xrp"]

def _parse_json_field(value):
    if isinstance(value, list):
        return value
    try:
        return json.loads(value)
    except Exception:
        return []

def get_crypto_markets(limit: int = 15) -> List[Dict]:
    """Получить активные крипто-рынки с Polymarket отсортированные по объёму за 24ч"""
    try:
        r = requests.get(
            f"{GAMMA_BASE}/markets",
            params={"active": "true", "closed": "false", "limit": 100, "order": "volume24hr", "ascending": "false"},
            timeout=TIMEOUT
        )
        if r.status_code != 200:
            print(f"Polymarket fetch failed: status {r.status_code}")
            return []
        markets = r.json()
        results = []
        for m in markets:
            question = m.get("question", "")
            q_lower = question.lower()
            if not any(k in q_lower for k in CRYPTO_KEYWORDS):
                continue
            outcomes = _parse_json_field(m.get("outcomes", "[]"))
            prices = _parse_json_field(m.get("outcomePrices", "[]"))
            if not outcomes or not prices:
                continue
            try:
                volume24h = float(m.get("volume24hr", 0) or 0)
            except Exception:
                volume24h = 0
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

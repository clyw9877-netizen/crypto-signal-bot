"""
Макро-радар: следит за политикой и макроэкономикой, которые двигают
американский рынок и вместе с ним крипту.

Отличие от twitter_agent: тот ловит твиты про конкретные монеты,
этот — про нефть, Иран, ФРС, безработицу, тарифы, пузырь ИИ и т.д.
"""

import json
import os
import re
import time

MACRO_STATE = "data/macro_state.json"
MAX_AGE_HOURS = 24

# Аккаунты: власть, ФРС, макро-ленты и энергетика.
# Недоступные зеркало просто пропустит — бот не упадёт.
MACRO_ACCOUNTS = [
    # Власть США
    "realDonaldTrump", "POTUS", "WhiteHouse", "VP", "PressSec",
    "SecScottBessent", "SecRubio", "StateDept", "federalreserve",
    # Макро- и рыночные ленты
    "DeItaone", "FirstSquawk", "LiveSquawk", "KobeissiLetter",
    "unusual_whales", "zerohedge", "Schuldensuehner",
    # Энергетика и нефть
    "JavierBlas", "OilandEnergy", "EIAgov",
]

# Вес источника: официальные заявления двигают рынок сильнее комментариев.
ACCOUNT_WEIGHT = {
    "realDonaldTrump": 3, "POTUS": 3, "WhiteHouse": 3, "federalreserve": 3,
    "SecScottBessent": 3, "SecRubio": 2, "StateDept": 2, "PressSec": 2, "VP": 2,
    "DeItaone": 2, "FirstSquawk": 2, "LiveSquawk": 2,
}

# risk_off = уход из риска (обычно плохо для крипты и акций)
# risk_on  = аппетит к риску (обычно хорошо)
MACRO_TOPICS = {
    "iran": {
        "label": "🛢 Иран / Ближний Восток",
        "bias": "risk_off",
        "kw": ["iran", "tehran", "hormuz", "strait of hormuz", "irgc",
               "israel strike", "houthi", "red sea", "middle east conflict"],
    },
    "oil": {
        "label": "🛢 Нефть и энергия",
        "bias": "risk_off",
        "kw": ["oil price", "crude", "brent", "wti", "opec", "opec+",
               "barrel", "gas prices", "energy prices", "spr"],
    },
    "fed": {
        "label": "🏛 ФРС и ставка",
        "bias": "neutral",
        "kw": ["federal reserve", "the fed", "fomc", "powell", "interest rate",
               "rate cut", "rate hike", "basis points", "monetary policy",
               "quantitative", "balance sheet"],
    },
    "inflation": {
        "label": "📈 Инфляция",
        "bias": "neutral",
        "kw": ["inflation", "cpi", "ppi", "pce", "consumer prices", "deflation"],
    },
    "jobs": {
        "label": "👷 Рынок труда",
        "bias": "neutral",
        "kw": ["unemployment", "jobless", "jobs report", "payroll", "nonfarm",
               "layoff", "layoffs", "hiring freeze", "labor market", "jolts"],
    },
    "tariffs": {
        "label": "⚖️ Тарифы и торговые войны",
        "bias": "risk_off",
        "kw": ["tariff", "tariffs", "trade war", "trade deal", "sanction",
               "sanctions", "export controls", "embargo"],
    },
    "ai_bubble": {
        "label": "🤖 Пузырь ИИ / технологии",
        "bias": "risk_off",
        "kw": ["ai bubble", "bubble in ai", "nvidia", "capex", "data center",
               "circular deal", "overvalued", "tech selloff", "magnificent seven"],
    },
    "shutdown": {
        "label": "🏚 Госдолг и шатдаун",
        "bias": "risk_off",
        "kw": ["government shutdown", "debt ceiling", "default on", "downgrade",
               "treasury yields", "bond selloff", "national debt"],
    },
    "china": {
        "label": "🇨🇳 Китай / Тайвань",
        "bias": "risk_off",
        "kw": ["china", "beijing", "taiwan", "yuan", "pboc", "xi jinping"],
    },
    "war": {
        "label": "⚔️ Война и геополитика",
        "bias": "risk_off",
        "kw": ["ukraine", "russia", "putin", "nato", "ceasefire", "peace deal",
               "missile", "invasion", "nuclear"],
    },
    "crypto_policy": {
        "label": "🪙 Регулирование крипты",
        "bias": "neutral",
        "kw": ["strategic bitcoin reserve", "crypto regulation", "sec approves",
               "spot etf", "stablecoin bill", "crypto executive order",
               "digital asset"],
    },
    "recession": {
        "label": "📉 Рецессия",
        "bias": "risk_off",
        "kw": ["recession", "hard landing", "soft landing", "gdp contraction",
               "credit crunch", "bank failure", "yield curve"],
    },
}

# Фразы, которые переворачивают знак темы независимо от её базового bias.
DIRECTIONAL = [
    (r"\brate cuts?\b|\bcut(s|ting)? (interest )?rates?\b|\bdovish\b|\blower(s|ed|ing)? rates?\b", "risk_on"),
    (r"\brate hikes?\b|\b(raise|raises|raised|raising|hike|hikes|hiked) (interest )?rates?\b|\bhawkish\b|\bhigher for longer\b", "risk_off"),
    (r"\bceasefire|\bpeace deal|\bde-?escalat|\btruce\b", "risk_on"),
    (r"\bstrike[sd]?\b.*\b(iran|israel)|\bescalat|\battack(ed|s)?\b", "risk_off"),
    (r"\btariff(s)? (paused|delayed|lifted|removed)|\btrade deal reached\b", "risk_on"),
    (r"\bnew tariff|\braising tariff|\bimpos(e|ing) tariff", "risk_off"),
    (r"\binflation (cool|slow|fell|eased)", "risk_on"),
    (r"\binflation (rose|jump|accelerat|hot)", "risk_off"),
    (r"\b(layoffs|jobless claims) (surge|jump|rise|spike)", "risk_off"),
    (r"\bstrategic bitcoin reserve|\bapproves .*(etf|bitcoin)", "risk_on"),
]


def _load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def _save(path, data):
    try:
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "w") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass


def find_topics(text):
    """Какие макро-темы затронуты в тексте."""
    tl = (text or "").lower()
    hits = []
    for key, topic in MACRO_TOPICS.items():
        for kw in topic["kw"]:
            if re.search(r"\b" + re.escape(kw) + r"\b", tl):
                hits.append(key)
                break
    return hits


def classify_bias(text, topics):
    """risk_on / risk_off / neutral. Направленные фразы важнее базового bias темы."""
    tl = (text or "").lower()
    for pattern, bias in DIRECTIONAL:
        if re.search(pattern, tl):
            return bias
    for key in topics:
        bias = MACRO_TOPICS[key]["bias"]
        if bias != "neutral":
            return bias
    return "neutral"


def record_event(username, text, url):
    """Сохраняет макро-событие, если оно относится к отслеживаемым темам."""
    topics = find_topics(text)
    if not topics:
        return None
    bias = classify_bias(text, topics)
    weight = ACCOUNT_WEIGHT.get(username, 1)
    event = {
        "username": username,
        "text": text[:400],
        "url": url,
        "topics": topics,
        "bias": bias,
        "weight": weight,
        "ts": time.time(),
    }
    events = _load(MACRO_STATE, [])
    events.append(event)
    cutoff = time.time() - MAX_AGE_HOURS * 3600
    events = [e for e in events if e.get("ts", 0) > cutoff][-80:]
    _save(MACRO_STATE, events)
    return event


def recent_events(max_age_hours=MAX_AGE_HOURS):
    cutoff = time.time() - max_age_hours * 3600
    events = _load(MACRO_STATE, [])
    fresh = [e for e in events if e.get("ts", 0) > cutoff]
    fresh.sort(key=lambda e: (-e.get("weight", 1), -e.get("ts", 0)))
    return fresh


def get_macro_bias(max_age_hours=6):
    """Общий фон рынка за последние часы.
    Возвращает {"bias": ..., "score": int, "reasons": [...]}"""
    score = 0
    reasons = []
    for e in recent_events(max_age_hours):
        if e["bias"] == "risk_on":
            score += e.get("weight", 1)
        elif e["bias"] == "risk_off":
            score -= e.get("weight", 1)
        else:
            continue
        if len(reasons) < 3:
            label = MACRO_TOPICS[e["topics"][0]]["label"]
            reasons.append(f"{label} (@{e['username']})")
    if score >= 3:
        bias = "risk_on"
    elif score <= -3:
        bias = "risk_off"
    else:
        bias = "neutral"
    return {"bias": bias, "score": score, "reasons": reasons}


BIAS_RU = {
    "risk_on": "🟢 Аппетит к риску",
    "risk_off": "🔴 Уход из риска",
    "neutral": "⚪ Нейтрально",
}


def format_macro_section(max_items=5, max_age_hours=MAX_AGE_HOURS):
    """Секция для дайджеста. Lпортыват tr внутри — что быр�-]R�-��=-�]-�]r�=mM��"" �g&��vV�G2�G&�6�FR���'BG ��WfV�G2�&V6V�E�WfV�G2����vU���W'2���b��BWfV�G3��&WGW&�" ���fW&���vWE��7&��&�2����vU���W'2��FW�B�#�#�	���	����M��#��� �FW�B��b-
M�������#�$�5�%U��fW&�Ųv&�2u�����#����� ��6VV��6WB���6��v�� �f�"R��WfV�G3���W��U�'FW�B%ճ�cТ�b�W���6VV㠢6��F��VP�6VV��FB��W�����&V���5$��D��55�U�'F��72%ճ�ղ&�&V�%Т�&���'&�6����#�/	��""�'&�6���fb#�/	�KB"�&�WWG&�#�.)��'նU�&&�2%�Т7V��'��G"�U�'FW�B%ҕ��##ТFW�B��bw��&���#��&V����#�+r�U�'W6W&��R%����p��bR�vWB�'W&�"���FW�B��bs��&Vc�'�U�'W&�%��#�7V��'���������p�V�6S��FW�B��b'�7V��'������ ��6��v�����b6��v�������FV�3��'&V��&WGW&�FW�@
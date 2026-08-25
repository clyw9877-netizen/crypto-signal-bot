import requests
import json
import os
import re
import time
from bs4 import BeautifulSoup
from agents.sentiment import detect_sentiment
from agents.macro_agent import MACRO_ACCOUNTS, record_event as record_macro_event

# Список зеркал собран по памяти — публичные nitter-инстансы очень нестабильны
# и часто отключаются без предупреждения. Гарантии, что все живы, нет:
# при добавлении новых стоит время от времени чистить мёртвые вручную.
MIRRORS = [
    "https://xcancel.com", "https://nitter.net", "https://nitter.poast.org",
    "https://nitter.privacydev.net", "https://lightbrd.com",
]
# Таймаут снижен с 8 до 5 — иначе при добавлении зеркал худший случай
# (все мертвы, все 27 аккаунтов) растягивается на 10+ минут и блокирует бота,
# как это уже было с проверкой ссылок Polymarket.
TIMEOUT = 5

FAILURES_FILE = "data/twitter_failures.json"
_last_fetch_ok = {}
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

ACCOUNTS = [
    "elonmusk", "realDonaldTrump",
    "VitalikButerin", "saylor", "cz_binance",
    "WatcherGuru", "DocumentingBTC", "APompliano",
]

COIN_KEYWORDS = {
    "BTC": ["bitcoin", "btc"],
    "ETH": ["ethereum", "eth"],
    "SOL": ["solana"],
    "BNB": ["binance coin"],
    "XRP": ["xrp", "ripple"],
    "DOGE": ["dogecoin", "doge"],
    "ADA": ["cardano"],
    "AVAX": ["avalanche", "avax"],
    "DOT": ["polkadot"],
    "MATIC": ["polygon", "matic"],
    "LTC": ["litecoin", "ltc"],
    "LINK": ["chainlink"],
    "UNI": ["uniswap"],
    "ATOM": ["cosmos"],
    "ETC": ["ethereum classic"],
    "TRX": ["tron", "trx"],
    "NEAR": ["near protocol"],
    "FTM": ["fantom", "ftm"],
    "OP": ["optimism"],
    "ARB": ["arbitrum"],
    "SUI": ["sui network", "sui blockchain"],
    "INJ": ["injective"],
    "WIF": ["dogwifhat", "wif"],
    "PEPE": ["pepe"],
    "SHIB": ["shiba inu", "shib"],
}

CASHTAG_COINS = {
    "BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "DOT", "MATIC",
    "LTC", "LINK", "UNI", "ATOM", "ETC", "TRX", "NEAR", "FTM", "OP", "ARB",
    "SUI", "INJ", "WIF", "PEPE", "SHIB",
}

STATE_FILE = "data/twitter_state.json"
SENTIMENT_FILE = "data/twitter_sentiment.json"


def _load_json(path):
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_json(path, data):
    try:
        with open(path, "w") as f:
            json.dump(data, f)
    except Exception:
        pass


def _load_state():
    return _load_json(STATE_FILE)


def _save_state(state):
    _save_json(STATE_FILE, state)


def _fetch_profile_html(username):
    for base in MIRRORS:
        try:
            r = requests.get(f"{base}/{username}", headers={"User-Agent": UA}, timeout=TIMEOUT)
            if r.status_code == 200 and "timeline-item" in r.text:
                _last_fetch_ok[username] = True
                return r.text, base
        except Exception:
            continue
    _last_fetch_ok[username] = False
    return None, None


def _parse_tweets(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    tweets = []
    for item in soup.find_all("div", class_="timeline-item"):
        link = item.find("a", class_="tweet-link")
        if not link or not link.get("href"):
            continue
        href = link["href"]
        if "/status/" not in href:
            continue
        tweet_id = href.split("/status/")[1].split("#")[0].split("?")[0]
        content_div = item.find("div", class_="tweet-content")
        text = content_div.get_text(" ", strip=True) if content_div else ""
        is_retweet = item.find(class_="retweet-header") is not None
        tweets.append({"id": tweet_id, "text": text, "url": base_url + href.split("#")[0], "is_retweet": is_retweet})
    return tweets


def _find_coins(text):
    tl = text.lower()
    found = []
    for symbol, keywords in COIN_KEYWORDS.items():
        for kw in keywords:
            if re.search(r"\b" + re.escape(kw) + r"\b", tl):
                found.append(symbol)
                break
    for m in re.finditer(r"\$([a-zA-Z]{2,6})\b", text):
        symbol = m.group(1).upper()
        if symbol in CASHTAG_COINS and symbol not in found:
            found.append(symbol)
    return found


def _record_sentiment(username, text, coins):
    sentiment_state = _load_json(SENTIMENT_FILE)
    direction = detect_sentiment(text)
    if direction == "neutral":
        return
    now = time.time()
    for coin in coins:
        sentiment_state[coin] = {"direction": direction, "ts": now, "source": username, "text": text[:200]}
    _save_json(SENTIMENT_FILE, sentiment_state)


def get_recent_sentiment(symbol_base, max_age_hours=2):
    sentiment_state = _load_json(SENTIMENT_FILE)
    entry = sentiment_state.get(symbol_base)
    if not entry:
        return None
    age_hours = (time.time() - entry.get("ts", 0)) / 3600
    if age_hours > max_age_hours:
        return None
    return entry.get("direction")


def check_account(username, state):
    html, base = _fetch_profile_html(username)
    if not html:
        return []
    tweets = _parse_tweets(html, base)
    if not tweets:
        return []
    last_seen_id = state.get(username)
    if last_seen_id is None:
        state[username] = tweets[0]["id"]
        return []
    fresh = []
    for t in tweets:
        if t["id"] == last_seen_id:
            break
        fresh.append(t)
    alerts = []
    for t in reversed(fresh):
        if t["is_retweet"]:
            continue
        coins = _find_coins(t["text"])
        if coins:
            _record_sentiment(username, t["text"], coins)
            alerts.append({"username": username, "text": t["text"], "url": t["url"], "coins": coins})
        else:
            # Твит без монет всё равно может двигать рынок:
            # Иран, нефть, ФРС, безработица, тарифы, пузырь ИИ.
            try:
                record_macro_event(username, t["text"], t["url"])
            except Exception as e:
                print("macro record error:", e)
    state[username] = tweets[0]["id"]
    return alerts


def all_accounts():
    """Крипто-аккаунты + макро-аккаунты, без дублей."""
    merged = list(ACCOUNTS)
    for u in MACRO_ACCOUNTS:
        if u not in merged:
            merged.append(u)
    return merged


def check_all_accounts(usernames=None):
    usernames = usernames or all_accounts()
    state = _load_state()
    all_alerts = []
    _last_fetch_ok.clear()
    for u in usernames:
        try:
            all_alerts.extend(check_account(u, state))
        except Exception as e:
            print(f"Twitter monitor error for {u}:", e)
    _save_state(state)

    failed = [u for u in usernames if _last_fetch_ok.get(u) is False]
    _save_json(FAILURES_FILE, {
        "total": len(usernames),
        "failed": failed,
        "ts": time.time(),
    })
    return all_alerts


def get_failure_summary():
    """Сколько аккаунтов не удалось проверить на последнем проходе.
    Возвращает None, если проверок ещё не было или все прошли успешно."""
    data = _load_json(FAILURES_FILE)
    if not data or not data.get("failed"):
        return None
    return {"total": data.get("total", 0), "failed_count": len(data["failed"])}


def format_alert(alert):
    coins_str = ", ".join(alert["coins"])
    return (
        f"🚨 <b>Твит про {coins_str}</b>\n\n"
        f"👤 @{alert['username']}\n"
        f"💬 {alert['text']}\n\n"
        f"🔗 {alert['url']}"
    )

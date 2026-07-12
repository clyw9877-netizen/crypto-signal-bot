import requests
import json
import os
import re
from bs4 import BeautifulSoup

MIRRORS = ["https://xcancel.com", "https://nitter.net", "https://nitter.poast.org"]
TIMEOUT = 8
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36"

ACCOUNTS = ["elonmusk", "realDonaldTrump"]

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


def _load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_state(state):
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass


def _fetch_profile_html(username):
    for base in MIRRORS:
        try:
            r = requests.get(f"{base}/{username}", headers={"User-Agent": UA}, timeout=TIMEOUT)
            if r.status_code == 200 and "timeline-item" in r.text:
                return r.text, base
        except Exception:
            continue
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
            alerts.append({"username": username, "text": t["text"], "url": t["url"], "coins": coins})
    state[username] = tweets[0]["id"]
    return alerts


def check_all_accounts(usernames=None):
    usernames = usernames or ACCOUNTS
    state = _load_state()
    all_alerts = []
    for u in usernames:
        try:
            all_alerts.extend(check_account(u, state))
        except Exception as e:
            print(f"Twitter monitor error for {u}:", e)
    _save_state(state)
    return all_alerts


def format_alert(alert):
    coins_str = ", ".join(alert["coins"])
    return (
        f"🚨 <b>Твит про {coins_str}!</b>\n\n"
        f"👤 @{alert['username']}\n"
        f"💬 {alert['text']}\n\n"
        f"🔗 {alert['url']}"
    )

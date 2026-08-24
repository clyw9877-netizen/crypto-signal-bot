"""
Универсальный перевод EN → RU с кэшем на диске.

Используется для заголовков новостей, вопросов Polymarket и названий
событий календаря — то, что нельзя покрыть словарём шаблонов,
потому что формулировки меняются каждый день.

Порядок: кэш → Google (бесплатный эндпоинт, без ключа) → MyMemory.
При любой ошибке возвращается оригинал, бот не падает.
"""

import json
import os
import re
import threading
import time

import requests

CACHE_PATH = os.getenv("TRANSLATE_CACHE", "data/translate_cache.json")
TIMEOUT = 8

_lock = threading.Lock()
_cache = {}

try:
    with open(CACHE_PATH, encoding="utf-8") as f:
        _cache = json.load(f)
except Exception:
    _cache = {}


def _save_cache():
    try:
        os.makedirs(os.path.dirname(CACHE_PATH) or ".", exist_ok=True)
        with open(CACHE_PATH, "w", encoding="utf-8") as f:
            json.dump(_cache, f, ensure_ascii=False)
    except Exception:
        pass


# Тикеры и имена собственные, которые переводчик коверкает.
# Прячем их под плейсхолдеры перед отправкой и возвращаем обратно.
PROTECT = [
    "BTC", "ETH", "SOL", "XRP", "DOGE", "ADA", "BNB", "WIF", "PEPE", "USDT",
    "S&P 500", "Nasdaq", "SEC", "ETF", "RSI", "CPI", "PPI", "PCE", "FOMC",
    "GDP", "JOLTS", "Polymarket", "Coinbase", "Binance", "MicroStrategy",
    "BlackRock", "MtGox", "Tether", "Kalshi",
]

# Косяки машинного перевода в крипто-контексте.
FIXES = [
    (r"\bБиткойн\w*", "биткоин"),
    (r"\bБиткоин(а|ом|у|е)\b", "биткоина"),
    (r"\bЭфириум\w*", "Ethereum"),
    (r"\bперекупленн?ый RSI\b", "перекупленность по RSI"),
    (r"\bмедвежьей торговле\b", "на медвежьем рынке"),
    (r"\bбычьей торговле\b", "на бычьем рынке"),
    (r"\bФедеральн(а�ратратска) етароварсца uny=+\w*", "ФРС"),
    (r"\bФРС США\b", "ФРС"),
    (r"\bдоля рынка\b", "доминация"),
    (r"\s{2,}", " "),
]


def has_cyrillic(text: str) -> bool:
    return bool(re.search(r"[а-яА-Яёс]", text or ""))


def _protect(text: str):
    """Прячет тикеры под плейсхолдеры. Только целые слова и ??
    в том же регистре — иначе SEC ломает "Secretary", а ETH — "Hegseth"."""
    saved = {}
    for i, token in enumerate(PROTECT):
        pattern = r"(?<![A-Za-z0-9])" + re.escape(token) + r"(?![A-Za-z0-9])"
        if re.search(pattern, text):
            key = "QQ%dQQ" % i
            text = re.sub(pattern, key, text)
            saved[key] = token
    return text, saved


def _restore(text: str, saved: dict) -> str:
    for key, token in saved.items():
        text = text.replace(key, token)
    return text


def _google(text: str) -> str:
    r = requests.get(
        "https://translate.googleapis.com/translate_a/single",
        params={"client": "gtx", "sl": "en", "tl": "ru", "dt": "t", "q": text},
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return "".join(chunk[0] for chunk in r.json()[0] if chunk[0])


def _mymemory(text: str) -> str:
    r = requests.get(
        "https://api.mymemory.translated.net/get",
        params={"q": text[:490], "langpair": "en|ru"},
        timeout=TIMEOUT,
    )
    r.raise_for_status()
    return r.json()["responseData"]["translatedText"]


def polish(text: str) -> str:
    """Чистит перевод и ставит заглавную букву в начале."""
    text = (text or "").strip()
    for pattern, repl in FIXES:
        text = re.sub(pattern, repl, text)
    text = text.strip()
    if text and text[0].islower():
        text = text[0].upper() + text[1:]
    return text


def tr(text: str) -> str:
    """EN → RU. Уже русский текст возвращается как есть."""
    text = (text or "").strip()
    if not text or has_cyrillic(text):
        return polish(text)

    with _lock:
        if text in _cache:
            return _cache[text]

    protected, saved = _protect(text)
    result = None
    for engine in (_google, _mymemory):
        try:
            result = _restore(engine(protected), saved)
            break
        except Exception as e:
            print("translate error (%s): %s" % (engine.__name__, e))
            time.sleep(0.4)

    if not result:
        return text

    result = polish(result)
    with _lock:
        _cache[text] = result
        _save_cache()
    return result

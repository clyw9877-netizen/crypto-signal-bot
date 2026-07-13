import re
from config import COINS
from agents.data_agent import get_candles, get_all_prices, get_24h_stats
from agents.smc_agent import analyze_candles
from agents.decision_agent import enrich_signal
from agents.news_agent import get_crypto_news

COIN_ALIASES = {
    "BTC": ["btc", "bitcoin", "биткоин", "биток"],
    "ETH": ["eth", "ethereum", "эфир", "эфириум"],
    "SOL": ["sol", "solana", "солана"],
    "BNB": ["bnb", "binance coin"],
    "XRP": ["xrp", "ripple", "рипл"],
    "DOGE": ["doge", "dogecoin", "додж", "доге"],
    "ADA": ["ada", "cardano", "кардано"],
    "AVAX": ["avax", "avalanche"],
    "DOT": ["dot", "polkadot"],
    "MATIC": ["matic", "polygon"],
    "LTC": ["ltc", "litecoin", "лайткоин"],
    "LINK": ["link", "chainlink"],
    "UNI": ["uni", "uniswap"],
    "ATOM": ["atom", "cosmos"],
    "ETC": ["etc"],
    "TRX": ["trx", "tron", "трон"],
    "NEAR": ["near"],
    "FTM": ["ftm", "fantom"],
    "OP": ["op", "optimism"],
    "ARB": ["arb", "arbitrum"],
    "SUI": ["sui"],
    "INJ": ["inj", "injective"],
    "WIF": ["wif", "dogwifhat"],
    "PEPE": ["pepe"],
    "SHIB": ["shib", "shiba"],
    "HYPE": ["hype", "hyperliquid", "хайп"],
}

MARKET_WORDS = ["рынок", "маркет", "market", "обстановка", "ситуация"]
NEWS_WORDS = ["новост", "news"]

STOPWORDS = {"как", "рынок", "маркет", "что", "цена", "цены", "монета", "монету", "монеты",
             "по", "на", "за", "market", "price", "news", "новости", "и", "в", "у", "с", "из", "го"}


def _find_symbol_in_text(text):
    tl = text.lower()
    for base, aliases in COIN_ALIASES.items():
        for a in aliases:
            if re.search(r"\b" + re.escape(a) + r"\b", tl):
                return f"{base}-USDT"
    return _find_symbol_on_exchange(text)


def _find_symbol_on_exchange(text):
    tl = text.lower()
    candidate = None
    m = re.search(r"\b([a-z0-9]{2,10})[\s/\-]?usdt\b", tl)
    if m:
        candidate = m.group(1).upper()
    else:
        words = re.findall(r"[a-zA-Zа-яА-Я0-9]{2,10}", text)
        candidates = [w for w in words if w.lower() not in STOPWORDS and not w.isdigit()]
        if len(candidates) == 1:
            candidate = candidates[0].upper()
    if not candidate:
        return None
    symbol = f"{candidate}-USDT"
    try:
        stats = get_24h_stats(symbol)
    except Exception:
        stats = None
    if stats and stats.get("price"):
        return symbol
    return None


def _format_coin_reply(symbol):
    candles = get_candles(symbol, "1h", 100)
    if not candles or len(candles) < 30:
        return f"Не могу получить данные по {symbol} сейчас."
    price = candles[-1]["close"]
    change = 0.0
    if len(candles) >= 25:
        change = (candles[-1]["close"] - candles[-25]["close"]) / candles[-25]["close"] * 100

    signal = analyze_candles(symbol, candles)
    news = []
    try:
        news = get_crypto_news()
    except Exception:
        pass
    signal = enrich_signal(dict(signal), symbol, news)

    lines = [f"<b>{symbol}</b>: ${price:,.2f} ({change:+.1f}% за ~24ч)"]
    if signal.get("signal") in ("long", "short"):
        dir_text = "ЛОНГ 🟢" if signal["signal"] == "long" else "ШОРТ 🔴"
        lines.append(f"Сетап: {dir_text}, уверенность {signal['confidence']}%")
        for r in signal.get("reasons", [])[:3]:
            lines.append(f"• {r}")
        verdict = "можно рассматривать вход" if signal["confidence"] >= 65 else "сигнал слабый, я бы подождал"
        lines.append(f"Итог: {verdict}")
    else:
        lines.append("Чёткого сетапа по смарт-мани сейчас нет — жду.")
    return "\n".join(lines)


def _format_market_overview():
    lines = ["<b>📊 Обзор рынка</b>"]
    for sym in COINS:
        try:
            stats = get_24h_stats(sym)
        except Exception:
            stats = None
        if not stats or not stats.get("price"):
            continue
        price = stats["price"]
        change = stats.get("change", 0.0)
        emoji = "🟢" if change >= 0 else "🔴"
        base = sym.replace("-USDT", "")
        price_str = f"${price:,.2f}" if price >= 1 else f"${price:,.6f}"
        lines.append(f"{emoji} <b>{base}</b>: {price_str} ({change:+.1f}%)")
    if len(lines) == 1:
        return "Не могу получить цены прямо сейчас."
    return "\n".join(lines)


def _format_news_reply():
    try:
        news = get_crypto_news()
    except Exception:
        news = []
    if not news:
        return "Свежих новостей сейчас не вижу."
    lines = ["<b>Последние новости:</b>"]
    for n in news[:5]:
        lines.append(f"• {n['title']}")
    return "\n".join(lines)


def handle_message(text):
    if not text:
        return None
    symbol = _find_symbol_in_text(text)
    if symbol:
        return _format_coin_reply(symbol)
    tl = text.lower()
    if any(w in tl for w in NEWS_WORDS):
        return _format_news_reply()
    if any(w in tl for w in MARKET_WORDS):
        return _format_market_overview()
    return None

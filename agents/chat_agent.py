import re
from config import COINS
from agents.data_agent import get_candles, get_all_prices
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
}

MARKET_WORDS = ["рынок", "market", "обстановка", "ситуация"]
NEWS_WORDS = ["новост", "news"]


def _find_symbol_in_text(text):
    tl = text.lower()
    for base, aliases in COIN_ALIASES.items():
        for a in aliases:
            if re.search(r"\b" + re.escape(a) + r"\b", tl):
                symbol = f"{base}-USDT"
                if symbol in COINS:
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
    prices = get_all_prices(["BTC-USDT", "ETH-USDT", "SOL-USDT"])
    lines = ["<b>Обзор рынка</b>"]
    for sym in ["BTC-USDT", "ETH-USDT", "SOL-USDT"]:
        p = prices.get(sym)
        if p:
            lines.append(f"{sym}: ${p:,.2f}")
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

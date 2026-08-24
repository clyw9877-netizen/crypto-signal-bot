from agents.sentiment import detect_sentiment
from agents.twitter_agent import get_recent_sentiment as get_twitter_sentiment
from agents.macro_agent import get_macro_bias


def _news_sentiment_for(symbol_base, news_list):
    matches = [n for n in news_list if symbol_base in n.get("currencies", [])]
    if not matches:
        return None
    bulls = sum(1 for n in matches if detect_sentiment(n.get("title", "")) == "bullish")
    bears = sum(1 for n in matches if detect_sentiment(n.get("title", "")) == "bearish")
    if bulls > bears:
        return "bullish"
    if bears > bulls:
        return "bearish"
    return None


def enrich_signal(signal, symbol, news_list):
    if not signal or signal.get("signal") in (None, "none"):
        return signal

    direction = signal["signal"]
    expected = "bullish" if direction == "long" else "bearish"
    base = symbol.split("-")[0]

    votes = []
    tw = get_twitter_sentiment(base)
    if tw:
        votes.append(("Twitter", tw))
    nw = _news_sentiment_for(base, news_list)
    if nw:
        votes.append(("Новости", nw))

    # Макро-фон: Иран, нефть, ФРС, безработица, тарифы.
    # Крипта ходит за американским рынком риска, поэтому фон учитываем.
    try:
        macro = get_macro_bias()
        if macro["bias"] == "risk_on":
            votes.append(("Макро-фон", "bullish"))
        elif macro["bias"] == "risk_off":
            votes.append(("Макро-фон", "bearish"))
    except Exception as e:
        print("macro bias error:", e)

    agree = [name for name, v in votes if v == expected]
    conflict = [name for name, v in votes if v != expected]

    bonus = 0
    reasons = list(signal.get("reasons", []))

    if conflict:
        bonus -= 20 * len(conflict)
        reasons.append(f"⚠️ Против сигнала: {', '.join(conflict)}")
    if agree:
        if len(agree) == len(votes) and len(votes) >= 2:
            bonus += 15
            reasons.append(f"✅ Подтверждено: {', '.join(agree)}")
        elif not conflict:
            bonus += 5
            reasons.append(f"Подтверждено: {', '.join(agree)}")

    new_confidence = max(0, min(99, signal["confidence"] + bonus))
    signal["confidence"] = new_confidence
    signal["reasons"] = reasons
    if new_confidence < 50:
        signal["signal"] = "none"
    return signal

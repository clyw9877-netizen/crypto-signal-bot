BULLISH_WORDS = [
    "surge", "soar", "rally", "bullish", "moon", "breakout", "pump", "adoption",
    "partnership", "buy the dip", "upgrade", "approve", "approval", "record high",
    "all-time high", "ath", "outperform", "accumulate", "green light", "inflow",
    "institutional buying", "etf approved", "buy",
]
BEARISH_WORDS = [
    "crash", "plunge", "dump", "bearish", "sell-off", "selloff", "hack", "exploit",
    "ban", "lawsuit", "sue", "sues", "delist", "collapse", "fraud", "scam",
    "investigation", "sec charges", "warning", "recession", "outflow", "liquidated",
    "liquidation", "shutdown", "bankrupt", "bankruptcy",
]


def detect_sentiment(text: str) -> str:
    tl = text.lower()
    bull = sum(1 for w in BULLISH_WORDS if w in tl)
    bear = sum(1 for w in BEARISH_WORDS if w in tl)
    if bull > bear:
        return "bullish"
    if bear > bull:
        return "bearish"
    return "neutral"

def calc_rsi(candles, period=14):
    if len(candles) < period + 1:
        return 50.0
    closes = [c["close"] for c in candles]
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i - 1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def calc_atr(candles, period=14):
    if len(candles) < period:
        return candles[-1]["close"] * 0.01
    trs = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i - 1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)
    return sum(trs[-period:]) / period


def find_swings(candles, threshold_pct=2.0):
    if len(candles) < 3:
        return []
    swings = []
    trend = None
    start_idx = 0
    start_price = candles[0]["close"]
    extreme_idx = 0
    extreme_price = candles[0]["close"]
    for i in range(1, len(candles)):
        c = candles[i]
        if trend is None:
            if c["high"] >= extreme_price * (1 + threshold_pct / 100):
                trend = "up"
                swings.append({"idx": start_idx, "price": start_price, "type": "low"})
                extreme_price = c["high"]
                extreme_idx = i
            elif c["low"] <= extreme_price * (1 - threshold_pct / 100):
                trend = "down"
                swings.append({"idx": start_idx, "price": start_price, "type": "high"})
                extreme_price = c["low"]
                extreme_idx = i
            continue
        if trend == "up":
            if c["high"] > extreme_price:
                extreme_price = c["high"]
                extreme_idx = i
            elif c["low"] <= extreme_price * (1 - threshold_pct / 100):
                swings.append({"idx": extreme_idx, "price": extreme_price, "type": "high"})
                trend = "down"
                extreme_price = c["low"]
                extreme_idx = i
        else:
            if c["low"] < extreme_price:
                extreme_price = c["low"]
                extreme_idx = i
            elif c["high"] >= extreme_price * (1 + threshold_pct / 100):
                swings.append({"idx": extreme_idx, "price": extreme_price, "type": "low"})
                trend = "up"
                extreme_price = c["high"]
                extreme_idx = i
    swings.append({"idx": extreme_idx, "price": extreme_price, "type": "high" if trend == "up" else "low"})
    return swings


def _wave_len(a, b):
    return abs(b["price"] - a["price"])


def classify_impulse(swings):
    if len(swings) < 6:
        return None
    pts = swings[-6:]
    types = [p["type"] for p in pts]

    if types == ["low", "high", "low", "high", "low", "high"]:
        direction = "bullish"
    elif types == ["high", "low", "high", "low", "high", "low"]:
        direction = "bearish"
    else:
        return None

    p0, p1, p2, p3, p4, p5 = pts
    w1 = _wave_len(p0, p1)
    w3 = _wave_len(p2, p3)
    w5 = _wave_len(p4, p5)

    if direction == "bullish":
        if p2["price"] <= p0["price"]:
            return None
        if w3 < w1 and w3 < w5:
            return None
        if p4["price"] <= p1["price"]:
            return None
    else:
        if p2["price"] >= p0["price"]:
            return None
        if w3 < w1 and w3 < w5:
            return None
        if p4["price"] >= p1["price"]:
            return None

    return {
        "direction": direction,
        "points": pts,
        "wave3_extended": w3 > w1 and w3 > w5,
        "wave5_extended": w5 > w3,
        "w1": w1, "w3": w3, "w5": w5,
    }


def classify_correction(swings):
    if len(swings) < 9:
        return None
    impulse = classify_impulse(swings[-9:-3])
    if not impulse:
        return None
    pts = swings[-3:]
    types = [p["type"] for p in pts]
    p5 = impulse["points"][-1]

    if impulse["direction"] == "bullish":
        if types != ["low", "high", "low"]:
            return None
        c = pts[-1]
        retrace = (p5["price"] - c["price"]) / impulse["w5"] if impulse["w5"] else 0
        if not (0.382 <= retrace <= 1.0):
            return None
        return {"trend_direction": "bullish", "impulse": impulse, "points": pts, "retrace": retrace}
    else:
        if types != ["high", "low", "high"]:
            return None
        c = pts[-1]
        retrace = (c["price"] - p5["price"]) / impulse["w5"] if impulse["w5"] else 0
        if not (0.382 <= retrace <= 1.0):
            return None
        return {"trend_direction": "bearish", "impulse": impulse, "points": pts, "retrace": retrace}


def analyze_candles(symbol, candles):
    if len(candles) < 40:
        return {"signal": "none", "confidence": 0}

    current_price = candles[-1]["close"]
    rsi = calc_rsi(candles)
    atr = calc_atr(candles)
    swings = find_swings(candles, threshold_pct=2.0)

    direction = None
    confidence = 0
    reasons = []
    invalidation = None

    correction = classify_correction(swings)
    impulse = None if correction else classify_impulse(swings)

    if correction:
        direction = "long" if correction["trend_direction"] == "bullish" else "short"
        confidence = 60
        reasons.append(f"Коррекция ABC завершена ({correction['retrace']*100:.0f}% от волны 5)")
        invalidation = correction["points"][-1]["price"]
        if 0.5 <= correction["retrace"] <= 0.618:
            confidence += 15
            reasons.append("Откат в зоне Фибо 50-61.8%")
    elif impulse:
        direction = "long" if impulse["direction"] == "bullish" else "short"
        if impulse.get("wave3_extended") or not impulse.get("wave5_extended"):
            confidence = 55
            reasons.append("Импульс: волна 3 или ранняя волна 5")
        else:
            confidence = 40
            reasons.append("Волна 5 растянута — риск разворота")
        invalidation = impulse["points"][-2]["price"]

    if direction is None:
        return {"signal": "none", "confidence": 0}

    if direction == "long" and rsi < 45:
        confidence += 10
        reasons.append(f"RSI поддерживает вход ({rsi:.0f})")
    elif direction == "short" and rsi > 55:
        confidence += 10
        reasons.append(f"RSI поддерживает вход ({rsi:.0f})")

    if confidence < 50 or not invalidation:
        return {"signal": "none", "confidence": confidence}

    buffer = atr * 0.3
    max_distance = atr * 6
    if direction == "long":
        sl = invalidation - buffer
        if sl >= current_price or (current_price - sl) > max_distance:
            sl = current_price - atr * 2
        tp = current_price + (current_price - sl) * 2
    else:
        sl = invalidation + buffer
        if sl <= current_price or (sl - current_price) > max_distance:
            sl = current_price + atr * 2
        tp = current_price - (sl - current_price) * 2

    if tp <= 0:
        return {"signal": "none", "confidence": confidence}

    rr = abs(tp - current_price) / abs(sl - current_price)
    return {
        "signal": direction,
        "confidence": min(int(confidence), 99),
        "symbol": symbol,
        "price": current_price,
        "sl": sl,
        "tp": tp,
        "rr": rr,
        "rsi": rsi,
        "reasons": reasons,
        "has_sweep": False,
        "has_bos": False,
        "has_fvg": False,
        "atr": atr,
    }

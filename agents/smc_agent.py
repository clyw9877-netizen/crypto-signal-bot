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


DONCHIAN = 20


def donchian_channel(candles, n=DONCHIAN, offset=1):
    """Верхний/нижний уровень канала — та же логика, что в личном скринере
    пробоев. offset=1 исключает текущую свечу, чтобы уровень был реальным
    прошлым уровнем, а не включал саму пробойную свечу."""
    window = candles[-(n + offset):-offset] if offset else candles[-n:]
    if len(window) < n:
        return None, None
    return max(c["high"] for c in window), min(c["low"] for c in window)


def _body_ratio(c):
    rng = c["high"] - c["low"]
    return abs(c["close"] - c["open"]) / rng if rng else 0.0


def _avg_volume(candles, n=20):
    vols = [c.get("volume", 0) for c in candles[-n - 1:-1]]
    if not vols or sum(vols) == 0:
        return None
    return sum(vols) / len(vols)


def classify_breakout(candles):
    """Пробой уровня — как в личном скринере пробоев (core.py).
    Ищем только СВЕЖИЙ пробой: цена только что вышла за канал Дончиана,
    с подтверждением объёмом (если объём известен) и сильным телом свечи.
    Монеты, которые просто подходят к уровню ("watch" в терминологии
    скринера), сигнала не дают — только реальный пробой."""
    if len(candles) < DONCHIAN + 5:
        return None
    last = candles[-1]
    close = last["close"]
    hi, lo = donchian_channel(candles)
    if hi is None or hi <= 0 or lo <= 0:
        return None

    dist_hi = (close / hi - 1) * 100
    dist_lo = (close / lo - 1) * 100
    body = _body_ratio(last)

    avg_vol = _avg_volume(candles)
    rvol = (last.get("volume", 0) / avg_vol) if avg_vol else None
    vol_ok = (rvol > 1.8) if rvol is not None else True

    if 0.05 < dist_hi < 1.2 and vol_ok and body > 0.55:
        return {"direction": "long", "level": hi, "rvol": rvol, "body": body, "dist": dist_hi}
    if -1.2 < dist_lo < -0.05 and vol_ok and body > 0.55:
        return {"direction": "short", "level": lo, "rvol": rvol, "body": body, "dist": dist_lo}
    return None


def _fib_extension_levels(direction, entry, leg_len, ratios=(1.0, 1.272, 1.618, 2.0)):
    """Фибо-расширения последней волны, спроецированные от входа.
    Нужны, когда цена идёт на новый экстремум и позади неё нет
    ни одного реального свинга — единственный ориентир."""
    levels = []
    for r in ratios:
        dist = leg_len * r
        levels.append(entry + dist if direction == "long" else entry - dist)
    return levels


def calc_take_profits(direction, entry, sl, swings, max_levels=5, min_gap_mult=0.5, atr=None):
    """Несколько тейков по реальным уровням вместо одного механического 1:2.

    Берём свинг-хаи (для лонга) или свинг-лои (для шорта) впереди по цене —
    это места, где цена уже разворачивалась раньше и с высокой вероятностью
    отреагирует снова. Добавляем фибо-расширения последней волны на случай
    движения на новый экстремум, где старых уровней просто нет.

    Количество уровней НЕ фиксировано: может быть один, может быть пять —
    зависит от того, сколько реальных уровней нашлось на этом конкретном
    движении. Близкие уровни схлопываются в один — иначе тейки стоят
    почти впритык и не несут смысла. Первый тейк не может быть ближе
    половины риска до стопа, иначе RR слишком плохой, чтобы быть целью.
    """
    risk = abs(entry - sl)
    if risk <= 0:
        return []
    min_gap = (atr or risk * 0.3) * min_gap_mult

    candidates = []
    kind = "high" if direction == "long" else "low"
    for s in swings:
        price = s["price"]
        if s["type"] != kind:
            continue
        if direction == "long" and price > entry:
            candidates.append(price)
        elif direction == "short" and price < entry:
            candidates.append(price)

    if len(swings) >= 2:
        leg_len = abs(swings[-1]["price"] - swings[-2]["price"])
        if leg_len > 0:
            candidates.extend(_fib_extension_levels(direction, entry, leg_len))

    min_first_dist = risk * 0.5
    if direction == "long":
        candidates = [c for c in candidates if c - entry >= min_first_dist]
        candidates.sort()
    else:
        candidates = [c for c in candidates if entry - c >= min_first_dist]
        candidates.sort(reverse=True)

    merged = []
    for c in candidates:
        if not merged or abs(c - merged[-1]) >= min_gap:
            merged.append(c)

    levels = merged[:max_levels]
    if not levels:
        levels = [entry + risk * 2] if direction == "long" else [entry - risk * 2]
    return levels


def analyze_candles(symbol, candles):
    if len(candles) < 40:
        return {"signal": "none", "confidence": 0}

    current_price = candles[-1]["close"]
    rsi = calc_rsi(candles)
    atr = calc_atr(candles)
    swings = find_swings(candles)

    breakout = classify_breakout(candles)
    if not breakout:
        return {"signal": "none", "confidence": 0}

    direction = breakout["direction"]
    level = breakout["level"]
    confidence = 50
    reasons = []

    if direction == "long":
        reasons.append(f"Пробой уровня сопротивления ${level:.4g}")
    else:
        reasons.append(f"Пробой уровня поддержки ${level:.4g}")

    if breakout["rvol"] is not None:
        confidence += max(0, min(20, int((breakout["rvol"] - 1) * 10)))
        reasons.append(f"Объём {breakout['rvol']:.1f}x от среднего")

    if breakout["body"] > 0.7:
        confidence += 10
        reasons.append("Сильное тело пробойной свечи")

    if direction == "long" and rsi < 70:
        confidence += 5
    elif direction == "short" and rsi > 30:
        confidence += 5

    # Стоп — чуть за пробитым уровнем: для лонга он теперь опора (поддержка),
    # для шорта — сопротивление сверху. Буфер на ATR, чтобы не выбивало шумом.
    buffer = atr * 0.3
    if direction == "long":
        sl = level - buffer
        if sl >= current_price:
            sl = current_price - atr * 1.5
    else:
        sl = level + buffer
        if sl <= current_price:
            sl = current_price + atr * 1.5

    tps = calc_take_profits(direction, current_price, sl, swings, atr=atr)
    if not tps:
        return {"signal": "none", "confidence": confidence}
    tp = tps[0]  # ближайший, самый надёжный — по нему считается RR и закрытие бумажной позиции

    rr = abs(tp - current_price) / abs(sl - current_price)
    return {
        "signal": direction,
        "confidence": min(int(confidence), 99),
        "symbol": symbol,
        "price": current_price,
        "sl": sl,
        "tp": tp,
        "tps": tps,
        "rr": rr,
        "rsi": rsi,
        "reasons": reasons,
        "has_sweep": False,
        "has_bos": False,
        "has_fvg": False,
        "atr": atr,
    }

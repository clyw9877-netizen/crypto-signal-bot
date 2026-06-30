from typing import List, Dict, Optional
import math

def calc_rsi(candles, period=14):
    if len(candles) < period + 1: return 50.0
    closes = [c["close"] for c in candles]
    gains, losses = [], []
    for i in range(1, len(closes)):
        diff = closes[i] - closes[i-1]
        gains.append(max(diff, 0))
        losses.append(max(-diff, 0))
    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period
    if avg_loss == 0: return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

def find_fvg(candles):
    fvgs = []
    for i in range(2, len(candles)):
        c1, c2, c3 = candles[i-2], candles[i-1], candles[i]
        if c3["low"] > c1["high"]:
            fvgs.append({"type":"bullish","top":c3["low"],"bottom":c1["high"],"idx":i,"size":c3["low"]-c1["high"]})
        if c3["high"] < c1["low"]:
            fvgs.append({"type":"bearish","top":c1["low"],"bottom":c3["high"],"idx":i,"size":c1["low"]-c3["high"]})
    return fvgs[-5:]

def find_bos(candles, lookback=20):
    bos_list = []
    recent = candles[-lookback:] if len(candles) >= lookback else candles
    for i in range(3, len(recent)):
        local_high = max(c["high"] for c in recent[max(0,i-5):i])
        if recent[i]["close"] > local_high and recent[i]["close"] > recent[i]["open"]:
            bos_list.append({"type":"bullish","level":local_high,"idx":i})
        local_low = min(c["low"] for c in recent[max(0,i-5):i])
        if recent[i]["close"] < local_low and recent[i]["close"] < recent[i]["open"]:
            bos_list.append({"type":"bearish","level":local_low,"idx":i})
    return bos_list[-3:]

def find_sweep(candles, lookback=30):
    recent = candles[-lookback:] if len(candles) >= lookback else candles
    for i in range(5, len(recent)):
        c = recent[i]
        body = abs(c["close"] - c["open"])
        lower_wick = min(c["open"], c["close"]) - c["low"]
        upper_wick = c["high"] - max(c["open"], c["close"])
        if lower_wick > body * 2 and c["close"] > c["open"]:
            prev_low = min(cc["low"] for cc in recent[max(0,i-10):i])
            if c["low"] < prev_low:
                return {"type":"bullish","swept_level":prev_low,"wick_low":c["low"],"idx":i}
        if upper_wick > body * 2 and c["close"] < c["open"]:
            prev_high = max(cc["high"] for cc in recent[max(0,i-10):i])
            if c["high"] > prev_high:
                return {"type":"bearish","swept_level":prev_high,"wick_high":c["high"],"idx":i}
    return None

def calc_atr(candles, period=14):
    if len(candles) < period: return candles[-1]["close"] * 0.01
    trs = []
    for i in range(1, len(candles)):
        high = candles[i]["high"]
        low = candles[i]["low"]
        prev_close = candles[i-1]["close"]
        tr = max(high-low, abs(high-prev_close), abs(low-prev_close))
        trs.append(tr)
    return sum(trs[-period:]) / period

def analyze_candles(symbol, candles):
    if len(candles) < 20: return {"signal":"none","confidence":0}
    confidence = 0
    reasons = []
    direction = None
    current_price = candles[-1]["close"]
    rsi = calc_rsi(candles)
    if rsi < 30:
        confidence += 15
        reasons.append("RSI oversold (" + str(round(rsi,1)) + ")")
        direction = "long"
    elif rsi > 70:
        confidence += 15
        reasons.append("RSI overbought (" + str(round(rsi,1)) + ")")
        direction = "short"
    fvgs = find_fvg(candles)
    bullish_fvg = [f for f in fvgs if f["type"] == "bullish"]
    if bullish_fvg:
        latest_fvg = bullish_fvg[-1]
        if latest_fvg["bottom"] <= current_price <= latest_fvg["top"]:
            confidence += 20
            reasons.append("Price in bullish FVG")
            direction = "long"
    bos_list = find_bos(candles)
    recent_bos = [b for b in bos_list if b["type"] == "bullish"]
    if recent_bos:
        confidence += 15
        reasons.append("Bullish BOS confirmed")
        direction = "long"
    sweep = find_sweep(candles)
    if sweep and sweep["type"] == "bullish":
        confidence += 20
        reasons.append("Liquidity sweep at $" + str(round(sweep["swept_level"],2)))
        direction = "long"
    ma20 = sum(c["close"] for c in candles[-20:]) / 20
    if current_price > ma20 and direction == "long":
        confidence += 10
        reasons.append("Price above MA20")
    if confidence < 50 or not direction:
        return {"signal":"none","confidence":confidence}
    atr = calc_atr(candles)
    if direction == "long":
        sl = current_price - atr * 2
        tp = current_price + atr * 4
    else:
        sl = current_price + atr * 2
        tp = current_price - atr * 4
    rr = abs(tp - current_price) / abs(sl - current_price)
    return {"signal":direction,"confidence":min(int(confidence),99),"symbol":symbol,"price":current_price,"sl":sl,"tp":tp,"rr":rr,"rsi":rsi,"reasons":reasons,"has_sweep":sweep is not None,"has_bos":len(recent_bos)>0,"has_fvg":len(bullish_fvg)>0,"atr":atr}

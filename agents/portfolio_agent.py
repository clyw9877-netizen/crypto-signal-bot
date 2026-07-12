import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from config import VIRTUAL_DEPOSIT, BINGX_FEE, CONFIDENCE_MATRIX

PORTFOLIO_FILE = "data/portfolio.json"

def load_portfolio() -> Dict:
    if os.path.exists(PORTFOLIO_FILE):
        with open(PORTFOLIO_FILE, "r") as f:
            return json.load(f)
    return {"deposit":VIRTUAL_DEPOSIT,"start_deposit":VIRTUAL_DEPOSIT,"trades":[],"open_positions":[],"total_trades":0,"wins":0,"losses":0,"total_pnl":0.0,"created_at":datetime.now().isoformat()}

def save_portfolio(portfolio: Dict):
    os.makedirs("data", exist_ok=True)
    with open(PORTFOLIO_FILE, "w") as f:
        json.dump(portfolio, f, indent=2, ensure_ascii=False)

def get_position_size(deposit: float, confidence: int):
    for (conf_min, conf_max, size_pct, leverage) in CONFIDENCE_MATRIX:
        if conf_min <= confidence < conf_max:
            return deposit * size_pct / 100, leverage
    return deposit * 0.2, 5

def calc_liquidation_price(entry: float, leverage: float, direction: str) -> float:
    if direction == "long":
        return entry * (1 - 1 / leverage)
    return entry * (1 + 1 / leverage)

def open_position(signal: Dict) -> Optional[Dict]:
    portfolio = load_portfolio()
    deposit = portfolio["deposit"]
    confidence = signal.get("confidence", 50)
    size, leverage = get_position_size(deposit, confidence)
    fee_open = size * leverage * BINGX_FEE
    liquidation = calc_liquidation_price(signal["price"], leverage, signal["signal"])
    position = {"liquidation":liquidation,"id":len(portfolio["trades"])+1,"symbol":signal["symbol"],"direction":signal["signal"],"entry_price":signal["price"],"sl":signal["sl"],"tp":signal["tp"],"size":size,"leverage":leverage,"fee_open":fee_open,"confidence":confidence,"reasons":signal.get("reasons",[]),"opened_at":datetime.now().isoformat(),"status":"open"}
    portfolio["open_positions"].append(position)
    save_portfolio(portfolio)
    return position

def check_positions(current_prices: Dict) -> List[Dict]:
    portfolio = load_portfolio()
    closed = []
    still_open = []
    for pos in portfolio["open_positions"]:
        symbol = pos["symbol"]
        current_price = current_prices.get(symbol)
        if not current_price:
            still_open.append(pos)
            continue
        direction = pos["direction"]
        sl = pos["sl"]
        tp = pos["tp"]
        hit_sl = current_price <= sl if direction == "long" else current_price >= sl
        hit_tp = current_price >= tp if direction == "long" else current_price <= tp
        if hit_sl or hit_tp:
            close_price = sl if hit_sl else tp
            pnl_pct = (close_price - pos["entry_price"]) / pos["entry_price"] if direction == "long" else (pos["entry_price"] - close_price) / pos["entry_price"]
            gross_pnl = pos["size"] * pos["leverage"] * pnl_pct
            fee_close = pos["size"] * pos["leverage"] * BINGX_FEE
            net_pnl = gross_pnl - pos["fee_open"] - fee_close
            pos.update({"close_price":close_price,"gross_pnl":gross_pnl,"fee_close":fee_close,"net_pnl":net_pnl,"closed_at":datetime.now().isoformat(),"result":"win" if net_pnl > 0 else "loss","hit_sl":hit_sl,"hit_tp":hit_tp,"status":"closed"})
            portfolio["deposit"] += net_pnl
            portfolio["total_trades"] += 1
            portfolio["total_pnl"] += net_pnl
            if net_pnl > 0: portfolio["wins"] += 1
            else: portfolio["losses"] += 1
            portfolio["trades"].append(pos)
            closed.append(pos)
        else:
            still_open.append(pos)
    portfolio["open_positions"] = still_open
    save_portfolio(portfolio)
    return closed

def format_position_opened(pos: Dict) -> str:
    dir_text = "ЛОНГ 🟢" if pos["direction"] == "long" else "ШОРТ 🔴"
    liq = pos.get("liquidation")
    liq_danger = False
    if liq:
        liq_danger = liq >= pos["sl"] if pos["direction"] == "long" else liq <= pos["sl"]
    liq_line = f"Ликвидация: ${liq:,.2f}" + (" ⚠️ БЛИЖЕ СТОПА!" if liq_danger else "") + "\n" if liq else ""
    return (f"<b>✅ Позиция открыта #{pos['id']}</b>\n"
            f"{pos['symbol']} {dir_text}\n"
            f"Вход: ${pos['entry_price']:,.2f}\n"
            f"SL: ${pos['sl']:,.2f}\n"
            f"TP: ${pos['tp']:,.2f}\n"
            f"{liq_line}"
            f"Плечо: x{pos['leverage']}\n"
            f"Размер позиции: ${pos['size']:,.2f}\n"
            f"Уверенность: {pos['confidence']}%")

def format_position_closed(pos: Dict, new_deposit: float) -> str:
    p = load_portfolio()
    wr = p["wins"]/p["total_trades"]*100 if p["total_trades"] > 0 else 0
    result = "✅ ПРИБЫЛЬ" if pos["result"]=="win" else "❌ УБЫТОК"
    trigger = "🎯 TP" if pos.get("hit_tp") else "🛑 SL"
    return (f"<b>{result} — Сделка #{pos['id']} закрыта</b>\n"
            f"{pos['symbol']}\n"
            f"Сработал: {trigger} по цене ${pos.get('close_price',0):,.2f}\n"
            f"Прибыль/убыток: ${pos.get('net_pnl',0):,.2f}\n"
            f"Депозит сейчас: ${new_deposit:,.2f}\n"
            f"Винрейт: {round(wr)}%")

def get_portfolio_stats() -> str:
    p = load_portfolio()
    wr = p["wins"]/p["total_trades"]*100 if p["total_trades"] > 0 else 0
    growth = (p["deposit"]-p["start_deposit"])/p["start_deposit"]*100
    return (f"<b>📊 Статистика портфеля</b>\n"
            f"Старт: ${p['start_deposit']:,.2f}\n"
            f"Сейчас: ${p['deposit']:,.2f}\n"
            f"Рост: {growth:+.1f}%\n"
            f"Побед/Поражение: {p['wins']}/{p['losses']}\n"
            f"Винрейт: {round(wr)}%\n"
            f"Общий P&L: ${p['total_pnl']:,.2f}\n"
            f"Открытых позиций: {len(p['open_positions'])}")

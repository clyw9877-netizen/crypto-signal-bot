import json
import os
import math
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
    if any(p["symbol"] == signal.get("symbol") for p in portfolio["open_positions"]):
        return None
    deposit = portfolio["deposit"]
    used_margin = sum(p["size"] for p in portfolio["open_positions"])
    free_margin = deposit - used_margin
    if free_margin <= 10:
        return None
    confidence = signal.get("confidence", 50)
    size, leverage = get_position_size(free_margin, confidence)
    fee_open = size * leverage * BINGX_FEE
    liquidation = calc_liquidation_price(signal["price"], leverage, signal["signal"])
    position = {"liquidation":liquidation,"id":len(portfolio["trades"])+1,"symbol":signal["symbol"],"direction":signal["signal"],"entry_price":signal["price"],"sl":signal["sl"],"tp":signal["tp"],"size":size,"leverage":leverage,"fee_open":fee_open,"confidence":confidence,"reasons":signal.get("reasons",[]),"opened_at":datetime.now().isoformat(),"status":"open","tps":signal.get("tps",[signal["tp"]]),"tp_index":0,"breakeven":False}
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
        tps = pos.get("tps", [tp])
        tp_index = pos.get("tp_index", 0)
        hit_sl = current_price <= sl if direction == "long" else current_price >= sl
        hit_tp = current_price >= tp if direction == "long" else current_price <= tp
        if hit_sl:
            close_price = sl
            pnl_pct = (close_price - pos["entry_price"]) / pos["entry_price"] if direction == "long" else (pos["entry_price"] - close_price) / pos["entry_price"]
            gross_pnl = pos["size"] * pos["leverage"] * pnl_pct
            fee_close = pos["size"] * pos["leverage"] * BINGX_FEE
            net_pnl = gross_pnl - pos["fee_open"] - fee_close
            pos.update({"close_price":close_price,"gross_pnl":gross_pnl,"fee_close":fee_close,"net_pnl":net_pnl,"closed_at":datetime.now().isoformat(),"result":"win" if net_pnl > 0 else "loss","hit_sl":True,"hit_tp":False,"status":"closed"})
            portfolio["deposit"] += net_pnl
            portfolio["total_trades"] += 1
            portfolio["total_pnl"] += net_pnl
            if net_pnl > 0: portfolio["wins"] += 1
            else: portfolio["losses"] += 1
            portfolio["trades"].append(pos)
            closed.append(pos)
        elif hit_tp:
            next_tp_index = tp_index + 1
            is_last_tp = next_tp_index >= len(tps)
            if is_last_tp:
                close_price = tp
                pnl_pct = (close_price - pos["entry_price"]) / pos["entry_price"] if direction == "long" else (pos["entry_price"] - close_price) / pos["entry_price"]
                gross_pnl = pos["size"] * pos["leverage"] * pnl_pct
                fee_close = pos["size"] * pos["leverage"] * BINGX_FEE
                net_pnl = gross_pnl - pos["fee_open"] - fee_close
                pos.update({"close_price":close_price,"gross_pnl":gross_pnl,"fee_close":fee_close,"net_pnl":net_pnl,"closed_at":datetime.now().isoformat(),"result":"win","hit_sl":False,"hit_tp":True,"status":"closed"})
                portfolio["deposit"] += net_pnl
                portfolio["total_trades"] += 1
                portfolio["total_pnl"] += net_pnl
                portfolio["wins"] += 1
                portfolio["trades"].append(pos)
                closed.append(pos)
            else:
                pos["sl"] = pos["entry_price"]
                pos["tp"] = tps[next_tp_index]
                pos["tp_index"] = next_tp_index
                pos["breakeven"] = True
                still_open.append(pos)
                try:
                    from agents.telegram_agent import send_message as _send
                    _send(f"\U0001F3AF <b>TP{tp_index+1} достигнут!</b> #{pos['id']} {pos['symbol']}\nЦена: {current_price:.4f}\n✅ Стоп → безубыток: {pos['entry_price']:.4f}\nСлед. цель: <b>TP{next_tp_index+1}</b> → {tps[next_tp_index]:.4f}")
                except Exception:
                    pass
        else:
            still_open.append(pos)
    portfolio["open_positions"] = still_open
    save_portfolio(portfolio)
    return closed

def _format_price(value: float) -> str:
    if value <= 0:
        return "0"
    if value >= 1:
        return f"{value:,.2f}"
    magnitude = math.floor(math.log10(abs(value)))
    decimals = max(4, -magnitude + 3)
    return f"{value:.{decimals}f}"

def format_position_opened(pos: Dict) -> str:
    dir_text = "ЛОНГ 🟢" if pos["direction"] == "long" else "ШОРТ 🔴"
    liq = pos.get("liquidation")
    liq_danger = False
    if liq:
        liq_danger = liq >= pos["sl"] if pos["direction"] == "long" else liq <= pos["sl"]
    liq_line = f"Ликвидация: ${_format_price(liq)}" + (" ⚠️ БЛИЖЕ СТОПА!" if liq_danger else "") + "\n" if liq else ""
    tps_list = pos.get("tps", [pos["tp"]])
    tp_lines = "\n".join(f"  TP{i+1}: ${_format_price(t)}" for i, t in enumerate(tps_list))
    return (f"<b>✅ Позиция открыта #{pos['id']}</b>\n"
            f"{pos['symbol']} {dir_text}\n"
            f"Вход: ${_format_price(pos['entry_price'])}\n"
            f"SL: ${_format_price(pos['sl'])}\n"
            f"Тейки:\n{tp_lines}\n"
            f"{liq_line}"
            f"Плечо: x{pos['leverage']}\n"
            f"Размер позиции: ${pos['size']:,.2f}\n"
            f"Уверенность: {pos['confidence']}%\n"
            f"⚡ Плечо: x{pos['leverage']}")

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
            f"Винрейт: {round(wr)}%\n"
            f"⚡ Плечо: x{pos.get('leverage', '?')}")

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

def get_trade_journal(min_trades=3):
    p = load_portfolio()
    closed = [t for t in p.get("trades", []) if t.get("status") == "closed"]
    if len(closed) < min_trades:
        return None

    by_symbol = {}
    for t in closed:
        s = t["symbol"]
        by_symbol.setdefault(s, {"wins": 0, "losses": 0, "pnl": 0.0})
        by_symbol[s]["pnl"] += t["net_pnl"]
        if t["result"] == "win":
            by_symbol[s]["wins"] += 1
        else:
            by_symbol[s]["losses"] += 1
    ranked = sorted(by_symbol.items(), key=lambda kv: kv[1]["pnl"], reverse=True)

    by_conf = {}
    for t in closed:
        tier = (t["confidence"] // 10) * 10
        by_conf.setdefault(tier, {"wins": 0, "total": 0})
        by_conf[tier]["total"] += 1
        if t["result"] == "win":
            by_conf[tier]["wins"] += 1

    best_trade = max(closed, key=lambda t: t["net_pnl"])
    worst_trade = min(closed, key=lambda t: t["net_pnl"])
    total_fees = sum(t.get("fee_open", 0) + t.get("fee_close", 0) for t in closed)

    lines = ["<b>📓 Журнал сделок</b>", ""]
    lines.append("По монетам (P&L):")
    for symbol, stats in ranked[:5]:
        total = stats["wins"] + stats["losses"]
        wr = stats["wins"] / total * 100 if total > 0 else 0
        lines.append(f"  {symbol}: ${stats['pnl']:+,.2f} (винрейт {round(wr)}%, {total} сделок)")
    lines.append("")
    lines.append("По уверенности сигнала:")
    for tier in sorted(by_conf.keys()):
        stats = by_conf[tier]
        wr = stats["wins"] / stats["total"] * 100 if stats["total"] > 0 else 0
        lines.append(f"  {tier}-{tier+9}%: винрейт {round(wr)}% ({stats['total']} сделок)")
    lines.append("")
    lines.append(f"Лучшая сделка: {best_trade['symbol']} ${best_trade['net_pnl']:+,.2f}")
    lines.append(f"Худшая сделка: {worst_trade['symbol']} ${worst_trade['net_pnl']:+,.2f}")
    lines.append(f"Комиссии всего: ${total_fees:,.2f}")
    return "\n".join(lines)

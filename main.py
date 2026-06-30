import time, schedule, logging, os, sys
from config import COINS, SCAN_INTERVAL
from agents.data_agent import get_candles, get_all_prices
from agents.smc_agent import analyze_candles
from agents.chart_agent import draw_signal_chart
from agents.news_agent import get_crypto_news, get_forex_factory_events, check_high_impact_now, format_morning_digest, format_evening_digest, format_signal_news
from agents.portfolio_agent import load_portfolio, open_position, check_positions, format_position_opened, format_position_closed, get_portfolio_stats
from agents.telegram_agent import send_message, send_photo, test_connection, send_signal

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)
sent_signals = set()

# Railway runs in UTC.
# Pacific Time (PDT, summer) = UTC-7  -> 08:00 PDT = 15:00 UTC, 22:00 PDT = 05:00 UTC (next day)
# Moscow Time (MSK) = UTC+3          -> 08:00 MSK = 05:00 UTC, 22:00 MSK = 19:00 UTC
SCHEDULE_UTC = {
    "pacific_morning": "15:00",
    "pacific_evening": "05:00",
    "moscow_morning":  "05:00",
    "moscow_evening":  "19:00",
}

def safe(fn, name, default=None):
    try:
        return fn()
    except Exception as e:
        log.error(f"{name} failed: {e}")
        return default

def scan_market():
    log.info(f"=== SCAN START: {len(COINS)} coins ===")

    news_ok = safe(check_high_impact_now, "check_high_impact_now", False)
    if news_ok:
        send_message("⚠️ <b>Красная новость по крипте!</b> Пропускаю сканирование.")
        return

    prices = safe(lambda: get_all_prices(COINS), "get_all_prices", {})
    log.info(f"Got {len(prices)} prices")

    closed = safe(lambda: check_positions(prices), "check_positions", [])
    for pos in closed:
        p = load_portfolio()
        send_message(format_position_closed(pos, p["deposit"]))
    if closed:
        log.info(f"Closed {len(closed)} positions")

    signals = []
    for idx, symbol in enumerate(COINS):
        try:
            candles = get_candles(symbol, "1h", 100)
            if len(candles) < 30:
                continue
            signal = analyze_candles(symbol, candles)
            if signal["signal"] == "none" or signal["confidence"] < 55:
                continue
            key = f"{symbol}_{signal['signal']}_{int(signal['price']/100)}"
            if key not in sent_signals:
                signals.append((symbol, signal, candles, key))
                log.info(f"SIGNAL FOUND: {symbol} {signal['signal']} conf={signal['confidence']}")
        except Exception as e:
            log.error(f"{symbol}: {e}")

    log.info(f"=== SCAN DONE. {len(signals)} signals found ===")

    for symbol, signal, candles, key in signals[:3]:
        try:
            port = load_portfolio()
            if len(port["open_positions"]) < 3:
                pos = open_position(signal)
                chart = draw_signal_chart(symbol, candles, signal)
                news = safe(get_crypto_news, "get_crypto_news", [])
                related = [n for n in news if symbol.split("-")[0] in n.get("currencies",[])]
                send_signal(signal, chart, format_signal_news(signal, related))
                send_message(format_position_opened(pos))
                sent_signals.add(key)
                time.sleep(2)
        except Exception as e:
            log.error(f"Signal send {symbol}: {e}")

def send_digest(kind: str):
    log.info(f"=== DIGEST [{kind}] START ===")
    prices = safe(lambda: get_all_prices(["BTC-USDT", "ETH-USDT", "SOL-USDT"]), "prices", {})
    events = safe(lambda: get_forex_factory_events(crypto_only=True), "events", [])
    news = safe(get_crypto_news, "news", [])
    if "morning" in kind:
        text = format_morning_digest(prices, events, news)
    else:
        text = format_evening_digest(prices, events, news)
    label = "🇺🇸 твоё время" if "pacific" in kind else "🇷🇺 Москва"
    send_message(f"{label}\n\n{text}")
    send_message(get_portfolio_stats())
    log.info(f"=== DIGEST [{kind}] DONE ===")

def main():
    log.info("Starting Crypto Signal Bot...")
    os.makedirs("data", exist_ok=True)
    if not test_connection():
        log.error("Cannot connect to Telegram!")
        return

    port = load_portfolio()
    send_message(f"🤖 <b>Бот перезапущен!</b>\nДепозит: ${port['deposit']:.2f}")

    schedule.every(SCAN_INTERVAL).seconds.do(scan_market)
    schedule.every().day.at(SCHEDULE_UTC["pacific_morning"]).do(lambda: send_digest("pacific_morning"))
    schedule.every().day.at(SCHEDULE_UTC["pacific_evening"]).do(lambda: send_digest("pacific_evening"))
    schedule.every().day.at(SCHEDULE_UTC["moscow_morning"]).do(lambda: send_digest("moscow_morning"))
    schedule.every().day.at(SCHEDULE_UTC["moscow_evening"]).do(lambda: send_digest("moscow_evening"))

    scan_market()
    log.info("Entering main loop...")
    while True:
        schedule.run_pending()
        time.sleep(10)

if __name__ == "__main__":
    main()

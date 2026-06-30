import time, schedule, logging, os
from config import COINS, SCAN_INTERVAL, MORNING_DIGEST_TIME, VIRTUAL_DEPOSIT
from agents.data_agent import get_candles, get_all_prices
from agents.smc_agent import analyze_candles
from agents.chart_agent import draw_signal_chart
from agents.news_agent import get_crypto_news, get_forex_factory_events, check_high_impact_now, format_morning_digest, format_signal_news
from agents.portfolio_agent import load_portfolio, open_position, check_positions, format_position_opened, format_position_closed, get_portfolio_stats
from agents.telegram_agent import send_message, send_photo, test_connection, send_signal

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s", handlers=[logging.StreamHandler()])
log = logging.getLogger(__name__)
sent_signals = set()

def scan_market():
    log.info(f"Scanning {len(COINS)} coins...")
    if check_high_impact_now():
        send_message("Red news! Skipping scan.")
        return
    prices = get_all_prices(COINS)
    for pos in check_positions(prices):
        p = load_portfolio()
        send_message(format_position_closed(pos, p["deposit"]))
    signals = []
    for symbol in COINS:
        try:
            candles = get_candles(symbol, "1h", 100)
            if len(candles) < 30: continue
            signal = analyze_candles(symbol, candles)
            if signal["signal"] == "none" or signal["confidence"] < 55: continue
            port = load_portfolio()
            if len(port["open_positions"]) < 3:
                pos = open_position(signal)
                chart = draw_signal_chart(symbol, candles, signal)
                news = get_crypto_news()
                related = [n for n in news if symbol.split("-")[0] in n.get("currencies",[])]
                send_signal(signal, chart, format_signal_news(signal, related))
                send_message(format_position_opened(pos))
                time.sleep(2)
        except Exception as e: log.error(f"{symbol}: {e}")

def morning_digest():
    prices = get_all_prices(["BTC-USDT", "ETH-USDT", "SOL-USDT"])
    send_message(format_morning_digest(prices, get_forex_factory_events(), get_crypto_news()))
    send_message(get_portfolio_stats())

def main():
    log.info("Starting Crypto Signal Bot...")
    os.makedirs("data", exist_ok=True)
    if not test_connection():
        log.error("Cannot connect to Telegram!")
        return
    port = load_portfolio()
    send_message(f"Bot started! Deposit: ${port['deposit']:.2f}")
    schedule.every(SCAN_INTERVAL).seconds.do(scan_market)
    schedule.every().day.at(MORNING_DIGEST_TIME).do(morning_digest)
    scan_market()
    while True:
        schedule.run_pending()
        time.sleep(10)

if __name__ == "__main__":
    main()

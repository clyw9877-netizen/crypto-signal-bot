import requests
import json
import os
from config import TELEGRAM_TOKEN, TELEGRAM_CHANNEL


BASE_URL = "https://api.telegram.org/bot" + TELEGRAM_TOKEN
OFFSET_FILE = "data/telegram_offset.json"


def send_message(text, chat_id=None, parse_mode="HTML"):
    try:
        chat = chat_id or TELEGRAM_CHANNEL
        r = requests.post(BASE_URL + "/sendMessage", json={"chat_id":chat,"text":text,"parse_mode":parse_mode,"disable_web_page_preview":True}, timeout=15)
        ok = r.json().get("ok", False)
        if not ok:
            print("Telegram sendMessage failed:", r.json())
        return ok
    except Exception as e:
        print("Telegram error:", e)
        return False


def send_photo(image_bytes, caption="", chat_id=None):
    try:
        chat = chat_id or TELEGRAM_CHANNEL
        r = requests.post(BASE_URL + "/sendPhoto", data={"chat_id":chat,"caption":caption,"parse_mode":"HTML"}, files={"photo":("chart.png",image_bytes,"image/png")}, timeout=30)
        ok = r.json().get("ok", False)
        if not ok:
            print("Telegram sendPhoto failed:", r.json())
        return ok
    except Exception as e:
        print("Telegram error:", e)
        return False


def send_signal(signal, chart_bytes, news_text=""):
    s = signal
    direction = s.get("signal", "long")
    dir_text = "ЛОНГ 🟢" if direction == "long" else "ШОРТ 🔴"
    confidence = s.get("confidence", 0)
    entry = s.get("price", 0)
    sl = s.get("sl", 0)
    tp = s.get("tp", 0)
    rr = s.get("rr", 0)
    rsi = s.get("rsi", 50)
    reasons = s.get("reasons", [])


    reasons_ru = []
    for r in reasons:
        rr_ru = (r.replace("RSI oversold", "RSI перепродан")
                  .replace("RSI overbought", "RSI перекуплен")
                  .replace("Price in bullish FVG", "Цена в бычьей FVG зоне")
                  .replace("Bullish BOS confirmed", "Подтверждён слом структуры вверх (BOS)")
                  .replace("Liquidity sweep at", "Снятие ликвидности на")
                  .replace("Price above MA20", "Цена выше MA20"))
        reasons_ru.append(rr_ru)


    confidence_emoji = "🔥" if confidence >= 85 else "⚡" if confidence >= 70 else "📊"


    caption = f"<b>{s.get('symbol','')} — {dir_text}</b> {confidence_emoji} {confidence}%\n\n"
    caption += f"Вход: <b>${entry:,.2f}</b>\n"
    caption += f"SL: <b>${sl:,.2f}</b>\n"
    caption += f"TP: <b>${tp:,.2f}</b>\n"
    caption += f"📊 RR: <b>1:{rr:.1f}</b>\n"
    caption += f"📈 RSI: <b>{rsi:.0f}</b>\n\n"
    if reasons_ru:
        caption += "<b>✅ Паттерны:</b>\n"
        for r in reasons_ru[:5]:
            caption += f"• {r}\n"
    caption += news_text
    caption += "\n⚠️ <i>Это не финансовый совет. Своя торговля — свой риск.</i>"


    return send_photo(chart_bytes, caption)


def test_connection():
    try:
        r = requests.get(BASE_URL + "/getMe", timeout=10)
        data = r.json()
        if data.get("ok"):
            print("Telegram connected:", data["result"]["username"])
            return True
        return False
    except Exception as e:
        print("Connection error:", e)
        return False


def _load_offset():
    try:
        with open(OFFSET_FILE) as f:
            return json.load(f).get("offset")
    except Exception:
        return None


def _save_offset(offset):
    try:
        with open(OFFSET_FILE, "w") as f:
            json.dump({"offset": offset}, f)
    except Exception:
        pass


def get_new_messages():
    try:
        offset = _load_offset()
        params = {"timeout": 0}
        if offset is not None:
            params["offset"] = offset
        r = requests.get(BASE_URL + "/getUpdates", params=params, timeout=10)
        data = r.json()
        if not data.get("ok"):
            return []
        updates = data.get("result", [])
    except Exception as e:
        print("getUpdates error:", e)
        return []

    messages = []
    last_id = offset
    for u in updates:
        last_id = u["update_id"] + 1
        msg = u.get("message") or u.get("channel_post")
        if not msg:
            continue
        text = msg.get("text")
        chat_id = msg.get("chat", {}).get("id")
        if text and chat_id:
            messages.append((chat_id, text))
    if last_id is not None:
        _save_offset(last_id)
    return messages

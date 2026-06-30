import requests
from config import TELEGRAM_TOKEN, TELEGRAM_CHANNEL

BASE_URL = "https://api.telegram.org/bot" + TELEGRAM_TOKEN

def send_message(text, chat_id=None, parse_mode="HTML"):
    try:
        chat = chat_id or TELEGRAM_CHANNEL
        r = requests.post(BASE_URL + "/sendMessage", json={"chat_id":chat,"text":text,"parse_mode":parse_mode,"disable_web_page_preview":True}, timeout=15)
        return r.json().get("ok", False)
    except Exception as e:
        print("Telegram error:", e)
        return False

def send_photo(image_bytes, caption="", chat_id=None):
    try:
        chat = chat_id or TELEGRAM_CHANNEL
        r = requests.post(BASE_URL + "/sendPhoto", data={"chat_id":chat,"caption":caption,"parse_mode":"HTML"}, files={"photo":("chart.png",image_bytes,"image/png")}, timeout=30)
        return r.json().get("ok", False)
    except Exception as e:
        print("Photo error:", e)
        return False

def send_signal(signal, chart_bytes, news_text=""):
    s = signal
    caption = s.get("symbol","") + " " + ("LONG" if s.get("signal")=="long" else "SHORT") + "\nEntry: $" + str(round(s.get("price",0),2)) + "\nSL: $" + str(round(s.get("sl",0),2)) + "\nTP: $" + str(round(s.get("tp",0),2)) + "\nConfidence: " + str(s.get("confidence",0)) + "%"
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

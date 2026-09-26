"""
ИИ-слой поверх пробойной стратегии.

Перед входом: проверяет сигнал на здравый смысл, может слегка
скорректировать SL/TP/уверенность или отклонить вход целиком.
После закрытия сделки: разбирает, что пошло не так (или что сработало),
и запоминает урок — следующая проверка входа по этой же монете видит
последние уроки и учитывает их.

Работает только если задан ANTHROPIC_API_KEY (переменная окружения).
Без ключа или при любой ошибке вызова — тихо пропускается (fail-open):
бот не должен останавливаться из-за недоступности ИИ, стратегия и без
него рабочая — это дополнительная проверка, а не обязательное звено.
"""

import json
import os
import re
import time

import requests

API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5-20251001"
TIMEOUT = 20
LESSONS_FILE = "data/lessons.json"
MAX_LESSONS_IN_PROMPT = 6


def _api_key():
    return os.environ.get("ANTHROPIC_API_KEY", "").strip()


def _call_claude(system_prompt, user_prompt, max_tokens=400):
    key = _api_key()
    if not key:
        return None
    try:
        r = requests.post(
            API_URL,
            headers={
                "x-api-key": key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": MODEL,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            },
            timeout=TIMEOUT,
        )
        if r.status_code != 200:
            print("Claude API error:", r.status_code, r.text[:300])
            return None
        data = r.json()
        blocks = data.get("content", [])
        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        return text.strip()
    except Exception as e:
        print("Claude API call failed:", e)
        return None


def _extract_json(text):
    """Достаёт JSON из ответа, даже если модель обернула его в ```json ... ```."""
    if not text:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try:
        return json.loads(cleaned)
    except Exception:
        m = re.search(r"\{.*\}", cleaned, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                return None
        return None


def _load_lessons():
    try:
        with open(LESSONS_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save_lessons(lessons):
    try:
        os.makedirs(os.path.dirname(LESSONS_FILE) or ".", exist_ok=True)
        with open(LESSONS_FILE, "w", encoding="utf-8") as f:
            json.dump(lessons, f, ensure_ascii=False)
    except Exception:
        pass


def get_recent_lessons(limit=MAX_LESSONS_IN_PROMPT):
    lessons = _load_lessons()
    return lessons[-limit:]


def save_lesson(symbol, direction, result, lesson_text):
    if not lesson_text:
        return
    lessons = _load_lessons()
    lessons.append({
        "symbol": symbol,
        "direction": direction,
        "result": result,
        "lesson": lesson_text,
        "ts": time.time(),
    })
    lessons = lessons[-200:]  # не даём файлу расти бесконечно
    _save_lessons(lessons)


def review_signal(signal):
    """Проверка перед входом. Возвращает (signal, approve, reasoning).
    Без ключа или при ошибке — (signal без изменений, True, None): открывать можно."""
    if not _api_key():
        return signal, True, None

    lessons = get_recent_lessons()
    lessons_text = "\n".join(f"- {l['lesson']}" for l in lessons) if lessons else "Уроков по этой монете ещё нет."

    system = (
        "Ты — риск-аналитик у трейдингового бота, торгующего пробои уровней "
        "(канал Дончиана, подтверждение объёмом и телом свечи). Проверяешь "
        "конкретный уже найденный сигнал на здравый смысл и, если видишь явную "
        "проблему, слегка корректируешь стоп/тейк. Ты НЕ меняешь направление "
        "сделки и не придумываешь новую стратегию — только да/нет и небольшая "
        "поправка уровней. Отвечай СТРОГО JSON без текста вокруг: "
        '{"approve": true/false, "confidence_delta": -20..20, '
        '"sl_adjust_pct": -2.0..2.0, "tp_adjust_pct": -5.0..5.0, "reasoning": "коротко, по-русски"}'
    )
    user = (
        f"Монета: {signal.get('symbol')}\n"
        f"Направление: {signal.get('signal')}\n"
        f"Вход: {signal.get('price')}\n"
        f"SL: {signal.get('sl')}\n"
        f"TP (ближайший): {signal.get('tp')}\n"
        f"Все TP-уровни: {signal.get('tps')}\n"
        f"RSI: {signal.get('rsi', 50):.1f}\n"
        f"Уверенность стратегии: {signal.get('confidence')}%\n"
        f"Причины входа: {signal.get('reasons')}\n\n"
        f"Прошлые уроки по этой монете:\n{lessons_text}\n\n"
        "Оцени: логично ли входить именно так? Если по прошлым урокам видна "
        "повторяющаяся ошибка — учти её при решении. Ответь JSON."
    )

    raw = _call_claude(system, user)
    parsed = _extract_json(raw)
    if not parsed:
        return signal, True, None

    approve = bool(parsed.get("approve", True))
    reasoning = parsed.get("reasoning") or None

    if approve:
        try:
            conf_delta = float(parsed.get("confidence_delta", 0) or 0)
            sl_pct = float(parsed.get("sl_adjust_pct", 0) or 0)
            tp_pct = float(parsed.get("tp_adjust_pct", 0) or 0)
            signal["confidence"] = max(0, min(99, int(signal["confidence"] + conf_delta)))
            direction_sign = 1 if signal["signal"] == "long" else -1
            if sl_pct:
                signal["sl"] = signal["sl"] * (1 - direction_sign * sl_pct / 100)
            if tp_pct and signal.get("tps"):
                signal["tps"] = [t * (1 + direction_sign * tp_pct / 100) for t in signal["tps"]]
                signal["tp"] = signal["tps"][0]
        except Exception as e:
            print("AI adjustment apply error:", e)

    return signal, approve, reasoning


def analyze_trade_outcome(position):
    """Пост-анализ закрытой сделки. Возвращает текст урока (1-2 предложения)
    или None, если ИИ недоступен."""
    if not _api_key():
        return None

    system = (
        "Ты — трейдинг-коуч, разбирающий уже закрытую сделку бота, торгующего "
        "пробои уровней. Дай ОДИН короткий, конкретный вывод на будущее "
        "(1-2 предложения, по-русски) — без общих слов вроде 'рынок "
        "непредсказуем'. Если видна причина (пробой на слабом объёме, "
        "уровень был слишком близко ко входу, разворот сразу после входа) — "
        "назови её прямо."
    )
    user = (
        f"Монета: {position.get('symbol')}\n"
        f"Направление: {position.get('direction')}\n"
        f"Вход: {position.get('entry_price')}\n"
        f"SL: {position.get('sl')}, TP: {position.get('tp')}\n"
        f"Закрылась по: {position.get('close_price')} "
        f"({'сработал TP' if position.get('hit_tp') else 'сработал SL'})\n"
        f"Результат: {position.get('result')}, P&L: ${position.get('net_pnl', 0):.2f}\n"
        f"Уверенность при входе: {position.get('confidence')}%\n"
        f"Причины входа: {position.get('reasons')}\n\n"
        "Сформулируй урок на будущее одним-двумя предложениями."
    )
    lesson = _call_claude(system, user, max_tokens=200)
    return lesson.strip() if lesson else None

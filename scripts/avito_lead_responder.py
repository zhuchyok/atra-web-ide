"""Avito Auto-Responder — монитор лидов + автоответчик.

Каждые 10 минут проверяет непрочитанные чаты клиентов.
Новые лиды → алерт через ntfy (мгновенно на телефон Ивана).
Дальнейшая разработка: авто-генерация ответа через qwen38 + отправка через API.

Использование: launchd каждые 10 минут или вручную.
"""
import json
import os
import sys
import time
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
STATE_PATH = REPO / "logs" / "avito_lead_state.json"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "atra_victoria_curator")
ACCOUNT_ID = "7561711"


def get_token() -> str:
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": os.environ.get("AVITO_CLIENT_ID", ""),
        "client_secret": os.environ.get("AVITO_CLIENT_SECRET", "")
    }).encode()
    req = urllib.request.Request("https://api.avito.ru/token", data=data)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())["access_token"]


def notify_ntfy(message: str, title: str = "🔥 Avito Лид") -> None:
    topic = os.environ.get("NTFY_TOPIC", "atra_victoria_curator")
    data = json.dumps({"topic": topic, "message": message[:3500]}).encode()
    req = urllib.request.Request(
        f"https://ntfy.sh/{topic}", data=data,
        headers={"Content-Type": "application/json", "Title": title},
    )
    urllib.request.urlopen(req, timeout=15)


def notify_telegram(message: str) -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat_id = os.environ.get("TELEGRAM_USER_ID", "")
    if not token or not chat_id:
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": message[:3500]}).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage", data=data, timeout=10
        )
    except Exception:
        pass  # Telegram недоступен — не блокируем




def send_reply(token: str, chat_id: str, text: str) -> bool:
    """Отправить ответ в чат через Avito Messenger API."""
    hdrs = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    body = json.dumps({"message": {"text": text}, "type": "text"}).encode()
    url = f"https://api.avito.ru/messenger/v1/accounts/{ACCOUNT_ID}/chats/{chat_id}/messages"
    req = urllib.request.Request(url, data=body, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status == 200
    except Exception as e:
        print(f"  ❌ Отправка: {e}")
        return False


def main() -> int:
    # свежий токен
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": os.environ.get("AVITO_CLIENT_ID", ""),
        "client_secret": os.environ.get("AVITO_CLIENT_SECRET", "")
    }).encode()
    req = urllib.request.Request("https://api.avito.ru/token", data=data)
    with urllib.request.urlopen(req, timeout=15) as r:
        token = json.loads(r.read())["access_token"]

    hdrs = {"Authorization": f"Bearer {token}"}

    # непрочитанные чаты
    url = f"https://api.avito.ru/messenger/v2/accounts/{ACCOUNT_ID}/chats?unread_only=true&limit=50"
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=15) as r:
        chats = json.loads(r.read()).get("chats", [])

    if not chats:
        print("Непрочитанных чатов нет.")
        return 0

    print(f"Непрочитанных чатов: {len(chats)}")
    alerts_sent = 0

    for chat in chats[:10]:  # обрабатываем первые 10 за запуск
        chat_id = chat["id"]
        ctx = chat.get("context", {})
        val = ctx.get("value", {}) if isinstance(ctx, dict) else {}
        item_title = val.get("title", "?")[:50] if isinstance(val, dict) else "?"

        # получить сообщения
        msg_url = f"https://api.avito.ru/messenger/v3/accounts/{ACCOUNT_ID}/chats/{chat_id}/messages/"
        req_msg = urllib.request.Request(msg_url, headers=hdrs)
        try:
            with urllib.request.urlopen(req_msg, timeout=15) as r:
                msgs = json.loads(r.read()).get("messages", [])
        except Exception as e:
            print(f"ERR messages {chat_id[:15]}: {e}")
            continue

        # последнее сообщение от клиента
        customer_text = ""
        for m in reversed(msgs):
            author = m.get("author", {})
            content = m.get("content", {})
            if author.get("type") == "customer" and isinstance(content, dict):
                customer_text = str(content.get("text", ""))[:150]
                break

        alert = f"🔥 Avito: новый лид!\nОбъявление: {item_title}\nСообщение: {customer_text or '(без текста)'}"

        # ntfy (мгновенно на телефон)
        try:
            notify_ntfy(alert)
            alerts_sent += 1
            print(f"✅ ntfy: {item_title[:40]}")
        except Exception as e:
            print(f"ntfy ERR: {e}")

        # автоответ клиенту
        if customer_text:
            reply = f"Здравствуйте! Спасибо за обращение по «{item_title[:40]}». Мы на рынке с 2009 года, гарантия 5 лет. Напишите размеры — посчитаем точную цену. Или позвоните: +7 (8352) 38-40-20."
            if send_reply(token, chat_id, reply):
                print(f"  ✅ Автоответ отправлен")

        # Telegram (если доступен)
        try:
            notify_telegram(alert)
        except Exception:
            pass

        # пометить чат как прочитанный через API (чтобы не дублировал)
        read_url = f"https://api.avito.ru/messenger/v2/accounts/{ACCOUNT_ID}/chats/{chat_id}/read"
        req_read = urllib.request.Request(read_url, headers=hdrs, method="POST")
        try:
            urllib.request.urlopen(req_read, timeout=10)
        except Exception:
            pass

        time.sleep(1)  # не спамить API

    print(f"Итого алертов отправлено: {alerts_sent}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

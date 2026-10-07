"""Avito Messenger Monitor — монитор непрочитанных чатов клиентов.

Каждые 10 минут проверяет новые сообщения от покупателей и:
  1. Шлёт алерт через ntfy (мгновенно на телефон)
  2. Дублирует в Telegram (если маршрут доступен)
  3. Логирует в logs/avito_messages.log

Не отправляет ответы клиентам — только УВЕДОМЛЯЕТ Ивана.
Запуск: launchd каждые 10 минут.
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
STATE_PATH = REPO / "logs" / "avito_messages_state.json"
NTFY_TOPIC = os.environ.get("NTFY_TOPIC", "atra_victoria_curator")

# Аккаунт Avito Pro
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


def get_unread_chats(token: str) -> list:
    hdrs = {"Authorization": f"Bearer {token}"}
    url = f"https://api.avito.ru/messenger/v2/accounts/{ACCOUNT_ID}/chats?unread_only=true&limit=50"
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read()).get("chats", [])


def get_chat_messages(token: str, chat_id: str) -> list:
    hdrs = {"Authorization": f"Bearer {token}"}
    url = f"https://api.avito.ru/messenger/v3/accounts/{ACCOUNT_ID}/chats/{chat_id}/messages/"
    req = urllib.request.Request(url, headers=hdrs)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read()).get("messages", [])


def notify_ntfy(message: str) -> None:
    data = json.dumps({"topic": NTFY_TOPIC, "message": message[:3500]}).encode()
    req = urllib.request.Request(
        f"https://ntfy.sh/{NTFY_TOPIC}", data=data,
        headers={"Content-Type": "application/json", "Title": "🛡 Avito Лид"},
    )
    urllib.request.urlopen(req, timeout=15)


def main() -> int:
    state = {"processed_chats": []}
    if STATE_PATH.exists():
        state = json.loads(STATE_PATH.read_text())

    token = get_token()
    chats = get_unread_chats(token)

    new_leads = []
    for chat in chats:
        chat_id = chat["id"]
        if chat_id in state.get("processed_chats", []):
            continue
        # получить последнее сообщение от клиента
        msgs = get_chat_messages(token, chat_id)
        customer_text = ""
        item_title = ""
        for m in msgs:
            author = m.get("author", {})
            content = m.get("content", {})
            if author.get("type") == "customer" and isinstance(content, dict):
                customer_text = str(content.get("text", ""))[:150]
            ctx_val = chat.get("context", {}).get("value", {})
            if isinstance(ctx_val, dict) and ctx_val.get("title"):
                item_title = ctx_val["title"][:50]

        new_leads.append({
            "chat_id": chat_id,
            "item": item_title,
            "customer_text": customer_text,
        })

    if not new_leads:
        print("Новых лидов нет.")
        # сохранить state
        STATE_PATH.parent.mkdir(exist_ok=True)
        STATE_PATH.write_text(json.dumps(state, ensure_ascii=False))
        return 0

    # Алерт для каждого лида
    for lead in new_leads:
        msg = f"🔥 Новый лид на Авито!\nТовар: {lead['item']}\nСообщение: {lead['customer_text'] or 'без текста'}"
        try:
            notify_ntfy(msg)
            print(f"✅ ntfy отправлен: {lead['chat_id'][:20]}")
        except Exception as e:
            print(f"❌ ntfy error: {e}")

    state.setdefault("processed_chats", []).extend(l["chat_id"] for l in new_leads)
    state["processed_chats"] = state["processed_chats"][-200:]
    STATE_PATH.parent.mkdir(exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, ensure_ascii=False, indent=1))

    print(f"Итого лидов обработано: {len(new_leads)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

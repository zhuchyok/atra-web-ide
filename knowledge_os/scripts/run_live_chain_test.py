#!/usr/bin/env python3
"""
Проверка живой цепочки: Victoria (8010) → Department Heads / Task Distribution → результат.

Использование:
  cd knowledge_os && python scripts/run_live_chain_test.py
  VICTORIA_URL=http://localhost:8010 python scripts/run_live_chain_test.py

Перед запуском:
  1. Запустите Knowledge OS (Victoria, БД, при необходимости Veronica):
     docker-compose -f knowledge_os/docker-compose.yml up -d
  2. На сервере Victoria: USE_VICTORIA_ENHANCED=true, DATABASE_URL настроен
"""

import os
import sys

try:
    import requests
except ImportError:
    print("Установите: pip install requests")
    sys.exit(2)

VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8010")
GOAL = "Помоги с анализом данных"


def main():
    print(f"Живая цепочка: {VICTORIA_URL} goal={GOAL!r}")
    try:
        r = requests.get(f"{VICTORIA_URL}/health", timeout=5)
        if r.status_code != 200:
            print(f"Victoria /health: {r.status_code}")
            return 1
    except Exception as e:
        print(f"Victoria недоступна: {e}")
        print("Запустите: docker-compose -f knowledge_os/docker-compose.yml up -d")
        return 1

    payload = {"goal": GOAL, "project_context": "atra-web-ide", "chat_history": []}
    try:
        r = requests.post(
            f"{VICTORIA_URL}/run",
            json=payload,
            params={"async_mode": "false"},
            timeout=120,
        )
    except Exception as e:
        print(f"Ошибка запроса: {e}")
        return 1

    print(f"HTTP {r.status_code}")
    if r.status_code != 200:
        print(r.text[:1000])
        return 1

    data = r.json()
    method = (data.get("knowledge") or {}).get("method", "?")
    output = (data.get("output") or "").strip()
    print(f"method: {method}")
    print(f"output:\n{output[:2000]}")
    if data.get("status") != "success" or not output:
        return 1
    print("\nЖивая цепочка прошла успешно.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

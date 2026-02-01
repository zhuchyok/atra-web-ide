#!/usr/bin/env python3
"""
Один запрос к Victoria из терминала (удобно из Cursor Terminal).
Использование:
  python3 scripts/ask_victoria.py "привет"
  python3 scripts/ask_victoria.py "какой статус проекта?"
  python3 scripts/ask_victoria.py "покажи файлы в frontend"
"""
import sys
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from victoria_chat import (
    check_victoria_health,
    send_message,
    normalize_victoria_output,
    VICTORIA_URL,
    REMOTE_URL,
)

def main():
    if len(sys.argv) < 2:
        print("Использование: python3 scripts/ask_victoria.py \"ваш вопрос\"")
        print("Пример: python3 scripts/ask_victoria.py \"привет\"")
        sys.exit(1)

    goal = " ".join(sys.argv[1:]).strip()
    if not goal:
        print("Введите непустой вопрос.")
        sys.exit(1)

    url = VICTORIA_URL if check_victoria_health(VICTORIA_URL) else (REMOTE_URL if check_victoria_health(REMOTE_URL) else None)
    if not url:
        print("❌ Victoria недоступна (проверьте: curl http://localhost:8010/health)")
        sys.exit(1)

    project_context = os.getenv("PROJECT_CONTEXT", "atra-web-ide")
    print(f"🤖 Victoria ({url}) | проект: {project_context}")
    print(f"👤 Вы: {goal}\n")

    result = send_message(url, goal, project_context=project_context, async_run=True)
    if not result:
        print("❌ Нет ответа от Victoria.")
        sys.exit(1)

    if result.get("status") == "success":
        output = normalize_victoria_output(result.get("output"))
        print("🤖 Victoria:")
        print("-" * 50)
        print(output or "(пустой ответ)")
        print("-" * 50)
    else:
        print("❌", result.get("error", "Неизвестная ошибка"))
        sys.exit(1)

if __name__ == "__main__":
    main()

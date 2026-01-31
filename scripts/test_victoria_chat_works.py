#!/usr/bin/env python3
"""
Тест: чат с Victoria возвращает настоящий ответ (не шаблон).
Запуск: python3 scripts/test_victoria_chat_works.py
Требует: Victoria на 8010, MLX (11435) или Ollama (11434) на хосте.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

def main():
    import requests
    victoria_url = os.getenv("VICTORIA_URL", "http://localhost:8010")
    # 1. Health Victoria
    try:
        r = requests.get(f"{victoria_url}/health", timeout=5)
        if r.status_code != 200:
            print(f"FAIL: Victoria health {r.status_code}")
            return 1
    except Exception as e:
        print(f"FAIL: Victoria недоступна ({victoria_url}): {e}")
        return 1
    # 2. Call /run with "привет"
    try:
        r = requests.post(
            f"{victoria_url}/run",
            json={"goal": "привет", "max_steps": 500, "project_context": "atra-web-ide"},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"FAIL: /run error: {e}")
        return 1
    if data.get("status") != "success":
        print(f"FAIL: status={data.get('status')}, error={data.get('error')}")
        return 1
    output = (data.get("output") or "").strip()
    # 3. Не шаблон
    if "Получила ваш запрос" in output:
        print("FAIL: Victoria вернула шаблон (Получила ваш запрос). Нужны MLX/Ollama и перезапуск Victoria.")
        return 1
    if "Сейчас не могу подключиться к моделям" in output:
        print("FAIL: Модели недоступны. Запустите MLX (11435) или Ollama (11434), перезапустите victoria-agent.")
        return 1
    if len(output) < 10:
        print(f"FAIL: Слишком короткий ответ: {output!r}")
        return 1
    print("OK: Victoria вернула настоящий ответ:")
    print(output[:300] + ("..." if len(output) > 300 else ""))
    return 0

if __name__ == "__main__":
    sys.exit(main())

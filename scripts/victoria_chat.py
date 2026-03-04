#!/usr/bin/env python3
"""
Интерактивный чат с Victoria в терминале (через Rust Gateway)
Использование: python3 scripts/victoria_chat.py
"""

import sys
import os
import json
import threading
import time
import requests
import textwrap
import shutil
import argparse
from typing import Optional

# Global verbose flag
VERBOSE = False

def wrap_to_terminal(text: str, width: Optional[int] = None) -> str:
    """Перенос длинных строк по ширине терминала."""
    if width is None:
        try:
            width = shutil.get_terminal_size().columns - 2
        except Exception:
            width = 72
    width = max(40, min(width, 120))
    return textwrap.fill(text, width=width, replace_whitespace=False, drop_whitespace=False)

def check_victoria_health(url: str, verbose: bool = False) -> bool:
    """Проверить доступность Gateway"""
    try:
        # Убираем путь для проверки здоровья
        base = url.split('/v1/')[0]
        response = requests.get(f"{base}/health", timeout=5)
        return response.status_code == 200
    except Exception:
        return False

# URL Rust Gateway
VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8081/v1/chat/completions")
VICTORIA_SYNC_TIMEOUT = 600

def send_message(url: str, goal: str, chat_history: Optional[list] = None) -> Optional[dict]:
    """Отправить сообщение к Rust Gateway (OpenAI compatible)."""
    payload = {
        "model": "victoria-wisdom-v3.5:latest",
        "messages": [{"role": "user", "content": goal}],
        "use_rag": True,
        "stream": False
    }

    result_holder: list = []
    error_holder: list = []

    def _do_rust_request():
        try:
            r = requests.post(url, json=payload, timeout=VICTORIA_SYNC_TIMEOUT)
            r.raise_for_status()
            result_holder.append(r.json())
        except Exception as e:
            error_holder.append(e)

    thread = threading.Thread(target=_do_rust_request, daemon=True)
    thread.start()

    status_phases = ["думаю...", "подключаю модель...", "генерирую ответ...", "проверяю контекст...", "формулирую ответ..."]
    spinner = "|/-\\"
    phase_idx = 0
    spin_idx = 0
    last_phase_time = time.monotonic()

    while thread.is_alive():
        now = time.monotonic()
        if now - last_phase_time >= 2.5:
            phase_idx = (phase_idx + 1) % len(status_phases)
            last_phase_time = now
        phase = status_phases[phase_idx]
        char = spinner[spin_idx % len(spinner)]
        spin_idx += 1
        print(f"\r🤔 Victoria: {phase} {char} ", end="", flush=True)
        time.sleep(0.12)
    print("\r" + " " * 60 + "\r", end="", flush=True)

    if error_holder:
        return {"status": "error", "output": f"Error: {error_holder[0]}"}

    if result_holder:
        data = result_holder[0]
        content = data["choices"][0]["message"]["content"]
        return {"status": "success", "output": content}

    return None

def main():
    global VERBOSE
    parser = argparse.ArgumentParser(description='Victoria Chat via Rust Gateway')
    parser.add_argument('-v', '--verbose', action='store_true')
    args = parser.parse_args()
    VERBOSE = args.verbose

    print("=" * 60)
    print("🤖 VICTORIA CHAT (Rust Core) - Интерактивный чат")
    print("=" * 60)

    if not check_victoria_health(VICTORIA_URL):
        print(f"❌ Rust Gateway недоступен на {VICTORIA_URL}")
        print("💡 Запустите Gateway: cd rust_core/gateway && cargo run --release")
        sys.exit(1)

    print(f"✅ Подключено к Rust Gateway: {VICTORIA_URL}")
    print("💬 Введите сообщение (exit — выход):")
    print("-" * 60)

    chat_history = []
    while True:
        try:
            user_input = input("👤 Вы: ").strip()
            if not user_input: continue
            if user_input.lower() in ['exit', 'quit', 'q']: break

            result = send_message(VICTORIA_URL, user_input, chat_history)

            if result and result.get("status") == "success":
                output = result.get("output", "")
                print("\n" + "=" * 60)
                print("🤖 Victoria:")
                print("=" * 60)
                print(output)
                print("=" * 60 + "\n")
                chat_history.append({"user": user_input, "assistant": output})
            else:
                print(f"\n❌ Ошибка: {result.get('output') if result else 'Нет ответа'}")

        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"\n❌ Ошибка: {e}\n")

    print("\n👋 До свидания!")

if __name__ == "__main__":
    main()

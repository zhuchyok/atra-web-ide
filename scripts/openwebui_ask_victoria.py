#!/usr/bin/env python3
"""
Singularity 15.0: ask_victoria tool for Open WebUI.
Вызов Victoria /run для делегирования задачи (единая точка входа).
Использование: из Open WebUI как Python Tool или из CLI.

Переменные окружения:
  VICTORIA_URL — базовый URL Victoria (default: http://victoria-agent:8000 или http://localhost:8010)
  ASK_VICTORIA_TIMEOUT — таймаут в секундах (default: 600)

Пример вызова из кода:
  goal="Проверь бэкенд на ошибки"; project_context="atra-web-ide"; user_key="openwebui-123"
"""
import os
import sys
import json
import argparse
from typing import Optional

try:
    import httpx
except ImportError:
    print("Victoria is temporarily unavailable; try again later. (httpx not installed)", file=sys.stderr)
    sys.exit(1)

# Единый default: в Docker — localhost:8081 (Rust Gateway); с хоста задать VICTORIA_URL
DEFAULT_URL = os.getenv("VICTORIA_URL") or "http://localhost:8081/v1/chat/completions"
TIMEOUT = int(os.getenv("ASK_VICTORIA_TIMEOUT", "600"))
UNAVAILABLE_MSG = "Victoria is temporarily unavailable; try again later."


def ask_victoria(
    goal: str,
    project_context: str = "atra-web-ide",
    user_key: Optional[str] = None,
    session_id: Optional[str] = None,
    use_enhanced: bool = True,
    timeout: int = TIMEOUT,
    base_url: str = DEFAULT_URL,
) -> str:
    """
    Отправить задачу в Rust Gateway и вернуть текстовый результат.
    """
    payload = {
        "model": "victoria-wisdom-30b:latest",
        "messages": [{"role": "user", "content": goal}],
        "use_rag": True,
        "stream": false
    }

    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(base_url, json=payload)
            r.raise_for_status()
            data = r.json()
            return data["choices"][0]["message"]["content"]


def main():
    parser = argparse.ArgumentParser(description="Ask Victoria (Singularity 15.0 tool)")
    parser.add_argument("goal", nargs="?", default=None, help="Цель/запрос для Victoria")
    parser.add_argument("--project", "-p", default="atra-web-ide", help="project_context (default: atra-web-ide)")
    parser.add_argument("--user-key", "-u", default=None, help="user_key / session_id для LTM (e.g. openwebui-{id})")
    parser.add_argument("--no-enhanced", action="store_true", help="Отключить Victoria Enhanced")
    parser.add_argument("--timeout", "-t", type=int, default=TIMEOUT, help=f"Timeout in seconds (default: {TIMEOUT})")
    parser.add_argument("--url", default=DEFAULT_URL, help="Victoria base URL")
    parser.add_argument("--json", action="store_true", help="Read goal from stdin as JSON: {\"goal\": \"...\", \"project_context\": \"...\"}")
    args = parser.parse_args()

    if args.json:
        try:
            inp = json.load(sys.stdin)
            goal = inp.get("goal", "")
            project_context = inp.get("project_context", args.project)
            user_key = inp.get("user_key") or inp.get("session_id") or args.user_key
        except Exception:
            print(UNAVAILABLE_MSG, file=sys.stderr)
            sys.exit(1)
    else:
        goal = args.goal or sys.stdin.read().strip()
        project_context = args.project
        user_key = args.user_key

    if not goal:
        print("Usage: openwebui_ask_victoria.py <goal> [--project atra-web-ide] [--user-key openwebui-ID]", file=sys.stderr)
        sys.exit(2)

    result = ask_victoria(
        goal=goal,
        project_context=project_context,
        user_key=user_key,
        use_enhanced=not args.no_enhanced,
        timeout=args.timeout,
        base_url=args.url,
    )
    print(result)


if __name__ == "__main__":
    main()

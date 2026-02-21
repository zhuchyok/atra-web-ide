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

# Единый default: в Docker — victoria-agent:8000; с хоста задать VICTORIA_URL=http://localhost:8010
DEFAULT_URL = os.getenv("VICTORIA_URL") or "http://victoria-agent:8000"
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
    Отправить задачу в Victoria /run и вернуть текстовый результат.
    При недоступности Victoria возвращает понятное сообщение для пользователя.
    """
    url = f"{base_url.rstrip('/')}/run"
    payload = {
        "goal": goal,
        "project_context": project_context,
        "use_enhanced": use_enhanced,
    }
    if user_key:
        payload["session_id"] = user_key
    elif session_id:
        payload["session_id"] = session_id

    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, json=payload)
            r.raise_for_status()
            data = r.json()
    except httpx.ConnectError:
        return UNAVAILABLE_MSG
    except httpx.TimeoutException:
        return "Victoria took too long to respond; try again or simplify the request."
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 503:
            return UNAVAILABLE_MSG
        return f"Victoria returned an error (HTTP {e.response.status_code}). Try again later."
    except Exception as e:
        return f"{UNAVAILABLE_MSG} ({type(e).__name__})"

    status = data.get("status", "")
    output = data.get("output") or data.get("result") or ""
    if isinstance(output, dict):
        output = output.get("result", str(output))
    if not isinstance(output, str):
        output = str(output)

    if status != "success" and not output:
        return data.get("error") or UNAVAILABLE_MSG

    # Уточняющие вопросы — отдаём как читаемый текст
    clarification = data.get("clarification_questions") or data.get("knowledge", {}).get("clarification_questions")
    if clarification:
        if isinstance(clarification, list):
            lines = [f"Мне нужно уточнить: {q}" if isinstance(q, str) else str(q) for q in clarification]
            clarification_text = "\n".join(lines)
        else:
            clarification_text = str(clarification)
        return clarification_text + ("\n\n" + output if output else "")

    return output


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

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Тест чата с Victoria по тому же контракту, что и Telegram-бот (POST /run).
Простые, средние и сложные вопросы — без реальной отправки в Telegram.

Запуск:
  cd /path/to/atra-web-ide
  python3 scripts/test_telegram_chat_victoria.py           # все три: простой, средний, сложный
  python3 scripts/test_telegram_chat_victoria.py --quick   # только простой вопрос (15 с таймаут)

Требуется: Victoria на http://localhost:8010 (docker-compose -f knowledge_os/docker-compose.yml up -d).
Средний и сложный вопросы могут занимать 1–3 минуты (LLM).
"""

import asyncio
import os
import sys

import httpx

# Корень проекта для импортов
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8010")
TIMEOUT_SIMPLE = 30
TIMEOUT_MEDIUM = 90
TIMEOUT_COMPLEX = 180

QUESTIONS = [
    ("simple", "Привет! Как дела?", TIMEOUT_SIMPLE),
    ("medium", "Объясни кратко, как настроить docker для проекта на Python.", TIMEOUT_MEDIUM),
    ("complex", "Спланируй поэтапно внедрение мониторинга в наш стек: Prometheus, Grafana, алерты. Только план, без кода.", TIMEOUT_COMPLEX),
]

# --quick: только простой вопрос, таймаут 15 сек (для быстрой проверки)
QUICK_SIMPLE_TIMEOUT = 15


def _parse_output(data: dict) -> str:
    out = data.get("output") or data.get("response") or data.get("result")
    if out is not None:
        return str(out)[:1500]
    if data.get("status") == "needs_clarification":
        qs = data.get("clarification_questions", [])
        return "needs_clarification: " + "; ".join(qs[:3]) if qs else "needs_clarification"
    return data.get("error", "no output")


async def ask_victoria(goal: str, timeout_sec: int) -> tuple[bool, str]:
    """Один запрос к Victoria POST /run (как Telegram-бот)."""
    payload = {
        "goal": goal,
        "project_context": os.getenv("PROJECT_NAME", "atra-web-ide"),
        "max_steps": 500,
    }
    try:
        async with httpx.AsyncClient(timeout=float(timeout_sec + 10)) as client:
            r = await client.post(f"{VICTORIA_URL}/run", json=payload)
            if r.status_code == 200:
                data = r.json()
                return True, _parse_output(data)
            return False, f"HTTP {r.status_code}: {(r.text or '')[:300]}"
    except httpx.TimeoutException:
        return False, f"timeout ({timeout_sec}s)"
    except Exception as e:
        return False, f"{type(e).__name__}: {e}"


async def main():
    quick = "--quick" in sys.argv
    print("=" * 60)
    print("Тест чата с Victoria (контракт как у Telegram-бота)")
    print(f"Victoria URL: {VICTORIA_URL}" + (" [--quick: только простой вопрос]" if quick else ""))
    print("=" * 60)

    # Проверка здоровья Victoria
    try:
        async with httpx.AsyncClient(timeout=5.0) as c:
            h = await c.get(f"{VICTORIA_URL}/health")
            if h.status_code != 200:
                print(f"⚠️ Victoria /health вернул {h.status_code}. Запустите: docker-compose -f knowledge_os/docker-compose.yml up -d")
                return
            print("✅ Victoria /health OK\n")
    except Exception as e:
        print(f"❌ Victoria недоступна: {e}")
        print("   Запустите: docker-compose -f knowledge_os/docker-compose.yml up -d\n")
        return

    to_run = [(QUESTIONS[0][0], QUESTIONS[0][1], QUICK_SIMPLE_TIMEOUT)] if quick else QUESTIONS
    for level, question, timeout in to_run:
        print(f"[{level.upper()}] Вопрос ({timeout}s): {question[:70]}{'...' if len(question) > 70 else ''}")
        ok, out = await ask_victoria(question, timeout)
        if ok:
            preview = (out or "").strip()[:400]
            print(f"     Ответ: {preview}{'...' if len(out or '') > 400 else ''}")
        else:
            print(f"     Ошибка: {out}")
        print()
        await asyncio.sleep(0.5)

    print("=" * 60)
    print("Тест завершён.")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

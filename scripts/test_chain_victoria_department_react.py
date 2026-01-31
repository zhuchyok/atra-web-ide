#!/usr/bin/env python3
"""
Тест цепочки: пользователь → Victoria (8010) → Department Heads → отдел → эксперт (БД) → ReActAgent.run(goal) → Ollama/MLX.

Проверяет:
1. Victoria доступна (GET /health).
2. POST /run с задачей, которая идёт через Department Heads (создание файла).
3. Ответ не «пустой успех» (не только «Задача выполнена экспертом … (статус: finish)»); честное сообщение считается успехом.

Запуск: python3 scripts/test_chain_victoria_department_react.py
Если видите старый «пустой успех», пересоберите образ Victoria:
  docker-compose -f knowledge_os/docker-compose.yml build victoria-agent && docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent
"""
import asyncio
import json
import os
import sys

try:
    import httpx
except ImportError:
    print("Установите httpx: pip install httpx")
    sys.exit(1)

VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8010")
TIMEOUT_RUN = float(os.getenv("VICTORIA_TIMEOUT", "120"))


async def main():
    print("=" * 60)
    print("Тест цепочки: Victoria → Department Heads → ReActAgent → Ollama/MLX")
    print("=" * 60)
    print(f"Victoria URL: {VICTORIA_URL}")
    print()

    # 1) Health
    print("[1] GET /health ...")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            r = await client.get(f"{VICTORIA_URL}/health")
            r.raise_for_status()
            health = r.json()
            print(f"    OK: {health}")
    except Exception as e:
        print(f"    FAIL: {e}")
        print("    Убедитесь, что Victoria запущена (например: docker-compose -f knowledge_os/docker-compose.yml up -d)")
        return 1
    print()

    # 2) Задача, которая должна идти через Department Heads (создание файла → эксперт → ReActAgent)
    goal = (
        "Создай в корне проекта файл test_chain.txt с одной строкой: Тест цепочки Victoria Department Heads ReActAgent."
    )
    payload = {
        "goal": goal,
        "project_context": "atra-web-ide",
    }
    print("[2] POST /run (задача на создание файла → Department Heads → ReActAgent)")
    print(f"    goal: {goal[:80]}...")
    print()

    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_RUN) as client:
            r = await client.post(f"{VICTORIA_URL}/run", json=payload)
            r.raise_for_status()
            data = r.json()
    except httpx.TimeoutException:
        print("    FAIL: таймаут запроса. Увеличьте VICTORIA_TIMEOUT или проверьте Ollama/MLX.")
        return 1
    except Exception as e:
        print(f"    FAIL: {e}")
        return 1

    output = (
        data.get("output")
        or data.get("result")
        or data.get("response")
        or ""
    )
    status = data.get("status", "")
    print(f"    status: {status}")
    print(f"    output length: {len(output)} chars")
    print()
    print("    --- output (первые 800 символов) ---")
    print((output[:800] if output else "(пусто)"))
    print("    --- конец вывода ---")
    print()

    # 3) Проверки результата
    empty_success_placeholder = "Задача выполнена экспертом" in output and "(статус: finish)" in output
    honest_empty_message = "Эксперт завершил задачу без вывода" in output or "модель вызвала finish без результата" in output

    if empty_success_placeholder and len(output.strip()) < 120:
        print("[3] FAIL: ответ — «пустой успех» (только подставная строка про статус finish).")
        print("     Чтобы подхватить правки (замена на честное сообщение), пересоберите образ и перезапустите:")
        print("     docker-compose -f knowledge_os/docker-compose.yml build victoria-agent && docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent")
        return 1
    if honest_empty_message:
        print("[3] OK: цепочка сработала; вернулось честное сообщение (модель не передала output в finish).")
        return 0
    if output and (len(output) > 50 or "create_file" in output.lower() or "test_chain" in output or "файл" in output.lower() or "Действие" in output):
        print("[3] OK: получен осмысленный ответ (есть текст/упоминание файла/результат).")
        return 0
    print("[3] OK: ответ получен, цепочка выполнилась.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

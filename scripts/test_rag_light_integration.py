#!/usr/bin/env python3
"""
Интеграционный тест RAG-light и рекомендаций Agent (Фаза 2).
Проверяет POST /api/chat/stream в режиме Ask: шаблон, RAG-light, рекомендация.
Запуск: из корня проекта, бэкенд на localhost:8080
  python3 scripts/test_rag_light_integration.py
  BACKEND_URL=http://localhost:8080 python3 scripts/test_rag_light_integration.py
"""
import asyncio
import json
import os
import sys

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8080")


async def test_stream_query(session, query: str, mode: str = "ask"):
    """Отправляет запрос в stream и собирает step titles."""
    url = f"{BACKEND_URL}/api/chat/stream"
    body = {
        "content": query,
        "mode": mode,
        "use_victoria": True,
    }
    steps = []  # list of (title, content)
    try:
        async with session.post(
            url,
            json=body,
            headers={"Accept": "text/event-stream", "Content-Type": "application/json"},
            timeout=60,
        ) as response:
            if response.status != 200:
                return steps, f"HTTP {response.status}"
            buffer = ""
            async for chunk in response.content:
                if chunk:
                    buffer += chunk.decode("utf-8", errors="replace")
                    while "\n" in buffer:
                        line, buffer = buffer.split("\n", 1)
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                if data.get("type") == "step":
                                    steps.append((data.get("title", ""), data.get("content", "")))
                                if data.get("type") == "end":
                                    return steps, None
                            except json.JSONDecodeError:
                                pass
    except asyncio.TimeoutError:
        return steps, "timeout"
    except Exception as e:
        return steps, str(e)
    return steps, None


async def main():
    try:
        import aiohttp
    except ImportError:
        print("Установите aiohttp: pip install aiohttp")
        sys.exit(1)

    test_cases = [
        {"query": "привет", "mode": "ask", "expect": "template"},
        {"query": "сколько стоит подписка?", "mode": "ask", "expect": "rag_light_or_llm"},
        {"query": "проанализируй мои логи на предмет ошибок", "mode": "ask", "expect": "suggestion_or_llm"},
    ]

    print("Интеграционный тест RAG-light / рекомендаций (Фаза 2)")
    print(f"BACKEND_URL = {BACKEND_URL}\n")

    async with aiohttp.ClientSession() as session:
        for test in test_cases:
            q = test["query"]
            print(f"Тест: {q[:50]}...")
            steps, err = await test_stream_query(session, q, test["mode"])
            if err:
                print(f"  Ошибка: {err}")
                continue
            titles = [t for t, _ in steps]
            contents = " ".join(c for _, c in steps)
            if "Найдено в БЗ" in titles:
                print("  RAG-light путь")
            if "Рекомендация" in titles:
                print("  Рекомендация Agent показана")
            if "Шаблонный ответ" in contents or "шаблон" in contents.lower():
                print("  Горячий путь (шаблон)")
            if "Быстрый ответ" in titles and "Найдено в БЗ" not in titles and "Рекомендация" not in titles and "шаблон" not in contents.lower():
                print("  Путь быстрого ответа (MLX/Ollama)")
            if not steps:
                print("  Нет шагов (проверьте бэкенд)")
    print("\nГотово.")


if __name__ == "__main__":
    asyncio.run(main())

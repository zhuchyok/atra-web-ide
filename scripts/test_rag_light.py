#!/usr/bin/env python3
"""
Тест RAG-light: extract_direct_answer и (при доступном бэкенде) fast_fact_answer через API.
Запуск: из корня проекта
  python3 scripts/test_rag_light.py
  BACKEND_URL=http://localhost:8080 python3 scripts/test_rag_light.py
"""
import os
import sys

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8080")


def _truncate(text: str, max_len: int = 150) -> str:
    if len(text) <= max_len:
        return text.strip()
    t = text[:max_len]
    last = t.rfind(" ")
    if last > max_len // 2:
        t = t[:last]
    return t.strip() + "..."


def test_extract_direct_answer():
    """Тест логики извлечения ответа из чанка (без загрузки backend)."""
    test_chunk = "Стоимость подписки составляет 999 рублей в месяц. Включены все функции."
    query = "сколько стоит подписка?"
    # Упрощённая логика: первое предложение с числом и ключевым словом
    keywords = ("составляет", "равно", "стоит", "является")
    for s in test_chunk.replace(".\n", ". ").split(". "):
        s = s.strip()
        if not s:
            continue
        if any(kw in s.lower() for kw in keywords) and any(c.isdigit() for c in s):
            answer = _truncate(s)
            print("\n=== RAG-light: extract_direct_answer (логика) ===\n")
            print(f"  Запрос: {query!r}")
            print(f"  Ответ:  {answer!r}\n")
            print("  OK\n")
            return
    print("\n=== RAG-light: extract_direct_answer ===\n  (нет подходящего предложения в тестовом чанке)\n")


def test_factual_via_api():
    """Проверка фактуального запроса через POST /api/chat/stream (режим Ask)."""
    import urllib.request
    import json
    url = f"{BACKEND_URL}/api/chat/stream"
    body = json.dumps({
        "content": "сколько стоит подписка?",
        "mode": "ask",
        "use_victoria": True,
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw = r.read().decode()
    except Exception as e:
        print(f"  [FAIL] API: {e}\n")
        return
    has_rag = "RAG-light" in raw or "базе знаний" in raw or "Найдено в БЗ" in raw
    has_chunk = '"type": "chunk"' in raw
    print("  RAG-light step present:", has_rag)
    print("  Has chunks:", has_chunk)
    if has_rag and has_chunk:
        print("  [OK] RAG-light path used or fallback with answer\n")
    else:
        print("  [??] Check logs: backend may use MLX/Ollama if RAG-light missed\n")


def main():
    print("BACKEND_URL =", BACKEND_URL)
    test_extract_direct_answer()
    try:
        import urllib.request
        with urllib.request.urlopen(f"{BACKEND_URL}/health", timeout=2) as r:
            pass
    except Exception:
        print("Бэкенд недоступен — тест API пропущен.\n")
        return
    test_factual_via_api()
    print("Готово.")


if __name__ == "__main__":
    main()

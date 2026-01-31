#!/usr/bin/env python3
"""
Проверка путей Фазы 1: QueryClassifier, шаблонные ответы, mode/health.
Запуск: из корня проекта
  python scripts/test_paths.py
  BACKEND_URL=http://localhost:8080 python scripts/test_paths.py
"""
import os
import sys
import time
import urllib.request
import urllib.parse
import json

# Добавляем backend в path для локального вызова classify_query без сервера
BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8080")

# Тестовые запросы: (текст, ожидаемый type)
TEST_QUERIES = [
    ("привет", "simple"),
    ("как дела?", "simple"),
    ("спасибо большое!", "simple"),
    ("понятно", "simple"),
    ("сколько стоит подписка?", "factual"),
    ("что такое RAG?", "factual"),
    ("как настроить PostgreSQL?", "factual"),  # factual (как настроить); можно считать complex при длине
    ("проанализируй мои логи", "complex"),
]


def test_classifier_via_api():
    """Проверка классификатора через GET /api/chat/classify?q=..."""
    print("\n=== Классификатор (GET /api/chat/classify) ===\n")
    ok = 0
    for query, expected_type in TEST_QUERIES:
        url = f"{BACKEND_URL}/api/chat/classify?q={urllib.parse.quote(query)}"
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                data = json.loads(r.read().decode())
        except Exception as e:
            print(f"  [FAIL] {query!r}: {e}")
            continue
        got = data.get("classification", {}).get("type", "?")
        template = data.get("template_response")
        if got == expected_type:
            print(f"  [OK]   {query!r} -> {got} (template={bool(template)})")
            ok += 1
        else:
            print(f"  [??]   {query!r} -> {got} (expected {expected_type}) template={bool(template)}")
    print(f"\nИтого: {ok}/{len(TEST_QUERIES)}")
    return ok == len(TEST_QUERIES)


def test_classifier_local():
    """Проверка классификатора локально (без сервера и без зависимостей backend)."""
    import importlib.util
    root = os.path.join(os.path.dirname(__file__), "..")
    path = os.path.join(root, "backend", "app", "services", "query_classifier.py")
    if not os.path.isfile(path):
        print("\n=== Классификатор (локально): файл не найден ===\n")
        return False
    spec = importlib.util.spec_from_file_location("query_classifier", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    classify_query = mod.classify_query
    get_template_response = mod.get_template_response

    print("\n=== Классификатор (локально) ===\n")
    ok = 0
    for query, expected_type in TEST_QUERIES:
        classification = classify_query(query)
        got = classification.get("type", "?")
        template = get_template_response(query, None) if got == "simple" else None
        if got == expected_type:
            tpreview = (template[:40] + "...") if template and len(template) > 40 else (template or "-")
            print(f"  [OK]   {query!r} -> {got} (template={tpreview})")
            ok += 1
        else:
            print(f"  [??]   {query!r} -> {got} (expected {expected_type})")
    print(f"\nИтого: {ok}/{len(TEST_QUERIES)}")
    return ok == len(TEST_QUERIES)


def test_mode_health():
    """Проверка GET /api/chat/mode/health"""
    print("\n=== Mode health (GET /api/chat/mode/health) ===\n")
    try:
        with urllib.request.urlopen(f"{BACKEND_URL}/api/chat/mode/health", timeout=5) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False
    for mode in ("ask", "agent", "plan"):
        block = data.get(mode, {})
        avail = block.get("_available", "?")
        print(f"  {mode}: _available={avail}, keys={list(block.keys())}")
    print()
    return True


def test_ask_hot_path():
    """Проверка горячего пути Ask: POST /api/chat/stream с 'привет', mode=ask."""
    print("\n=== Hot path Ask (POST /api/chat/stream, привет, mode=ask) ===\n")
    url = f"{BACKEND_URL}/api/chat/stream"
    body = json.dumps({
        "content": "привет",
        "mode": "ask",
        "use_victoria": True,
    }).encode()
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": "application/json"})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read().decode()
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False
    elapsed = (time.perf_counter() - start) * 1000
    # Горячий путь: нет шага "Проверяю MLX" и есть чанки или шаг "Шаблонный ответ" / "без вызова LLM"
    no_mlx_step = "Проверяю MLX" not in raw
    has_template_step = "Шаблонный ответ" in raw or "без вызова LLM" in raw or "шаблон" in raw.lower()
    has_chunks = '"type": "chunk"' in raw and '"type": "end"' in raw
    ok = no_mlx_step and (has_template_step or has_chunks)
    if ok:
        print(f"  [OK]   Шаблонный путь использован, ответ за {elapsed:.0f} ms")
    else:
        print(f"  [??]   template={has_template_step}, no_mlx={no_mlx_step}, chunks={has_chunks}, {elapsed:.0f} ms")
    return ok


def main():
    print("BACKEND_URL =", BACKEND_URL)
    # Локальная проверка классификатора (всегда)
    test_classifier_local()
    # Через API (если бэкенд доступен)
    try:
        with urllib.request.urlopen(f"{BACKEND_URL}/health", timeout=2) as r:
            pass
    except Exception as e:
        print(f"\nБэкенд недоступен ({BACKEND_URL}) — проверки через API пропущены.")
        print("  Запустите бэкенд (docker-compose up -d backend или uvicorn) и повторите.")
        return
    test_classifier_via_api()
    test_mode_health()
    test_ask_hot_path()
    print("\nГотово.")


if __name__ == "__main__":
    main()

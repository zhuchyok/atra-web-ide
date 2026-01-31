#!/usr/bin/env python3
"""
Тест рекомендаций перехода в режим Агент (Фаза 2, день 3–4).
Запуск: из корня проекта
  python3 scripts/test_agent_suggestions.py
  BACKEND_URL=http://localhost:8080 python3 scripts/test_agent_suggestions.py
"""
import os
import sys

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8080")

# Запросы, для которых ожидаем рекомендацию Agent
SHOULD_SUGGEST = [
    "проанализируй мои логи и найди ошибки",
    "сравни производительность двух алгоритмов и дай рекомендации",
    "разработай план по миграции с MySQL на PostgreSQL",
    "оцени риски внедрения новой системы и предложи стратегию",
]
# Запросы, для которых не рекомендуем Agent
SHOULD_NOT_SUGGEST = [
    "сколько времени работает сервер",
    "как создать базу данных",
    "привет",
    "что такое Docker",
]


def test_analyze_complexity_local():
    """Тест analyze_complexity локально (без бэкенда)."""
    path = os.path.join(
        os.path.dirname(__file__), "..", "backend", "app", "services", "query_classifier.py"
    )
    if not os.path.isfile(path):
        print("Файл query_classifier.py не найден")
        return
    import importlib.util
    spec = importlib.util.spec_from_file_location("query_classifier", path)
    mod = importlib.util.module_from_spec(spec)
    # Мокаем get_settings если нужен config
    spec.loader.exec_module(mod)
    analyze_complexity = mod.analyze_complexity

    print("\n=== Рекомендации Agent (локально) ===\n")
    ok = 0
    for query in SHOULD_SUGGEST:
        r = analyze_complexity(query)
        suggest = r.get("suggest_agent", False)
        score = r.get("complexity_score", 0)
        if suggest:
            print(f"  [OK]   Рекомендуем Agent: {query[:50]}... (score={score})")
            ok += 1
        else:
            print(f"  [??]   Ожидали рекомендацию: {query[:50]}... (score={score})")
    for query in SHOULD_NOT_SUGGEST:
        r = analyze_complexity(query)
        suggest = r.get("suggest_agent", False)
        score = r.get("complexity_score", 0)
        if not suggest:
            print(f"  [OK]   Не рекомендуем: {query[:50]}... (score={score})")
            ok += 1
        else:
            print(f"  [??]   Не ожидали рекомендацию: {query[:50]}... (score={score})")
    total = len(SHOULD_SUGGEST) + len(SHOULD_NOT_SUGGEST)
    print(f"\nИтого: {ok}/{total}\n")


def test_classify_via_api():
    """Проверка suggest_agent через GET /api/chat/classify."""
    import urllib.request
    import urllib.parse
    import json
    print("=== Рекомендации Agent (API) ===\n")
    for query in SHOULD_SUGGEST[:2] + SHOULD_NOT_SUGGEST[:2]:
        url = f"{BACKEND_URL}/api/chat/classify?q={urllib.parse.quote(query)}"
        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                data = json.loads(r.read().decode())
        except Exception as e:
            print(f"  [FAIL] {query[:40]}...: {e}")
            continue
        c = data.get("classification", {})
        suggest = c.get("suggest_agent", False)
        score = c.get("complexity_score", 0)
        print(f"  suggest_agent={suggest}, score={score}: {query[:45]}...")
    print()


def main():
    print("BACKEND_URL =", BACKEND_URL)
    test_analyze_complexity_local()
    try:
        import urllib.request
        with urllib.request.urlopen(f"{BACKEND_URL}/health", timeout=2) as r:
            pass
    except Exception:
        print("Бэкенд недоступен — тест API пропущен.\n")
        return
    test_classify_via_api()
    print("Готово.")


if __name__ == "__main__":
    main()

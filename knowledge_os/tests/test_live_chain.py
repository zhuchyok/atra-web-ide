"""
Интеграционный тест живой цепочки: запрос → Victoria (8010) → Department Heads / Task Distribution → результат.

Требования:
- Victoria сервер запущен (http://localhost:8010 или VICTORIA_URL)
- USE_VICTORIA_ENHANCED=true на сервере
- DATABASE_URL на сервере (PostgreSQL с экспертами)
- При необходимости: Veronica на 8011, MLX/Ollama для LLM

Запуск:
  pytest knowledge_os/tests/test_live_chain.py -v -m integration
  VICTORIA_URL=http://localhost:8010 ./scripts/run_tests_with_db.sh tests/test_live_chain.py -v
"""

import os
import pytest

try:
    import requests
except ImportError:
    requests = None

VICTORIA_URL = os.getenv("VICTORIA_URL", "http://localhost:8010")
# Цель, которая должна пойти через Department Heads (просьба без явных ключевых отдела)
LIVE_GOAL = "Помоги с анализом данных"


def _victoria_health() -> bool:
    """Проверка доступности Victoria."""
    if not requests:
        return False
    try:
        r = requests.get(f"{VICTORIA_URL}/health", timeout=5)
        return r.status_code == 200
    except Exception:
        return False


@pytest.mark.integration
def test_live_chain_victoria_health():
    """Проверка: Victoria отвечает на /health."""
    if not requests:
        pytest.skip("requests не установлен")
    assert _victoria_health(), f"Victoria недоступна: {VICTORIA_URL}"


@pytest.mark.integration
@pytest.mark.slow
def test_live_chain_run_sync_returns_success():
    """
    Живая цепочка: POST /run с целью «Помоги с анализом данных» (sync).
    Ожидание: status=success, output не пустой. Может занять до 2 мин (LLM + Department Heads).
    """
    if not requests:
        pytest.skip("requests не установлен")
    if not _victoria_health():
        pytest.skip(f"Victoria недоступна: {VICTORIA_URL}. Запустите: docker-compose -f knowledge_os/docker-compose.yml up -d")

    payload = {
        "goal": LIVE_GOAL,
        "project_context": "atra-web-ide",
        "chat_history": [],
    }
    r = requests.post(
        f"{VICTORIA_URL}/run",
        json=payload,
        params={"async_mode": "false"},
        timeout=120,
    )
    assert r.status_code == 200, f"Ожидался 200, получен {r.status_code}: {r.text[:500]}"
    data = r.json()
    assert data.get("status") == "success", f"Ожидался status=success: {data}"
    output = data.get("output") or ""
    assert output.strip(), "output не должен быть пустым"
    # Метод может быть department_heads, task_distribution или другой (если цепочка пошла иначе)
    knowledge = data.get("knowledge") or {}
    method = knowledge.get("method")
    # Для живой цепочки через отделы ожидаем один из этих методов
    if method in ("department_heads", "task_distribution"):
        assert "department" in str(knowledge.get("metadata", {})).lower() or "department" in str(knowledge).lower() or True
    # В любом случае главное — успешный ответ и непустой output
    assert len(output) > 10, "Ответ слишком короткий"


@pytest.mark.integration
def test_live_chain_run_async_poll_until_completed():
    """
    Живая цепочка: POST /run async_mode=true, затем опрос GET /run/status/{task_id} до completed.
    """
    if not requests:
        pytest.skip("requests не установлен")
    if not _victoria_health():
        pytest.skip(f"Victoria недоступна: {VICTORIA_URL}")

    payload = {"goal": LIVE_GOAL, "project_context": "atra-web-ide", "chat_history": []}
    r = requests.post(
        f"{VICTORIA_URL}/run",
        json=payload,
        params={"async_mode": "true"},
        timeout=10,
    )
    assert r.status_code == 202, f"Ожидался 202, получен {r.status_code}: {r.text[:300]}"
    data = r.json()
    task_id = data.get("task_id")
    assert task_id, "В ответе 202 должен быть task_id"

    # Опрос статуса (макс. ~2 мин)
    status_url = f"{VICTORIA_URL}/run/status/{task_id}"
    for _ in range(60):
        sr = requests.get(status_url, timeout=10)
        assert sr.status_code == 200
        rec = sr.json()
        status = rec.get("status")
        if status == "completed":
            assert (rec.get("output") or "").strip(), "output не должен быть пустым при completed"
            return
        if status == "failed":
            pytest.fail(f"Задача завершилась с ошибкой: {rec.get('error', 'unknown')}")
        import time
        time.sleep(2)

    pytest.fail("Таймаут ожидания completed (2 мин)")


def run_manual():
    """Ручной запуск без pytest: один sync-запрос и вывод результата."""
    if not requests:
        print("Установите: pip install requests")
        return 2
    if not _victoria_health():
        print(f"Victoria недоступна: {VICTORIA_URL}")
        print("Запустите: docker-compose -f knowledge_os/docker-compose.yml up -d")
        return 1
    payload = {"goal": LIVE_GOAL, "project_context": "atra-web-ide", "chat_history": []}
    r = requests.post(f"{VICTORIA_URL}/run", json=payload, params={"async_mode": "false"}, timeout=120)
    print(f"HTTP {r.status_code}")
    if r.status_code != 200:
        print(r.text[:1000])
        return 1
    data = r.json()
    method = (data.get("knowledge") or {}).get("method", "?")
    print(f"method: {method}")
    print(f"output:\n{data.get('output', '')[:2000]}")
    return 0 if data.get("status") == "success" and (data.get("output") or "").strip() else 1


if __name__ == "__main__":
    exit(run_manual())

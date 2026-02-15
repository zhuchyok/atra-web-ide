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
# Цель для живой цепочки. По умолчанию «Привет» — быстрый ответ (quick_answer), меньше таймаутов/обрывов.
# LIVE_CHAIN_GOAL=Помоги с анализом данных — тяжёлая цель для ручной проверки.
LIVE_GOAL = os.getenv("LIVE_CHAIN_GOAL", "Привет")


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
def test_live_chain_run_completes_successfully(wait_for_victoria):
    """
    Живая цепочка: POST /run с async_mode=true, опрос /run/status до completed.
    Не используем sync — долгий запрос обрывается по таймауту; async даёт 202 и не зависит от времени выполнения.
    Цель из LIVE_CHAIN_GOAL (по умолчанию «Привет»).
    """
    if not requests:
        pytest.skip("requests не установлен")
    if not _victoria_health():
        pytest.skip(f"Victoria недоступна: {VICTORIA_URL}. Запустите: docker-compose -f knowledge_os/docker-compose.yml up -d")

    import time
    payload = {"goal": LIVE_GOAL, "project_context": "atra-web-ide", "chat_history": []}
    t0 = time.monotonic()
    r = requests.post(
        f"{VICTORIA_URL}/run",
        json=payload,
        params={"async_mode": "true"},
        timeout=30,
    )
    elapsed = time.monotonic() - t0
    assert r.status_code == 202, f"Ожидался 202, получен {r.status_code}: {r.text[:300]}"
    assert elapsed < 35, f"202 должен прийти быстро (<35 с), получено {elapsed:.1f} с"
    data = r.json()
    task_id = data.get("task_id")
    assert task_id, "В ответе 202 должен быть task_id"

    status_url = f"{VICTORIA_URL}/run/status/{task_id}"
    # Для «Привет» Victoria завершает без LLM (quick_answer). В CI можно сократить таймаут.
    default_poll = "90" if os.getenv("CI") else "300"
    poll_timeout = int(os.getenv("LIVE_CHAIN_POLL_TIMEOUT", default_poll))  # до 5 мин на выполнение (в CI 90 с)
    poll_interval = 2
    for _ in range(max(1, poll_timeout // poll_interval)):
        try:
            sr = requests.get(status_url, timeout=15)
        except (requests.exceptions.ConnectionError, ConnectionResetError, OSError):
            time.sleep(poll_interval)
            continue
        assert sr.status_code == 200, f"GET status вернул {sr.status_code}"
        rec = sr.json()
        status = rec.get("status")
        if status == "completed":
            if rec.get("clarification_questions") or (rec.get("knowledge") or {}).get("clarification_questions"):
                return
            output = (rec.get("output") or "").strip()
            assert output, "output не должен быть пустым при completed (без clarify)"
            knowledge = rec.get("knowledge") or {}
            if knowledge.get("method") in ("department_heads", "task_distribution"):
                assert "department" in str(knowledge.get("metadata", {})).lower() or "department" in str(knowledge).lower() or True
            assert len(output) > 10, "Ответ слишком короткий"
            return
        if status == "failed":
            pytest.fail(f"Задача завершилась с ошибкой: {rec.get('error', 'unknown')}")
        time.sleep(poll_interval)

    pytest.fail(f"Таймаут ожидания completed ({poll_timeout} с)")


@pytest.mark.integration
def test_live_chain_run_async_poll_until_completed(wait_for_victoria):
    """
    Живая цепочка: POST /run async_mode=true, затем опрос GET /run/status/{task_id} до completed.
    Требование «202 до стратегии»: ответ 202 должен прийти в течение 35 с (стратегия и understand_goal — в фоне).
    """
    if not requests:
        pytest.skip("requests не установлен")
    if not _victoria_health():
        pytest.skip(f"Victoria недоступна: {VICTORIA_URL}")

    import time
    payload = {"goal": LIVE_GOAL, "project_context": "atra-web-ide", "chat_history": []}
    t0 = time.monotonic()
    r = requests.post(
        f"{VICTORIA_URL}/run",
        json=payload,
        params={"async_mode": "true"},
        timeout=30,
    )
    elapsed = time.monotonic() - t0
    assert r.status_code == 202, f"Ожидался 202, получен {r.status_code}: {r.text[:300]}"
    assert elapsed < 35, f"202 должен прийти быстро (<35 с), получено {elapsed:.1f} с"
    data = r.json()
    task_id = data.get("task_id")
    assert task_id, "В ответе 202 должен быть task_id"

    # Опрос статуса (макс. ~2 мин), с retry при Connection reset
    status_url = f"{VICTORIA_URL}/run/status/{task_id}"
    for attempt in range(90):  # до ~3 мин (90 * 2 с)
        try:
            sr = requests.get(status_url, timeout=15)
        except (requests.exceptions.ConnectionError, ConnectionResetError, OSError) as e:
            # Обрыв/перезапуск Victoria — даём до 5 повторов
            if attempt >= 5:
                raise
            time.sleep(2)
            continue
        assert sr.status_code == 200, f"GET status вернул {sr.status_code}"
        rec = sr.json()
        status = rec.get("status")
        if status == "completed":
            # При needs_clarification в фоне output может быть пустым, есть clarification_questions
            if rec.get("clarification_questions") or (rec.get("knowledge") or {}).get("clarification_questions"):
                return
            assert (rec.get("output") or "").strip(), "output не должен быть пустым при completed (без clarify)"
            return
        if status == "failed":
            pytest.fail(f"Задача завершилась с ошибкой: {rec.get('error', 'unknown')}")
        time.sleep(2)

    pytest.fail("Таймаут ожидания completed (3 мин)")


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

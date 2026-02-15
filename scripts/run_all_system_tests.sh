#!/usr/bin/env bash
# Запуск тестов всей системы: Victoria (маршрутизация, цепочка), Veronica (делегирование),
# оркестраторы (IntegrationBridge), эксперты (expert_services). Без живых сервисов по умолчанию.
# См. docs/TESTING_FULL_SYSTEM.md
#
# Использование:
#   ./scripts/run_all_system_tests.sh                    # unit + быстрые (98 тестов)
#   RUN_INTEGRATION=1 ./scripts/run_all_system_tests.sh   # + интеграционные (live Victoria/Veronica)
#   RUN_WITH_DB=1 ./scripts/run_all_system_tests.sh      # + тесты с БД/Redis (e2e, knowledge_graph, load, …)

set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

# Предпочитаем venv с pytest (knowledge_os/.venv или backend/.venv), иначе python3 -m pytest / pytest
if [ -x "${REPO_ROOT}/knowledge_os/.venv/bin/python" ] && "${REPO_ROOT}/knowledge_os/.venv/bin/python" -m pytest --version >/dev/null 2>&1; then
    PYTHON="${REPO_ROOT}/knowledge_os/.venv/bin/python"
elif [ -x "${REPO_ROOT}/backend/.venv/bin/python" ] && "${REPO_ROOT}/backend/.venv/bin/python" -m pytest --version >/dev/null 2>&1; then
    PYTHON="${REPO_ROOT}/backend/.venv/bin/python"
else
    PYTHON=""
fi

echo "=== Системные тесты (Victoria, Veronica, оркестраторы, эксперты) ==="
echo "   Репозиторий: $REPO_ROOT"
echo ""

# 1) Backend: маршрутизация, делегирование Veronica (mock), стратегический классификатор, план-кэш, RAG, метрики
echo "--- Backend tests ---"
if [ -n "$PYTHON" ]; then
    "$PYTHON" -m pytest backend/app/tests/ -q --tb=short || true
elif python3 -m pytest backend/app/tests/ -q --tb=short 2>/dev/null; then
    true
else
    pytest backend/app/tests/ -q --tb=short 2>/dev/null || true
fi
echo ""

# 2) Knowledge OS: Victoria Enhanced, Veronica-цепочка, expert_services, IntegrationBridge, department_heads (unit без БД/Redis)
echo "--- Knowledge OS tests (Victoria, эксперты, оркестратор, skills) ---"
export PYTHONPATH="${REPO_ROOT}/knowledge_os:${REPO_ROOT}:${PYTHONPATH}"
KO_TESTS="tests/test_expert_services.py tests/test_integration_bridge.py tests/test_victoria_chat_and_request.py tests/test_chain_department_heads.py tests/test_skill_registry.py tests/test_skill_loader.py tests/test_skill_discovery.py tests/test_hierarchical_orchestration.py tests/test_security.py tests/test_json_fast_http_client.py tests/test_reasoning_logic_recap.py"
if [ -d "knowledge_os" ]; then
    if [ -n "$PYTHON" ]; then
        (cd knowledge_os && PYTHONPATH=".:${REPO_ROOT}:${PYTHONPATH}" "$PYTHON" -m pytest $KO_TESTS -q --tb=short -m "not integration and not slow") || true
    else
        (cd knowledge_os && PYTHONPATH=".:${REPO_ROOT}:${PYTHONPATH}" python3 -m pytest $KO_TESTS -q --tb=short 2>/dev/null) || \
        (cd knowledge_os && PYTHONPATH=".:${REPO_ROOT}:${PYTHONPATH}" pytest $KO_TESTS -q --tb=short 2>/dev/null) || true
    fi
fi
echo ""

# 3) Интеграционные — живая Victoria (8010), опционально Veronica/БД (только при RUN_INTEGRATION=1)
# Лёгкая цель «Привет»; тесты используют async+poll (без долгого sync-соединения).
if [ "${RUN_INTEGRATION}" = "1" ]; then
    echo "--- Integration tests (Victoria/Veronica/БД должны быть запущены) ---"
    export LIVE_CHAIN_GOAL="${LIVE_CHAIN_GOAL:-Привет}"
    export LIVE_CHAIN_POLL_TIMEOUT="${LIVE_CHAIN_POLL_TIMEOUT:-300}"
    if [ -n "$PYTHON" ]; then
        (cd knowledge_os && PYTHONPATH=".:${REPO_ROOT}:${PYTHONPATH}" "$PYTHON" -m pytest tests/ -v --tb=short -m "integration") || true
    else
        (cd knowledge_os && PYTHONPATH=".:${REPO_ROOT}:${PYTHONPATH}" python3 -m pytest tests/ -v --tb=short -m "integration") || true
    fi
fi

# 4) Тесты с БД/Redis/инфра — e2e, knowledge_graph, load, performance_optimizer, file_watcher, rest_api (только при RUN_WITH_DB=1)
if [ "${RUN_WITH_DB}" = "1" ]; then
    echo "--- Knowledge OS tests (требуют БД/Redis): e2e, knowledge_graph, load, performance_optimizer, file_watcher, rest_api ---"
    # С хоста Redis в Docker на порту 6381 (см. knowledge_os/docker-compose: 6381:6379)
    export REDIS_URL="${REDIS_URL:-redis://localhost:6381}"
    export DATABASE_URL="${DATABASE_URL:-postgresql://admin:secret@localhost:5432/knowledge_os}"
    (cd knowledge_os && PYTHONPATH=".:${REPO_ROOT}:${PYTHONPATH}" REDIS_URL="${REDIS_URL}" DATABASE_URL="${DATABASE_URL}" python3 -m pytest tests/test_e2e.py tests/test_knowledge_graph.py tests/test_load.py tests/test_performance_optimizer.py tests/test_file_watcher.py tests/test_rest_api.py tests/test_service_monitor.py -v --tb=short 2>/dev/null) || true
fi

echo ""
echo "=== Готово. Полный план: docs/TESTING_FULL_SYSTEM.md ==="

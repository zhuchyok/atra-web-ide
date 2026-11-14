#!/bin/bash
# Проверка Prometheus метрик (День 5)
# Запуск: ./scripts/check_prometheus.sh

set -euo pipefail
FAIL=0

echo "📊 Проверка Prometheus метрик (День 5)"

# 1. Проверяем, что бэкенд запущен
echo "1. Проверка health:"
curl -sf http://localhost:8080/health || { echo "❌ Backend not running on 8080"; exit 1; }
echo ""

# 2. Проверяем эндпоинт метрик
echo "2. Проверка /metrics:"
metrics_payload="$(curl -sf http://localhost:8080/metrics)"
printf '%s\n' "$metrics_payload" | head -30
echo ""

# 3. Проверяем сводку метрик
echo "3. Проверка /metrics/summary:"
curl -sf http://localhost:8080/metrics/summary | python3 -m json.tool 2>/dev/null || curl -s http://localhost:8080/metrics/summary
echo ""

# 4. Запускаем тесты
echo "4. Запуск тестов метрик:"
cd "$(dirname "$0")/../backend"
if python -c "import pytest" >/dev/null 2>&1; then
  python -m pytest app/tests/test_prometheus_metrics.py -v --tb=short || FAIL=1
else
  echo "⚠️  pytest not run (install: pip install pytest pytest-asyncio)"
  if [ "${REQUIRE_PROM_TESTS:-false}" = "true" ]; then
    FAIL=1
  fi
fi
echo ""

# 5. Проверяем Prometheus — live :9091 only (legacy :9090 warn-only)
echo "5. Проверка Prometheus targets:"
if curl -sf http://localhost:9091/api/v1/targets 2>/dev/null | grep -qE '"health":"(up|UP)"'; then
    echo "✅ Prometheus (live) on :9091 — targets UP"
elif curl -sf http://localhost:9091/api/v1/targets 2>/dev/null | grep -q "activeTargets"; then
    echo "✅ Prometheus (live) running on :9091 (targets: check UI)"
else
    echo "❌ Prometheus not healthy on :9091"
    FAIL=1
    if [ "${CHECK_LEGACY_MONITORING:-false}" = "true" ]; then
      if curl -sf http://localhost:9090/api/v1/targets 2>/dev/null | grep -q "activeTargets"; then
        echo "⚠️  Legacy Prometheus :9090 up (not counted as live pass)"
      fi
    fi
fi

# 6. Проверяем Grafana — live :3002 only
echo "6. Проверка Grafana:"
if curl -sf http://localhost:3002/api/health 2>/dev/null | grep -q "ok\|database"; then
    echo "✅ Grafana running on :3002"
else
    echo "❌ Grafana not healthy on :3002"
    FAIL=1
    if [ "${CHECK_LEGACY_MONITORING:-false}" = "true" ]; then
      if curl -sf http://localhost:3001/api/health 2>/dev/null | grep -q "ok\|database"; then
        echo "⚠️  Legacy Grafana :3001 up (not counted as live pass)"
      fi
    fi
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
  echo "✅ Проверка завершена"
else
  echo "⚠️ Проверка завершена С ОШИБКАМИ"
fi
exit "$FAIL"

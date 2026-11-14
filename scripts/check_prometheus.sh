#!/bin/bash
# Проверка Prometheus метрик (День 5)
# Запуск: ./scripts/check_prometheus.sh

set -euo pipefail

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
  python -m pytest app/tests/test_prometheus_metrics.py -v --tb=short
else
  echo "⚠️  pytest not run (install: pip install pytest pytest-asyncio)"
fi
echo ""

# 5. Проверяем Prometheus (если запущен; наш — порт 9091)
echo "5. Проверка Prometheus targets:"
if curl -sf http://localhost:9091/api/v1/targets 2>/dev/null | grep -qE '"health":"(up|UP)"'; then
    echo "✅ Prometheus (atra-web-ide) on :9091 — targets UP"
elif curl -sf http://localhost:9091/api/v1/targets 2>/dev/null | grep -q "activeTargets"; then
    echo "✅ Prometheus (atra-web-ide) running on :9091 (targets: check UI)"
elif curl -sf http://localhost:9090/api/v1/targets 2>/dev/null | grep -q "activeTargets"; then
    echo "✅ Prometheus running on :9090"
else
    echo "⚠️  Prometheus not running (docker-compose up -d prometheus, порт 9091)"
fi

# 6. Проверяем Grafana (если запущена; live host :3002)
echo "6. Проверка Grafana:"
if curl -sf http://localhost:3002/api/health 2>/dev/null | grep -q "ok"; then
    echo "✅ Grafana running on :3002"
elif curl -sf http://localhost:3001/api/health 2>/dev/null | grep -q "ok"; then
    echo "✅ Grafana running on :3001 (legacy)"
else
    echo "⚠️  Grafana not running (docker-compose up -d grafana). Port 3002 (frontend on 3000)."
fi

echo ""
echo "✅ Проверка завершена"

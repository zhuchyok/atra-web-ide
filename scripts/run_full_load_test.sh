#!/bin/bash
# Полный прогон: при необходимости поднять сервисы → стресс-тест → отчёт
# Использование:
#   ./scripts/run_full_load_test.sh
#   START_DOCKER=1 ./scripts/run_full_load_test.sh   # поднять Docker перед тестом

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

HOST="${HOST:-http://localhost:8080}"
USERS="${USERS:-50}"
SPAWN_RATE="${SPAWN_RATE:-10}"
RUN_TIME="${RUN_TIME:-2m}"
OUT_DIR="${OUT_DIR:-$REPO_ROOT/scripts/load_test/out}"
START_DOCKER="${START_DOCKER:-0}"
WAIT_MAX="${WAIT_MAX:-120}"

echo "🚀 Полный прогон стресс-теста ATRA Web IDE"
echo "   Host: $HOST"
echo "   Users: $USERS, Spawn: $SPAWN_RATE, Time: $RUN_TIME"
echo ""

# 1. При необходимости поднять Docker
if [ "$START_DOCKER" = "1" ]; then
  echo "1. Запуск Knowledge OS (агенты, БД, Redis)..."
  docker-compose -f knowledge_os/docker-compose.yml up -d
  echo "   Ожидание 15 сек..."
  sleep 15
  echo "2. Запуск Web IDE (backend, frontend)..."
  docker-compose up -d
  echo "   Ожидание 10 сек..."
  sleep 10
else
  echo "1. Docker не запускаем (START_DOCKER=0). Проверяем backend..."
fi

# 2. Ожидание готовности backend
echo ""
echo "2. Ожидание backend ($HOST)..."
waited=0
while [ "$waited" -lt "$WAIT_MAX" ]; do
  if curl -sf --connect-timeout 5 "$HOST/health" >/dev/null 2>&1; then
    echo "   Backend готов (через ${waited} сек)"
    break
  fi
  sleep 5
  waited=$((waited + 5))
  echo "   ... ещё ${waited} сек"
done
if [ "$waited" -ge "$WAIT_MAX" ]; then
  echo "❌ Backend не ответил за ${WAIT_MAX} сек. Запустите: docker-compose up -d"
  exit 1
fi

# 3. Стресс-тест (существующий скрипт)
echo ""
export HOST USERS SPAWN_RATE RUN_TIME OUT_DIR
"$REPO_ROOT/scripts/run_load_test.sh"

# 4. Итог
echo ""
echo "📊 Отчёт: $OUT_DIR/load_test_report.html"
echo "   Открыть: open $OUT_DIR/load_test_report.html"
echo "   Метрики: $HOST/metrics/summary (если включён Prometheus)"
echo ""
echo "✅ Готово"

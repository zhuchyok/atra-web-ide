#!/bin/bash
# Полный запуск: db -> api, worker -> Victoria, Veronica. Запускать из корня репо.

set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
COMPOSE="docker-compose -f knowledge_os/docker-compose.yml"
LOG="$HOME/migration/run_all_agents.log"

mkdir -p "$(dirname "$LOG")"
exec > >(tee -a "$LOG") 2>&1

echo "=============================================="
echo "Victoria & Veronica — полный запуск"
echo "=============================================="
echo "Лог: $LOG"
echo ""

# 1. Docker (таймаут 10 с)
echo "[1/5] Проверка Docker..."
if ! ( perl -e 'alarm 10; exec @ARGV' - docker info >/dev/null 2>&1 ) 2>/dev/null; then
  echo "Ошибка: Docker не запущен или не отвечает. Запустите Docker Desktop."
  exit 1
fi
echo "      OK"

# 2. db
echo ""
echo "[2/5] Запуск db (фоново, ожидание 90 с)..."
$COMPOSE up -d db > /tmp/run_all_db.log 2>&1 &
sleep 90
if ( perl -e 'alarm 5; exec @ARGV' - docker exec knowledge_os_db pg_isready -U admin -d knowledge_os 2>/dev/null ) 2>/dev/null; then
  echo "      db готов."
else
  echo "      db не ответил за 90 с, продолжаем. Лог: /tmp/run_all_db.log"
fi

# 3. api, worker (фоново, 60 с)
echo ""
echo "[3/5] Запуск api, worker (фоново, ожидание 60 с)..."
$COMPOSE up -d api worker > /tmp/run_all_api.log 2>&1 &
sleep 60
echo "      Продолжаем."

# 4. Сборка и запуск агентов
echo ""
echo "[4/5] Сборка Victoria, Veronica..."
$COMPOSE build victoria-agent veronica-agent

echo ""
echo "[4/5] Запуск Victoria, Veronica..."
$COMPOSE up -d victoria-agent veronica-agent

# 5. Проверка
echo ""
echo "[5/5] Ожидание 20 с, проверка..."
sleep 20
bash "$ROOT/scripts/migration/verify_agents.sh" || true

echo ""
echo "Готово. Victoria: http://localhost:8010  Veronica: http://localhost:8011"
echo "API: http://localhost:8000  MLX: localhost:11434"

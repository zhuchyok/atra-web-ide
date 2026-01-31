#!/bin/bash
# Запуск Victoria и Veronica после старта Docker.
# Запускать из корня репо: bash scripts/migration/up_agents_after_docker.sh

set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
COMPOSE="docker-compose -f knowledge_os/docker-compose.yml"

echo "=============================================="
echo "Victoria & Veronica — сборка и запуск"
echo "=============================================="

# Ждём Docker (до 60 сек), если не SKIP_DOCKER_WAIT=1
if [ "${SKIP_DOCKER_WAIT}" != "1" ]; then
  for i in $(seq 1 20); do
    if ( perl -e 'alarm 8; exec @ARGV' - docker info >/dev/null 2>&1 ) 2>/dev/null; then
      echo "Docker готов."
      break
    fi
    if [ $i -eq 20 ]; then
      echo "Ошибка: Docker не отвечает. Запустите Docker Desktop и повторите."
      exit 1
    fi
    echo "Ожидание Docker... ($i/20)"
    sleep 3
  done
else
  ( perl -e 'alarm 8; exec @ARGV' - docker info >/dev/null 2>&1 ) 2>/dev/null || { echo "Docker не запущен или не отвечает. Запустите Docker Desktop."; exit 1; }
  echo "Docker готов (SKIP_DOCKER_WAIT)."
fi

# Поднимаем стек (db, api, worker) в фоне — первый раз может занять 5–10 мин
echo ""
echo "[1/4] Стек Knowledge OS (db, api, worker)... $(date -u +%H:%M:%S)"
echo "      Ожидание до 10 мин (сборка api/worker при первом запуске)..."
$COMPOSE up -d db api worker > /tmp/up_agents_compose1.log 2>&1 &
CPID=$!
WAIT=600
ELAPSED=0
TIMEDOUT=0
while kill -0 $CPID 2>/dev/null && [ $ELAPSED -lt $WAIT ]; do
  sleep 30
  ELAPSED=$((ELAPSED + 30))
  echo "      ... ${ELAPSED} с"
done
[ $ELAPSED -ge $WAIT ] && kill -0 $CPID 2>/dev/null && TIMEDOUT=1
[ $TIMEDOUT -eq 1 ] && echo "      Таймаут 10 мин, продолжаем." && kill $CPID 2>/dev/null || true
wait $CPID 2>/dev/null || true
echo "[1/4] Готово. $(date -u +%H:%M:%S)"
echo "      Лог шага 1: tail -50 /tmp/up_agents_compose1.log"
sleep 5

# Сборка агентов (--no-cache при первом запуске)
echo ""
echo "[2/4] Сборка Victoria и Veronica... $(date -u +%H:%M:%S)"
$COMPOSE build --no-cache victoria-agent veronica-agent 2>&1 || { echo "[2/4] Ошибка сборки."; exit 1; }
echo "[2/4] Готово. $(date -u +%H:%M:%S)"

# Запуск агентов
echo ""
echo "[3/4] Запуск агентов... $(date -u +%H:%M:%S)"
$COMPOSE up -d victoria-agent veronica-agent 2>&1 || { echo "[3/4] Ошибка."; exit 1; }
echo "[3/4] Готово. $(date -u +%H:%M:%S)"

echo ""
echo "[4/4] Проверка (ожидание 30 с)... $(date -u +%H:%M:%S)"
sleep 30
v=0; bash "$ROOT/scripts/migration/verify_agents.sh" || v=$?
if [ $v -ne 0 ]; then
  echo "Повторная проверка через 20 с..."
  sleep 20
  bash "$ROOT/scripts/migration/verify_agents.sh" || v=$?
fi

if [ $v -ne 0 ]; then
  echo ""
  echo "--- Диагностика ---"
  bash "$ROOT/scripts/migration/docker_debug.sh" 2>&1 || true
fi

echo ""
echo "Готово. Victoria: http://localhost:8010  Veronica: http://localhost:8011"
echo "MLX/Ollama должен быть на localhost:11434."
echo "При сбое: docker logs victoria-agent; docker logs veronica-agent"

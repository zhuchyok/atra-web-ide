#!/bin/bash
# Всё сам: подъём стека + агенты + проверка. Запускать на Mac Studio из корня репо.
# Лог: ~/migration/do_all_verify.log

set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
COMPOSE="docker-compose -f knowledge_os/docker-compose.yml"
LOG="${HOME}/migration/do_all_verify.log"
mkdir -p "$(dirname "$LOG")"

log() { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== Старт ==="
log ""

# 1. Docker (таймаут 10 с)
log "[1/5] Docker..."
if ! ( perl -e 'alarm 10; exec @ARGV' - docker info >/dev/null 2>&1 ) 2>/dev/null; then
  log "Ошибка: Docker не запущен или не отвечает."
  exit 1
fi
log "OK"

# 2. db, api, worker
log ""
log "[2/5] db, api, worker..."
$COMPOSE up -d db api worker 2>&1 | tee -a "$LOG" || true
log "Ожидание 90 с..."
sleep 90
log "OK"

# 3. Агенты
log ""
log "[3/5] Victoria, Veronica..."
$COMPOSE up -d victoria-agent veronica-agent 2>&1 | tee -a "$LOG" || true
log "Ожидание 30 с..."
sleep 30
log "OK"

# 4. Проверка
log ""
log "[4/5] Проверка..."
if bash "$ROOT/scripts/migration/verify_agents.sh" 2>&1 | tee -a "$LOG"; then
  log ""
  log "[5/5] Всё OK. Victoria:8010  Veronica:8011"
  exit 0
fi

log ""
log "[5/5] Проверка не прошла. Логи: docker logs victoria-agent; docker logs veronica-agent"
log "Полный лог: $LOG"
exit 1

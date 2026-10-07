#!/bin/bash
# [v149.25] Redis-сторож: смерть Redis (OOM-137) стояла весь конвейер 20ч молча.
# Проверка изнутри оркестратора (тот же путь, что у диспетчера) + автоподъём + ntfy.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

# [v149.34] MAINTENANCE MODE: при ручных операциях с инфраструктурой все
# автоматические акторы молчат (файл-флаг ставит scripts/maintenance.sh).
if [ -f /tmp/atra_maintenance_mode ]; then echo "$(date '+%F %T') maintenance mode — skip"; exit 0; fi
R=$(docker exec knowledge_os_orchestrator python3 -c "
import socket
s = socket.socket(socket.AF_UNIX)
try:
    s.connect('/data/redis/redis.sock'); print('OK')
except Exception:
    print('DEAD')
s.close()" 2>/dev/null)
if [ "$R" != "OK" ]; then
  echo "$(date '+%F %T') redis DEAD — recreate" >> "$HOME/Library/Logs/atra/redis_watchdog.log"
  docker rm -f knowledge_os_redis 2>/dev/null
  cd /Users/bikos/Documents/atra-web-ide/knowledge_os && docker compose -f docker-compose.yml -f docker-compose.agents.yml up -d redis 2>&1 | tail -1 >> "$HOME/Library/Logs/atra/redis_watchdog.log"
  sleep 8
  curl -s -m 8 -H "Title: 🔴 Redis умер — поднят сторожем" -H "Priority: high" -d "Redis был недоступен (конвейер экспертов стоял). Контейнер пересоздан автоматически." "https://ntfy.sh/atra_victoria_curator" >/dev/null 2>&1
else
  echo "$(date '+%F %T') redis OK" >> "$HOME/Library/Logs/atra/redis_watchdog.log"
fi

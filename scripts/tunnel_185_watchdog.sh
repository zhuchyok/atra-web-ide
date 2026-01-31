#!/bin/bash
# Watchdog: проверяет доступность http://185.177.216.15:3002
# Если недоступен — убивает туннель, launchd перезапустит его

URL="http://185.177.216.15:3002"
TIMEOUT=10
LOG="/tmp/atra-tunnel-185-watchdog.log"

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') $1" >> "$LOG"
}

# Проверяем доступность 185:3002
if curl -sf --connect-timeout "$TIMEOUT" "$URL" >/dev/null 2>&1; then
    # Всё ок
    exit 0
fi

# Недоступен — убиваем туннель (launchd перезапустит)
log "⚠️ $URL недоступен, перезапуск туннеля..."
pkill -f "ssh.*185.177.216.15.*3002" 2>/dev/null
if [ $? -eq 0 ]; then
    log "✅ Туннель остановлен, launchd перезапустит через несколько секунд"
else
    log "ℹ️ Процесс туннеля не найден (возможно уже перезапускается)"
fi
exit 0

#!/bin/bash
# Ollama Runner Watchdog
# Убивает ollama runner процессы застрявшие в "Stopping..." >45 секунд.
# Запускается каждые 60 секунд через LaunchAgent com.atra.ollama-watchdog.plist.

OLLAMA_URL="http://localhost:11434"
WATCHDOG_TIMEOUT=45  # секунд — через сколько убивать Stopping/expired runner

log() { echo "[$(date '+%H:%M:%S')] [OLLAMA-WATCHDOG] $*"; }

# Получаем модели в состоянии Stopping (expires_at=0001-01-01) ИЛИ с истёкшим TTL
stuck_models=$(curl -s --max-time 3 "${OLLAMA_URL}/api/ps" | python3 -c "
import sys, json
from datetime import datetime, timezone
try:
    data = json.load(sys.stdin)
    now = datetime.now(timezone.utc)
    for m in data.get('models', []):
        name = m.get('name', '')
        expires = m.get('expires_at', '')
        if not expires:
            continue
        # expires_at='0001-01-01...' означает Stopping... в ollama ps
        if expires.startswith('0001'):
            print(name)
            continue
        try:
            exp = datetime.fromisoformat(expires.replace('Z', '+00:00'))
            if exp.utcoffset() is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp.astimezone(timezone.utc) < now:
                print(name)
        except Exception:
            pass
except:
    pass
" 2>/dev/null)

if [ -z "$stuck_models" ]; then
    log "Нет застрявших моделей"
    exit 0
fi

log "Застрявшие модели (Stopping/expired): $stuck_models"

# Убиваем runner процессы с достаточным временем жизни и памятью
runner_pids=$(ps aux | grep "ollama runner" | grep -v grep | awk '{print $2}')

if [ -z "$runner_pids" ]; then
    log "Runner процессы не найдены"
    exit 0
fi

for pid in $runner_pids; do
    etime=$(ps -p "$pid" -o etime= 2>/dev/null | tr -d ' ')
    if [ -z "$etime" ]; then continue; fi

    total_secs=0
    if echo "$etime" | grep -q "-"; then
        days=$(echo "$etime" | cut -d- -f1)
        rest=$(echo "$etime" | cut -d- -f2)
        total_secs=$((days * 86400))
        etime="$rest"
    fi
    IFS=: read -r h m s <<< "$etime"
    if [ -n "$s" ]; then
        total_secs=$((total_secs + 10#${h:-0} * 3600 + 10#${m:-0} * 60 + 10#${s:-0}))
    else
        total_secs=$((total_secs + 10#${h:-0} * 60 + 10#${m:-0}))
    fi

    mem_pct=$(ps -p "$pid" -o pmem= 2>/dev/null | tr -d ' ')
    mem_int=${mem_pct%.*}

    if [ "$total_secs" -gt "$WATCHDOG_TIMEOUT" ] && [ "${mem_int:-0}" -gt "5" ]; then
        log "KILL: pid=$pid uptime=${total_secs}s mem=${mem_pct}% (stuck Stopping runner)"
        kill -9 "$pid" 2>/dev/null && log "Killed pid=$pid" || log "Failed to kill pid=$pid"
    else
        log "OK: pid=$pid uptime=${total_secs}s mem=${mem_pct}% (threshold=${WATCHDOG_TIMEOUT}s, minmem=5%)"
    fi
done

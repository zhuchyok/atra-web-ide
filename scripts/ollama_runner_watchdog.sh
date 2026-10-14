#!/bin/bash
# Ollama Runner Watchdog
# Убивает ollama runner процессы застрявшие в "Stopping..." >45 секунд.
# Запускается каждые 60 секунд через LaunchAgent com.atra.ollama-watchdog.plist.
# [v150.9] Следит за ОБЕИМИ инстансами: 11434 (мозг) и 11437 (руки).

WATCHDOG_TIMEOUT=45  # секунд — через сколько убивать Stopping/expired runner

log() { echo "[$(date '+%H:%M:%S')] [OLLAMA-WATCHDOG] $*"; }

# [v150.3] ollama 0.33 переименовал раннеры: было «ollama runner», стало
# «llama-server». Старый паттерн НИКОГДА не матчился → застрявшие в Stopping
# раннеры висели часами и блокировали планировщик (503-патология загрузок).

for PORT in 11434 11437; do
    OLLAMA_URL="http://localhost:${PORT}"

    # Модели в состоянии Stopping (expires_at=0001-01-01) ИЛИ с истёкшим TTL
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
except Exception:
    pass
" 2>/dev/null)

    if [ -z "$stuck_models" ]; then
        log "Нет застрявших моделей (:$PORT)"
        continue
    fi

    log "Застрявшие модели (Stopping/expired, :$PORT): $stuck_models"

    MAIN_PID=$(lsof -nP -tiTCP:$PORT -sTCP:LISTEN 2>/dev/null | head -1)
    if [ -z "$MAIN_PID" ]; then
        log "Инстанс :$PORT не найден — пропускаем"
        continue
    fi

    runner_pids=$(pgrep -P "$MAIN_PID" -f llama-server 2>/dev/null)
    if [ -z "$runner_pids" ]; then
        log "Runner процессы не найдены (:$PORT)"
        continue
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

        # [v150.12] mem>5% убран из условия: застрявший в Stopping раннер при
        # разгрузке теряет RSS → сторож проходил мимо (мозг висел 15+ минут).
        if [ "$total_secs" -gt "$WATCHDOG_TIMEOUT" ]; then
            log "KILL :$PORT pid=$pid uptime=${total_secs}s mem=${mem_pct}% (stuck Stopping runner)"
            kill -9 "$pid" 2>/dev/null && log "Killed pid=$pid" || log "Failed to kill pid=$pid"
        else
            log "OK :$PORT pid=$pid uptime=${total_secs}s mem=${mem_pct}%"
        fi
    done
done  # [v150.9] цикл по инстансам 11434, 11437

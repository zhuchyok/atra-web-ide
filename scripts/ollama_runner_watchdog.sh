#!/bin/bash
# Ollama Runner Watchdog
# Убивает ollama runner процессы застрявшие в "Stopping..." >45 секунд.
# Запускается каждые 60 секунд через LaunchAgent com.atra.ollama-watchdog.plist.
# [v150.9] Следит за ОБЕИМИ инстансами: 11434 (мозг) и 11437 (руки).

export PATH="/opt/homebrew/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"
WATCHDOG_TIMEOUT=45  # секунд — через сколько убивать Stopping/expired runner

log() { echo "[$(date '+%H:%M:%S')] [OLLAMA-WATCHDOG] $*"; }

# [v150.3] ollama 0.33 переименовал раннеры: было «ollama runner», стало
# «llama-server». Старый паттерн НИКОГДА не матчился → застрявшие в Stopping
# раннеры висели часами и блокировали планировщик (503-патология загрузок).

for PORT in 11434 11437; do
    OLLAMA_URL="http://localhost:${PORT}"

    MAIN_PID=$(lsof -nP -tiTCP:$PORT -sTCP:LISTEN 2>/dev/null | head -1)

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


    if [ -z "$MAIN_PID" ]; then
        log "Инстанс :$PORT не найден — пропускаем"
        continue
    fi

    # [v150.22] Доп.сигнал: zombie-раннер — живёт >30 мин при CPU<1% и нулевой работе
    # (phi@11437 22.10: часы в Stopping без признака expires_at=0001, 503 всем)
    for pid in $(pgrep -P "$MAIN_PID" -f llama-server 2>/dev/null); do
        _cpu=$(ps -p "$pid" -o %cpu= 2>/dev/null | tr -d ' ' | cut -d. -f1)
        # etime форматы: MM:SS / HH:MM:SS / DD-HH:MM:SS — часы = два двоеточия или дефис
        _et=$(ps -p "$pid" -o etime= 2>/dev/null | tr -d ' ')
        _hrs=$(echo "$_et" | awk -F'[:-]' '{if (NF>=3) print 1; else print 0}')
        if [ "${_cpu:-0}" -lt 1 ] && [ "$_hrs" = "1" ]; then
            log "ZOMBIE :$PORT pid=$pid (CPU=${_cpu}%, uptime>1h) — kill"
            kill -9 "$pid" 2>/dev/null && log "Zombie killed pid=$pid"
        fi
    done

    # [v150.25b] Универсальная 503-проба (случай 25.10 19:44: раннер жив,
    # но очередь орфанена — старый детект смотрел только при 0 runner).
    _probe_model="phi3.5:3.8b-stable"
    [ "$PORT" = "11434" ] && _probe_model="victoria-qwen38:latest"
    _probe=$(curl -s --max-time 8 -o /dev/null -w '%{http_code}' \
        -X POST "http://localhost:${PORT}/api/generate" \
        -H 'Content-Type: application/json' \
        -d '{"model":"'"$_probe_model"'","prompt":"ok","stream":false,"options":{"num_predict":1,"num_ctx":2048}}' 2>/dev/null)
    if [ "$_probe" = "503" ]; then
        log "ORPHAN-QUEUE :$PORT — 503 (runners: $(pgrep -P "$MAIN_PID" -f llama-server 2>/dev/null | wc -l | tr -d ' ')), сброс serve"
        launchctl kickstart -k "gui/$(id -u)/$([ "$PORT" = "11434" ] && echo homebrew.mxcl.ollama || echo com.atra.ollama-hands)" 2>/dev/null \
            || kill -HUP "$MAIN_PID" 2>/dev/null
        log "ORPHAN-QUEUE :$PORT — serve сброшен"
        continue
    fi

    if [ -z "$stuck_models" ]; then
        log "Нет застрявших моделей (:$PORT)"
        continue
    fi

    log "Застрявшие модели (Stopping/expired, :$PORT): $stuck_models"


    runner_pids=$(pgrep -P "$MAIN_PID" -f llama-server 2>/dev/null)
    if [ -z "$runner_pids" ]; then
        # [v150.25] ОРФАН-ОЧЕРЕДЬ (ночь 24.10: 3117×503 за 12ч): runner умер
        # внутри serve (баг 0.33), очередь ожиданий не очистилась → вечный 503,
        # но сторожу нечего ловить — процессов-то нет. Детект: запрос generate
        # получает 503 при живом serve → орочим очередь рестартом serve.
        _probe=$(curl -s --max-time 5 -o /dev/null -w '%{http_code}'             -X POST "http://localhost:${PORT}/api/generate"             -H 'Content-Type: application/json'             -d '{"model":"'"$([ "$PORT" = "11434" ] && echo victoria-qwen38:latest || echo phi3.5:3.8b-stable)"'","prompt":"ok","stream":false,"options":{"num_predict":1,"num_ctx":2048}}' 2>/dev/null)
        if [ "$_probe" = "503" ]; then
            log "ORPHAN-QUEUE :$PORT — 503 без раннеров, сброс serve (pid=$MAIN_PID)"
            launchctl kickstart -k "gui/$(id -u)/$([ "$PORT" = "11434" ] && echo homebrew.mxcl.ollama || echo com.atra.ollama-hands)" 2>/dev/null                 || kill -HUP "$MAIN_PID" 2>/dev/null
            log "ORPHAN-QUEUE :$PORT — serve сброшен, очередь очищена"
        else
            log "Нет раннеров (:$PORT), проба=$_probe — инстанс спокоен"
        fi
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

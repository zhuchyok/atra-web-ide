#!/bin/bash
# Ollama Runner Watchdog
# Убивает ollama runner процессы застрявшие в "Stopping..." >45 секунд.
# Запускается каждые 60 секунд через LaunchAgent com.atra.ollama-watchdog.plist.
# [v150.9] Следит за ОБЕИМИ инстансами: 11434 (мозг) и 11437 (руки).

export PATH="/opt/homebrew/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH"
WATCHDOG_TIMEOUT=45  # секунд — через сколько убивать Stopping/expired runner

log() { echo "[$(date '+%H:%M:%S')] [OLLAMA-WATCHDOG] $*"; }
STATE_DIR="/tmp/atra_runtime_state"
BRAIN_NOT_READY_FLAG="${STATE_DIR}/brain_11434_not_ready"
METRICS_DIR="${ATRA_METRICS_DIR:-/tmp/atra_metrics}"
METRICS_FILE="${METRICS_DIR}/ollama_watchdog.prom"
TIMEOUT_LIVE_COUNTER_FILE="${STATE_DIR}/wd_generate_timeout_but_live_total"
mkdir -p "$STATE_DIR" 2>/dev/null || true
mkdir -p "$METRICS_DIR" 2>/dev/null || true

# [v150.31b] Anti-storm hysteresis knobs:
# - Do not restart on first transient probe timeout.
# - Require N consecutive probe failures + cooldown window.
# - Apply startup grace after restart/warmup to avoid immediate self-restart loops.
PROBE_FAILS_BEFORE_RESTART="${OLLAMA_WD_PROBE_FAILS_BEFORE_RESTART:-3}"
PROBE_RESTART_COOLDOWN_SEC="${OLLAMA_WD_PROBE_RESTART_COOLDOWN_SEC:-300}"
PROBE_STARTUP_GRACE_SEC="${OLLAMA_WD_PROBE_STARTUP_GRACE_SEC:-180}"
BRAIN_PROBE_EVERY_SEC="${OLLAMA_WD_BRAIN_PROBE_EVERY_SEC:-180}"
HANDS_PROBE_EVERY_SEC="${OLLAMA_WD_HANDS_PROBE_EVERY_SEC:-60}"
PROBE_TIMEOUT_SEC_BRAIN="${OLLAMA_WD_PROBE_TIMEOUT_SEC_BRAIN:-25}"
PROBE_TIMEOUT_SEC_HANDS="${OLLAMA_WD_PROBE_TIMEOUT_SEC_HANDS:-20}"

state_get() {
    local key="$1"
    local file="${STATE_DIR}/${key}"
    [ -f "$file" ] && cat "$file" 2>/dev/null || echo ""
}

state_set() {
    local key="$1"
    local val="$2"
    echo "$val" > "${STATE_DIR}/${key}"
}

counter_get() {
    local file="$1"
    [ -f "$file" ] && cat "$file" 2>/dev/null || echo "0"
}

counter_inc() {
    local file="$1"
    local val
    val="$(counter_get "$file")"
    [ -z "$val" ] && val=0
    val=$((val + 1))
    echo "$val" > "$file"
    echo "$val"
}

write_prom_metrics() {
    local now
    now="$(date +%s)"
    local timeout_live_total
    timeout_live_total="$(counter_get "$TIMEOUT_LIVE_COUNTER_FILE")"
    local fail_11434 fail_11437
    fail_11434="$(state_get "wd_probe_fail_11434")"
    fail_11437="$(state_get "wd_probe_fail_11437")"
    [ -z "$fail_11434" ] && fail_11434=0
    [ -z "$fail_11437" ] && fail_11437=0
    cat > "$METRICS_FILE" <<EOF
# HELP atra_ollama_generate_timeout_but_live_total Generate probe timed out but lightweight liveness endpoint confirmed the service was up.
# TYPE atra_ollama_generate_timeout_but_live_total counter
atra_ollama_generate_timeout_but_live_total ${timeout_live_total}
# HELP atra_ollama_watchdog_probe_failures Consecutive probe failures currently tracked by watchdog per port.
# TYPE atra_ollama_watchdog_probe_failures gauge
atra_ollama_watchdog_probe_failures{port="11434"} ${fail_11434}
atra_ollama_watchdog_probe_failures{port="11437"} ${fail_11437}
# HELP atra_ollama_watchdog_metrics_updated_unixtime Last metrics update timestamp.
# TYPE atra_ollama_watchdog_metrics_updated_unixtime gauge
atra_ollama_watchdog_metrics_updated_unixtime ${now}
EOF
}

now_ts() { date +%s; }

should_probe_now() {
    local port="$1"
    local now
    now=$(now_ts)
    local key="wd_probe_last_${port}"
    local last
    last="$(state_get "$key")"
    [ -z "$last" ] && last=0
    local every="$HANDS_PROBE_EVERY_SEC"
    [ "$port" = "11434" ] && every="$BRAIN_PROBE_EVERY_SEC"
    if [ $((now - last)) -lt "$every" ]; then
        return 1
    fi
    state_set "$key" "$now"
    return 0
}

in_startup_grace() {
    local port="$1"
    local now
    now=$(now_ts)
    local last_restart
    last_restart="$(state_get "wd_last_restart_${port}")"
    [ -z "$last_restart" ] && return 1
    [ $((now - last_restart)) -lt "$PROBE_STARTUP_GRACE_SEC" ]
}

note_probe_success() {
    local port="$1"
    state_set "wd_probe_fail_${port}" "0"
}

note_probe_failure() {
    local port="$1"
    local now
    now=$(now_ts)
    local key="wd_probe_fail_${port}"
    local n
    n="$(state_get "$key")"
    [ -z "$n" ] && n=0
    n=$((n + 1))
    state_set "$key" "$n"
    state_set "wd_probe_last_fail_${port}" "$now"
    echo "$n"
}

probe_cooldown_ok() {
    local port="$1"
    local now
    now=$(now_ts)
    local last_restart
    last_restart="$(state_get "wd_last_restart_${port}")"
    [ -z "$last_restart" ] && return 0
    [ $((now - last_restart)) -ge "$PROBE_RESTART_COOLDOWN_SEC" ]
}

should_restart_after_probe_failure() {
    local port="$1"
    local fail_count
    fail_count="$(state_get "wd_probe_fail_${port}")"
    [ -z "$fail_count" ] && fail_count=0
    if [ "$fail_count" -lt "$PROBE_FAILS_BEFORE_RESTART" ]; then
        return 1
    fi
    probe_cooldown_ok "$port"
}

probe_generate_payload() {
    # [v150.83] 11434 must not send num_ctx=2048: Ollama reloads the 27B runner
    # (native num_ctx change) and plist OLLAMA_KEEP_ALIVE=-1 then stamps expires 2319.
    local port="$1"
    local model="$2"
    if [ "$port" = "11434" ]; then
        printf '%s' '{"model":"'"$model"'","prompt":"ok","stream":false,"keep_alive":"24h","options":{"num_predict":1,"num_ctx":16384}}'
    else
        printf '%s' '{"model":"'"$model"'","prompt":"ok","stream":false,"keep_alive":-1,"options":{"num_predict":1,"num_ctx":2048}}'
    fi
}

brain_warmup_gate() {
    # [v150.30] Post-restart SLO gate for brain (11434):
    # require 2 consecutive successful micro-generations before considering
    # the serve "ready". This reduces first-request empty-reply flaps.
    local port="$1"
    [ "$port" != "11434" ] && return 0
    [ "${OLLAMA_WD_BRAIN_WARMUP:-true}" != "true" ] && return 0

    local model="${OLLAMA_WD_BRAIN_MODEL:-victoria-qwen38:latest}"
    local attempts="${OLLAMA_WD_BRAIN_WARMUP_ATTEMPTS:-4}"
    local need_ok="${OLLAMA_WD_BRAIN_WARMUP_CONSECUTIVE_OK:-2}"
    local timeout="${OLLAMA_WD_BRAIN_WARMUP_TIMEOUT_SEC:-20}"
    local streak=0

    mkdir -p "$STATE_DIR" 2>/dev/null || true
    touch "$BRAIN_NOT_READY_FLAG"
    log "BRAIN-WARMUP :$port start (model=$model attempts=$attempts need_ok=$need_ok)"
    local i=1
    while [ "$i" -le "$attempts" ]; do
        local body="/tmp/ollama_warmup_${port}.json"
        local code
        code=$(curl -s --max-time "$timeout" -o "$body" -w '%{http_code}' \
            -X POST "http://localhost:${port}/api/generate" \
            -H 'Content-Type: application/json' \
            -d "$(probe_generate_payload "$port" "$model")" 2>/dev/null)
        if [ "$code" = "200" ]; then
            streak=$((streak + 1))
            log "BRAIN-WARMUP :$port try=$i code=200 streak=$streak/$need_ok"
            if [ "$streak" -ge "$need_ok" ]; then
                rm -f "$BRAIN_NOT_READY_FLAG" 2>/dev/null || true
                log "BRAIN-WARMUP :$port ready"
                return 0
            fi
        else
            streak=0
            log "BRAIN-WARMUP :$port try=$i code=$code (streak reset)"
        fi
        i=$((i + 1))
        sleep 1
    done
    log "BRAIN-WARMUP :$port not_ready after $attempts tries"
    return 1
}

restart_serve() {
    local port="$1"
    local main_pid="$2"
    state_set "wd_last_restart_${port}" "$(now_ts)"
    launchctl kickstart -k "gui/$(id -u)/$([ "$port" = "11434" ] && echo homebrew.mxcl.ollama || echo com.atra.ollama-hands)" 2>/dev/null \
        || kill -HUP "$main_pid" 2>/dev/null
    if ! brain_warmup_gate "$port"; then
        # [v150.31] One controlled second chance for brain: if first warmup gate
        # fails, do one more restart+warmup before giving up.
        if [ "$port" = "11434" ]; then
            log "BRAIN-WARMUP :$port second_chance restart"
            launchctl kickstart -k "gui/$(id -u)/homebrew.mxcl.ollama" 2>/dev/null \
                || kill -HUP "$main_pid" 2>/dev/null
            brain_warmup_gate "$port" || true
        fi
    fi
}

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

    # [v150.31b] Throttled health probe with hysteresis/cooldown/grace:
    # avoid restart storms from transient 000/slow micro-generations.
    if should_probe_now "$PORT"; then
        _probe_model="phi3.5:3.8b-stable"
        _probe_timeout="$PROBE_TIMEOUT_SEC_HANDS"
        [ "$PORT" = "11434" ] && _probe_model="victoria-qwen38:latest" && _probe_timeout="$PROBE_TIMEOUT_SEC_BRAIN"
        _probe_body="/tmp/ollama_probe_${PORT}.json"
        rm -f "$_probe_body" 2>/dev/null || true
        _probe=$(curl -s --max-time "$_probe_timeout" -o "$_probe_body" -w '%{http_code}' \
            -X POST "http://localhost:${PORT}/api/generate" \
            -H 'Content-Type: application/json' \
            -d "$(probe_generate_payload "$PORT" "$_probe_model")" 2>/dev/null)
        _probe_msg=""
        [ -f "$_probe_body" ] && _probe_msg="$(tr -d '\n' < "$_probe_body" 2>/dev/null || true)"

        # If curl says 000 but response body already has done=true, treat as slow-success, not failure.
        if [ "$_probe" = "000" ] && echo "$_probe_msg" | grep -q '"done":true'; then
            _probe="200"
        fi
        # Fallback liveness guard: under peak load /api/generate may hit timeout while
        # serve is healthy; confirm with lightweight endpoint before counting a fail.
        if [ "$_probe" = "000" ]; then
            _live_code=$(curl -s --max-time 3 -o /tmp/ollama_live_${PORT}.json -w '%{http_code}' \
                "http://localhost:${PORT}/api/version" 2>/dev/null || echo "000")
            if [ "$_live_code" = "200" ]; then
                _probe="200"
                _probe_msg="timeout_on_generate_but_live_api_version"
                _total="$(counter_inc "$TIMEOUT_LIVE_COUNTER_FILE")"
                log "PROBE-TIMEOUT-LIVE :$PORT total=${_total} (generate timeout, /api/version=200)"
            fi
        fi

        if [ "$_probe" = "200" ]; then
            note_probe_success "$PORT"
        elif [ "$_probe" = "503" ] || [ "$_probe" = "000" ] || { [ "$_probe" = "500" ] && echo "$_probe_msg" | grep -Eiq 'llama-server process no longer running|unexpected EOF|server disconnected'; }; then
            _fails=$(note_probe_failure "$PORT")
            if in_startup_grace "$PORT"; then
                log "PROBE-DEFER :$PORT code=$_probe fails=${_fails}/${PROBE_FAILS_BEFORE_RESTART} (startup_grace ${PROBE_STARTUP_GRACE_SEC}s)"
            elif should_restart_after_probe_failure "$PORT"; then
                log "PROBE-RESTART :$PORT code=$_probe fails=${_fails}/${PROBE_FAILS_BEFORE_RESTART} body='$_probe_msg'"
                restart_serve "$PORT" "$MAIN_PID"
                log "PROBE-RESTART :$PORT — serve сброшен"
                note_probe_success "$PORT"
            else
                log "PROBE-FAIL :$PORT code=$_probe fails=${_fails}/${PROBE_FAILS_BEFORE_RESTART} (cooldown/hysteresis)"
            fi
        else
            # Unknown/non-critical probe outcome — do not escalate into restart.
            log "PROBE-SKIP :$PORT code=$_probe"
        fi
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
        _probe_body="/tmp/ollama_probe_norunner_${PORT}.json"
        _probe=$(curl -s --max-time 5 -o "$_probe_body" -w '%{http_code}' \
            -X POST "http://localhost:${PORT}/api/generate" \
            -H 'Content-Type: application/json' \
            -d "$(probe_generate_payload "$PORT" "$([ "$PORT" = "11434" ] && echo victoria-qwen38:latest || echo phi3.5:3.8b-stable)")" 2>/dev/null)
        _probe_msg=""
        [ -f "$_probe_body" ] && _probe_msg="$(tr -d '\n' < "$_probe_body" 2>/dev/null || true)"
        if [ "$_probe" = "503" ] || { [ "$_probe" = "500" ] && echo "$_probe_msg" | grep -Eiq 'llama-server process no longer running|unexpected EOF|server disconnected'; }; then
            log "ORPHAN-QUEUE :$PORT — probe=$_probe без раннеров, сброс serve (pid=$MAIN_PID)"
            restart_serve "$PORT" "$MAIN_PID"
            log "ORPHAN-QUEUE :$PORT — serve сброшен, очередь очищена"
        else
            log "Нет раннеров (:$PORT), проба=$_probe body='$_probe_msg' — инстанс спокоен"
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

# Export watchdog counters for scraping (node_exporter textfile style).
write_prom_metrics

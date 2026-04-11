#!/bin/bash
# cloud_watchdog.sh — автоматический переключатель STRICT_LOCAL
#
# Следит за доступностью api.anthropic.com (и api.openai.com).
# Если оба недоступны → STRICT_LOCAL=true + перезапуск Victoria + ntfy уведомление.
# Когда восстанавливается → STRICT_LOCAL=false + перезапуск + ntfy уведомление.
#
# Запуск как демон: launchd (com.atra.cloud-watchdog)
# Запуск вручную:  bash scripts/cloud_watchdog.sh
# Лог:             ~/Library/Logs/atra-cloud-watchdog.log

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env"
KOS_ENV_FILE="$ROOT/knowledge_os/.env"
LOG_FILE="$HOME/Library/Logs/atra-cloud-watchdog.log"
NTFY_URL="$(grep '^NTFY_URL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 | tr -d ' ')"
NTFY_URL="${NTFY_URL:-https://ntfy.sh/atra_victoria_curator}"

# Интервалы
CHECK_INTERVAL=30          # секунд между проверками в нормальном режиме
OFFLINE_RECHECK=60         # секунд между проверками в офлайн режиме
FAIL_THRESHOLD=3           # сколько подряд неудач → включить STRICT_LOCAL
RESTORE_THRESHOLD=2        # сколько подряд успехов → выключить STRICT_LOCAL
CONNECT_TIMEOUT=5          # секунд таймаут TCP соединения

# Хосты для проверки (достаточно одного доступного → интернет есть)
CLOUD_HOSTS=("api.anthropic.com:443" "api.openai.com:443" "1.1.1.1:53")

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $*"
    echo "$msg"
    echo "$msg" >> "$LOG_FILE"
}

notify() {
    local title="$1" msg="$2" priority="${3:-default}"
    if [ -n "$NTFY_URL" ]; then
        curl -s --max-time 5 \
            -H "Title: $title" \
            -H "Priority: $priority" \
            -d "$msg" \
            "$NTFY_URL" > /dev/null 2>&1 || true
    fi
}

check_cloud() {
    # Проверяем каждый хост — достаточно одного успешного
    for host_port in "${CLOUD_HOSTS[@]}"; do
        local host="${host_port%%:*}"
        local port="${host_port##*:}"
        if timeout "$CONNECT_TIMEOUT" bash -c "echo > /dev/tcp/$host/$port" 2>/dev/null; then
            return 0  # доступен
        fi
    done
    return 1  # все недоступны
}

get_strict_local() {
    grep '^STRICT_LOCAL=' "$ENV_FILE" 2>/dev/null | cut -d= -f2 | tr -d ' ' || echo "false"
}

set_strict_local() {
    local val="$1"
    # .env
    if grep -q '^STRICT_LOCAL=' "$ENV_FILE" 2>/dev/null; then
        sed -i '' "s/^STRICT_LOCAL=.*/STRICT_LOCAL=$val/" "$ENV_FILE"
    else
        echo "STRICT_LOCAL=$val" >> "$ENV_FILE"
    fi
    # knowledge_os/.env
    if [ -f "$KOS_ENV_FILE" ]; then
        if grep -q '^STRICT_LOCAL=' "$KOS_ENV_FILE" 2>/dev/null; then
            sed -i '' "s/^STRICT_LOCAL=.*/STRICT_LOCAL=$val/" "$KOS_ENV_FILE"
        else
            echo "STRICT_LOCAL=$val" >> "$KOS_ENV_FILE"
        fi
    fi
}

restart_victoria() {
    log "🔄 Перезапускаем victoria-agent..."
    cd "$ROOT"
    docker compose -f knowledge_os/docker-compose.yml up -d \
        --no-deps --force-recreate victoria-agent > /dev/null 2>&1 || \
        docker restart victoria-agent > /dev/null 2>&1 || true
    log "✅ victoria-agent перезапущен"
}

# ── Основной цикл ──────────────────────────────────────────────────────────────

log "🚀 cloud_watchdog запущен (проверка каждые ${CHECK_INTERVAL}s)"
log "   Хосты: ${CLOUD_HOSTS[*]}"
log "   Порог отключения: $FAIL_THRESHOLD подряд | восстановления: $RESTORE_THRESHOLD подряд"

fail_count=0
success_count=0
currently_offline=false

# Синхронизируем состояние с текущим значением STRICT_LOCAL
current_val="$(get_strict_local)"
if [ "$current_val" = "true" ]; then
    currently_offline=true
    log "📌 Запуск: STRICT_LOCAL уже true — режим офлайн"
fi

while true; do
    if check_cloud; then
        fail_count=0
        ((success_count++)) || true

        if $currently_offline && [ "$success_count" -ge "$RESTORE_THRESHOLD" ]; then
            log "🌐 Интернет восстановлен! Выключаем STRICT_LOCAL..."
            set_strict_local "false"
            restart_victoria
            currently_offline=false
            success_count=0
            notify "☁️ Victoria: онлайн режим" \
                "Доступ к облачным API восстановлён. STRICT_LOCAL=false. Victoria переключена." \
                "default"
            log "✅ STRICT_LOCAL=false, Victoria работает в нормальном режиме"
        fi
        sleep "$CHECK_INTERVAL"
    else
        success_count=0
        ((fail_count++)) || true
        log "⚠️ Облако недоступно (попытка $fail_count/$FAIL_THRESHOLD)"

        if ! $currently_offline && [ "$fail_count" -ge "$FAIL_THRESHOLD" ]; then
            log "🔒 Переключаемся в STRICT_LOCAL=true..."
            set_strict_local "true"
            restart_victoria
            currently_offline=true
            fail_count=0
            notify "🔒 Victoria: офлайн режим" \
                "api.anthropic.com недоступен. STRICT_LOCAL=true. Victoria работает только локально (MLX + Ollama + SearXNG)." \
                "high"
            log "🔒 STRICT_LOCAL=true, Victoria только локально"
        fi
        sleep "$OFFLINE_RECHECK"
    fi
done

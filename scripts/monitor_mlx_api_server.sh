#!/bin/bash
# Мониторинг и автоматический перезапуск MLX API Server
# Запускается через launchd для постоянного мониторинга

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LOG_FILE="${HOME}/Library/Logs/atra-mlx-monitor.log"
ERROR_LOG="${HOME}/Library/Logs/atra-mlx-monitor.error.log"
CHECK_INTERVAL=30  # Проверка каждые 30 секунд
MAX_RESTARTS_PER_HOUR=5  # Максимум 5 перезапусков в час
RESTART_COUNT_FILE="${HOME}/Library/Logs/atra-mlx-restart-count.txt"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

log_error() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" | tee -a "$ERROR_LOG"
}

# Порт MLX API Server (можно изменить через MLX_API_PORT)
MLX_PORT=${MLX_API_PORT:-11435}

# Таймаут полного ответа: если сервер принял соединение, но не отдал ответ (зависание) — считаем мёртвым
HEALTH_MAX_TIME=${MLX_HEALTH_MAX_TIME:-10}

# Функция проверки MLX API Server (мировые практики: health check легче /api/tags)
# --max-time: если /health не ответил за N с (процесс есть, но завис) — перезапуск
check_mlx_server() {
    if curl -s -f --connect-timeout 3 --max-time "$HEALTH_MAX_TIME" "http://localhost:${MLX_PORT}/health" >/dev/null 2>&1; then
        return 0
    fi
    # Fallback: /api/tags (если /health изменился)
    if curl -s -f --connect-timeout 3 --max-time "$HEALTH_MAX_TIME" "http://localhost:${MLX_PORT}/api/tags" >/dev/null 2>&1; then
        return 0
    fi
    return 1
}

# Функция проверки процесса
check_mlx_process() {
    if pgrep -f "uvicorn.*mlx_api_server" > /dev/null || \
       pgrep -f "python.*mlx_api_server" > /dev/null; then
        return 0
    else
        return 1
    fi
}

# Функция получения количества перезапусков за последний час
get_restart_count() {
    local current_hour=$(date '+%Y-%m-%d-%H')
    if [ -f "$RESTART_COUNT_FILE" ]; then
        local file_hour=$(head -1 "$RESTART_COUNT_FILE" 2>/dev/null || echo "")
        if [ "$file_hour" = "$current_hour" ]; then
            local count=$(tail -1 "$RESTART_COUNT_FILE" 2>/dev/null || echo "0")
            echo "$count"
        else
            echo "0"
        fi
    else
        echo "0"
    fi
}

# Функция увеличения счетчика перезапусков
increment_restart_count() {
    local current_hour=$(date '+%Y-%m-%d-%H')
    local count=$(get_restart_count)
    count=$((count + 1))
    echo "$current_hour" > "$RESTART_COUNT_FILE"
    echo "$count" >> "$RESTART_COUNT_FILE"
    echo "$count"
}

# Функция перезапуска MLX API Server
restart_mlx_server() {
    log "🔄 Перезапуск MLX API Server..."

    # 1. Сначала пробуем исправить launchd (Documents access workaround)
    # Если com.atra.mlx-api-server имеет статус 126 или 127 в launchctl list,
    # значит macOS заблокировала доступ к Documents.
    # См. docs/MLX_CRASH_ACCOUNTABILITY.md §5
    local launchd_status
    launchd_status=$(launchctl list gui/$(id -u) 2>/dev/null | grep "com.atra.mlx-api-server" | awk '{print $2}' || echo "0")
    if [[ "$launchd_status" == "126" || "$launchd_status" == "127" ]]; then
        log "⚠️ Обнаружена блокировка launchd (код $launchd_status). Перезапускаю setup_mlx_autostart.sh..."
        bash scripts/setup_mlx_autostart.sh >> "$LOG_FILE" 2>> "$ERROR_LOG" || true
        sleep 5
    fi

    # 1.1. Проверка монитора
    local monitor_status
    monitor_status=$(launchctl list 2>/dev/null | grep "com.atra.mlx-monitor" | awk '{print $2}' || echo "0")
    if [[ "$monitor_status" == "126" || "$monitor_status" == "127" ]]; then
        log "⚠️ Обнаружена блокировка монитора (код $monitor_status). Перезапускаю setup_system_auto_recovery.sh..."
        bash scripts/setup_system_auto_recovery.sh >> "$LOG_FILE" 2>> "$ERROR_LOG" || true
        sleep 5
    fi

    # 2. Убиваем старый процесс если есть
    pkill -f "uvicorn.*mlx_api_server" 2>/dev/null || true
    pkill -f "python.*mlx_api_server" 2>/dev/null || true
    sleep 2

    # Проверяем лимит перезапусков
    local restart_count=$(get_restart_count)
    if [ "$restart_count" -ge "$MAX_RESTARTS_PER_HOUR" ]; then
        log_error "❌ Достигнут лимит перезапусков ($MAX_RESTARTS_PER_HOUR/час). Требуется ручное вмешательство."
        return 1
    fi

    # 3. Запускаем MLX API Server
    # Сначала пробуем через launchd (так как мы его починили выше)
    log "🚀 Запуск через launchctl kickstart..."
    launchctl kickstart -k "gui/$(id -u)/com.atra.mlx-api-server" 2>/dev/null || \
    launchctl start com.atra.mlx-api-server 2>/dev/null || true

    sleep 10

    # Если через launchd не поднялся, используем прямой запуск как fallback
    if ! check_mlx_server; then
        log "⚠️ launchd не помог, пробую прямой запуск через start_mlx_api_server.sh..."
        if [ -f "scripts/start_mlx_api_server.sh" ]; then
            bash scripts/start_mlx_api_server.sh >> "$LOG_FILE" 2>> "$ERROR_LOG" &
            sleep 10
        fi
    fi

    # Финальная проверка
    if check_mlx_server; then
        local new_count=$(increment_restart_count)
        log "✅ MLX API Server успешно перезапущен (перезапуск #$new_count за этот час)"
        return 0
    else
        log_error "❌ MLX API Server не запустился после всех попыток"
        return 1
    fi
}

# Основной цикл мониторинга
log "=============================================="
log "📡 МОНИТОРИНГ MLX API SERVER ЗАПУЩЕН"
log "=============================================="
log "Интервал проверки: $CHECK_INTERVAL секунд"
log "Максимум перезапусков в час: $MAX_RESTARTS_PER_HOUR"
log "Таймаут ответа /health: ${HEALTH_MAX_TIME}с (env MLX_HEALTH_MAX_TIME)"
log ""

while true; do
    # Проверяем процесс (причина: Metal OOM или краш — процесс завершился)
    if ! check_mlx_process; then
        log "⚠️ Причина перезапуска: процесс MLX API Server не найден (возможен Metal OOM или краш)"
        restart_mlx_server || true
    # Проверяем доступность сервера (процесс есть, но не отвечает или ответ > HEALTH_MAX_TIME — зависание)
    elif ! check_mlx_server; then
        log "⚠️ Причина перезапуска: MLX API Server не ответил на :${MLX_PORT}/health за ${HEALTH_MAX_TIME}с (процесс запущен, зависание или перегрузка)"
        restart_mlx_server || true
    else
        # Все в порядке, логируем раз в 10 проверок (каждые ~5 минут при CHECK_INTERVAL=30)
        if [ $((RANDOM % 10)) -eq 0 ]; then
            log "✅ MLX API Server работает нормально (health OK)"
        fi
    fi

    sleep "$CHECK_INTERVAL"
done

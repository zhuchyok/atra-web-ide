#!/bin/bash
# Victoria Telegram Bot Supervisor
# Автоматический контроль и перезапуск бота при падении или зависании
# Мировые практики: Health Check + Process Monitoring

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Настройки
BOT_MODULE="src.agents.bridge.victoria_telegram_bot"
LOG_FILE="$ROOT/victoria_bot_supervisor.log"
PID_FILE="$ROOT/.victoria_bot_supervisor.pid"
VICTORIA_URL="${VICTORIA_URL:-http://localhost:8010}"
CHECK_INTERVAL=30
MAX_RESTARTS=10
RESTART_COUNT=0

# Защита от двойного запуска супервизора
if [ -f "$PID_FILE" ]; then
    OLD_PID=$(cat "$PID_FILE")
    if ps -p "$OLD_PID" > /dev/null 2>&1; then
        echo "⚠️ Супервизор уже запущен (PID: $OLD_PID). Выход."
        exit 0
    fi
fi
echo $$ > "$PID_FILE"

# Очистка PID файла при выходе
trap "rm -f $PID_FILE; exit" INT TERM EXIT

# Python
if [ -x "$ROOT/.venv/bin/python" ]; then
    PYTHON3="$ROOT/.venv/bin/python"
else
    PYTHON3="$(which python3 2>/dev/null || echo "/usr/bin/python3")"
fi

log() {
    echo "$(date '+%Y-%m-%d %H:%M:%S') - $1" | tee -a "$LOG_FILE"
}

start_bot() {
    log "🚀 Запуск Victoria Telegram Bot..."
    nohup "$PYTHON3" -m "$BOT_MODULE" >> "$ROOT/victoria_bot.log" 2>&1 &
    BOT_PID=$!
    log "✅ Бот запущен (PID: $BOT_PID)"
    RESTART_COUNT=$((RESTART_COUNT + 1))
}

check_bot() {
    # 1. Проверка процесса по имени модуля
    PID=$(pgrep -f "$BOT_MODULE" | head -n 1)
    if [ -z "$PID" ]; then
        log "⚠️ Процесс бота не найден!"
        return 1
    fi

    # 2. Проверка Health Check через Victoria Server
    HEALTH_JSON=$(curl -s "$VICTORIA_URL/health/telegram")
    if [ $? -ne 0 ]; then
        log "⚠️ Victoria Server недоступен, пропускаю Health Check"
        return 0
    fi

    STATUS=$(echo "$HEALTH_JSON" | grep -o '"status":"[^"]*"' | head -n 1 | cut -d'"' -f4)
    AGE=$(echo "$HEALTH_JSON" | grep -o '"heartbeat_age_seconds":[0-9.]*' | head -n 1 | cut -d':' -f2)

    if [ "$STATUS" == "error" ]; then
        log "❌ Health Check вернул ERROR"
        return 1
    fi

    if [ -n "$AGE" ]; then
        # Если пульса нет более 5 минут — считаем зависшим
        if (( $(echo "$AGE > 300" | bc -l) )); then
            log "❌ Пульс бота устарел ($AGE сек), возможно зависание"
            kill -9 "$PID"
            return 1
        fi
    fi

    return 0
}

log "=== Victoria Bot Supervisor Started ==="

while true; do
    if ! check_bot; then
        if [ $RESTART_COUNT -ge $MAX_RESTARTS ]; then
            log "❌ Превышено максимальное количество перезапусков ($MAX_RESTARTS). Жду 10 минут..."
            sleep 600
            RESTART_COUNT=0
        fi
        start_bot
    else
        # Сброс счетчика перезапусков при стабильной работе
        RESTART_COUNT=0
    fi
    sleep "$CHECK_INTERVAL"
done

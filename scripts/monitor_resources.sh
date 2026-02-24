#!/bin/bash

# Мониторинг ресурсов системы в реальном времени
# Отслеживает: RAM, CPU, температуру, MLX, Ollama

set -e

LOG_FILE="/tmp/resource_monitor.log"
INTERVAL=10  # Проверка каждые 10 секунд

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

check_resources() {
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    log "📊 МОНИТОРИНГ РЕСУРСОВ"
    log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    # Системные ресурсы
    log ""
    log "💻 СИСТЕМА:"
    RAM_USED=$(vm_stat | grep "Pages active" | awk '{print $3}' | sed 's/\.//')
    RAM_TOTAL=$(sysctl -n hw.memsize)
    RAM_PERCENT=$(python3 -c "print(f'{($RAM_USED * 4096 / $RAM_TOTAL) * 100:.1f}')" 2>/dev/null || echo "N/A")
    CPU_PERCENT=$(top -l 1 | grep "CPU usage" | awk '{print $3}' | sed 's/%//' || echo "N/A")

    log "   RAM: ${RAM_PERCENT}% использовано"
    log "   CPU: ${CPU_PERCENT}% использовано"

    # Температура (macOS)
    TEMP=$(sudo powermetrics --samplers smc -n 1 2>/dev/null | grep -i "CPU die temperature" | awk '{print $4}' || echo "N/A")
    if [ "$TEMP" != "N/A" ]; then
        log "   Температура: ${TEMP}°C"
    fi

    # MLX API Server
    log ""
    log "🍎 MLX API SERVER:"
    MLX_HEALTH=$(curl -s http://localhost:11435/health 2>/dev/null || echo "{}")
    if [ "$MLX_HEALTH" != "{}" ]; then
        ACTIVE=$(echo "$MLX_HEALTH" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('active_requests', 0))" 2>/dev/null || echo "0")
        MAX=$(echo "$MLX_HEALTH" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('max_concurrent', 5))" 2>/dev/null || echo "5")
        CACHED=$(echo "$MLX_HEALTH" | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('models_cached', 0))" 2>/dev/null || echo "0")
        log "   Активных запросов: ${ACTIVE}/${MAX}"
        log "   Кэшировано моделей: ${CACHED}"

        # Проверка перегрузки
        if [ "$ACTIVE" -ge "$MAX" ]; then
            log "   ⚠️ ПЕРЕГРУЗКА: Все слоты заняты!"
        fi
    else
        log "   ❌ Недоступен"
    fi

    # Ollama
    log ""
    log "🦙 OLLAMA:"
    OLLAMA_PS=$(curl -s http://localhost:11434/api/ps 2>/dev/null || echo "{}")
    if [ "$OLLAMA_PS" != "{}" ]; then
        PROCESSES=$(echo "$OLLAMA_PS" | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('processes', [])))" 2>/dev/null || echo "0")
        log "   Активных процессов: ${PROCESSES}"
        if [ "$PROCESSES" -gt 0 ]; then
            MODELS=$(echo "$OLLAMA_PS" | python3 -c "import sys, json; data=json.load(sys.stdin); [print(f'   • {p.get(\"model\", \"unknown\")}') for p in data.get('processes', [])[:3]]" 2>/dev/null || echo "")
            echo "$MODELS"
        fi
    else
        log "   ❌ Недоступен"
    fi

    # Статистика задач
    log ""
    log "📋 ЗАДАЧИ:"
    TASK_STATS=$(docker exec knowledge_postgres psql -U admin -d knowledge_os -t -c "
        SELECT
            status,
            COUNT(*) as count
        FROM tasks
        GROUP BY status
        ORDER BY
            CASE status
                WHEN 'completed' THEN 1
                WHEN 'in_progress' THEN 2
                WHEN 'pending' THEN 3
                ELSE 4
            END;
    " 2>/dev/null || echo "")

    if [ -n "$TASK_STATS" ]; then
        echo "$TASK_STATS" | while IFS='|' read -r status count; do
            status=$(echo "$status" | xargs)
            count=$(echo "$count" | xargs)
            if [ -n "$status" ] && [ -n "$count" ]; then
                log "   ${status}: ${count}"
            fi
        done
    fi

    # Скорость обработки
    log ""
    log "⚡ СКОРОСТЬ:"
    SPEED=$(docker exec knowledge_postgres psql -U admin -d knowledge_os -t -c "
        SELECT
            COUNT(*) FILTER (WHERE status = 'completed' AND updated_at > NOW() - INTERVAL '10 minutes')
        FROM tasks;
    " 2>/dev/null | xargs)

    if [ -n "$SPEED" ] && [ "$SPEED" != "0" ]; then
        SPEED_PER_MIN=$(python3 -c "print(f'{int($SPEED) / 10:.1f}')" 2>/dev/null || echo "N/A")
        log "   За 10 минут: ${SPEED} задач (~${SPEED_PER_MIN} задач/мин)"
    fi

    log ""
}

main_loop() {
    log "🚀 Запуск мониторинга ресурсов (интервал: ${INTERVAL}s)"

    while true; do
        check_resources
        sleep "$INTERVAL"
    done
}

main_loop

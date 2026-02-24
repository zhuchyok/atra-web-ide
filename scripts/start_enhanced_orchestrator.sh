#!/bin/bash
# Скрипт для запуска Enhanced Orchestrator в автоматическом режиме
# Запускается каждые 5 минут
# Redis: knowledge_redis (atra-network). При "too many clients already" — увеличьте max_connections в PostgreSQL.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 Запуск Enhanced Orchestrator..."
echo "   Проект: $PROJECT_ROOT"
echo "   Время: $(date)"

# Проверяем Docker
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker не запущен!"
    exit 1
fi

# Контейнер: victoria-agent предпочтителен (тот же что в cron; Redis=knowledge_redis)
ORCH_CONTAINER=""
if docker ps --format "{{.Names}}" | grep -q "victoria-agent"; then
    ORCH_CONTAINER="victoria-agent"
elif docker ps --format "{{.Names}}" | grep -q "knowledge_os_api"; then
    ORCH_CONTAINER="knowledge_os_api"
fi
if [ -z "$ORCH_CONTAINER" ]; then
    echo "❌ Ни контейнер knowledge_os_api, ни victoria-agent не запущены!"
    echo "   Запустите: docker-compose -f knowledge_os/docker-compose.yml up -d"
    exit 1
fi
echo "   Используем контейнер: $ORCH_CONTAINER"

# Функция запуска одного цикла
run_orchestrator_cycle() {
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Запуск Enhanced Orchestrator..."

    # knowledge_os_api и victoria-agent в atra-network видят только knowledge_redis (не atra-redis)
    if [ "$ORCH_CONTAINER" = "knowledge_os_api" ] || [ "$ORCH_CONTAINER" = "victoria-agent" ]; then
        REDIS_CONTAINER="knowledge_redis"
    elif docker ps --format "{{.Names}}" | grep -q "knowledge_redis"; then
        REDIS_CONTAINER="knowledge_redis"
    else
        REDIS_CONTAINER=$(docker ps --format "{{.Names}}" | grep -i redis | head -1)
    fi
    if [ -z "$REDIS_CONTAINER" ]; then
        REDIS_URL="redis://localhost:6379"
    else
        REDIS_URL="redis://${REDIS_CONTAINER}:6379"
    fi

    if [ "$ORCH_CONTAINER" = "victoria-agent" ]; then
        docker exec -e DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os \
            -e REDIS_URL="$REDIS_URL" \
            victoria-agent \
            python3 /app/knowledge_os/app/enhanced_orchestrator.py 2>&1 | tee -a /tmp/enhanced_orchestrator.log
    else
        docker exec -e DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os \
            -e REDIS_URL="$REDIS_URL" \
            knowledge_os_api \
            python3 /app/enhanced_orchestrator.py 2>&1 | tee -a /tmp/enhanced_orchestrator.log
    fi

    local exit_code=${PIPESTATUS[0]}

    if [ $exit_code -eq 0 ]; then
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] ✅ Orchestrator завершен успешно"
    else
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] ⚠️ Orchestrator завершен с кодом $exit_code"
    fi

    return $exit_code
}

# Если передан аргумент "once", запускаем один раз и выходим
if [ "$1" = "once" ]; then
    run_orchestrator_cycle
    exit $?
fi

# Режим "continuous": оркестратор всё время слушает (один процесс, цикл внутри Python)
# Интервал по умолчанию 60 сек; при появлении нераспределённых задач — следующий цикл через 30 сек
if [ "$1" = "continuous" ] || [ "$1" = "listen" ]; then
    [ -z "$REDIS_URL" ] && REDIS_URL="redis://knowledge_redis:6379"
    echo "🔄 Режим непрерывной работы: оркестратор слушает задачи (--continuous --interval 60)"
    echo "   Для остановки нажмите Ctrl+C"
    echo "   Логи: /tmp/enhanced_orchestrator.log"
    echo ""
    ORCH_INTERVAL="${ORCHESTRATOR_INTERVAL:-60}"
    ORCH_QUICK_POLL="${ORCHESTRATOR_QUICK_POLL:-30}"
    if [ "$ORCH_CONTAINER" = "victoria-agent" ]; then
        docker exec -e DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os \
            -e REDIS_URL="$REDIS_URL" \
            victoria-agent \
            python3 /app/knowledge_os/app/enhanced_orchestrator.py --continuous --interval "$ORCH_INTERVAL" --quick-poll "$ORCH_QUICK_POLL" 2>&1 | tee -a /tmp/enhanced_orchestrator.log
    else
        docker exec -e DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os \
            -e REDIS_URL="${REDIS_URL:-redis://knowledge_redis:6379}" \
            knowledge_os_api \
            python3 /app/enhanced_orchestrator.py --continuous --interval "$ORCH_INTERVAL" --quick-poll "$ORCH_QUICK_POLL" 2>&1 | tee -a /tmp/enhanced_orchestrator.log
    fi
    exit $?
fi

# Иначе запускаем в цикле каждые 5 минут (как раньше)
echo "🔄 Запуск в автоматическом режиме (каждые 5 минут)"
echo "   Для непрерывного режима: $0 continuous"
echo "   Для остановки нажмите Ctrl+C"
echo "   Логи: /tmp/enhanced_orchestrator.log"
echo ""

while true; do
    run_orchestrator_cycle

    echo "[$(date +'%Y-%m-%d %H:%M:%S')] Ожидание 5 минут до следующего запуска..."
    sleep 300  # 5 минут
done

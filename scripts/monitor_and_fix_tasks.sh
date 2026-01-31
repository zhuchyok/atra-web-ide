#!/bin/bash

# Автоматический мониторинг и исправление задач
# Отслеживает выполнение задач dashboard_audit и других критических задач
# Если задачи застряли - ищет причину и исправляет

set -e

LOG_FILE="/tmp/task_monitor.log"
MAX_STUCK_TIME=600  # 10 минут - если задача в in_progress дольше, считаем застрявшей
CHECK_INTERVAL=30   # Проверка каждые 30 секунд

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

check_dashboard_audit_tasks() {
    log "🔍 Проверка задач dashboard_audit..."
    
    # Получаем статус задач
    STATUS=$(docker exec knowledge_postgres psql -U admin -d knowledge_os -t -c "
        SELECT 
            id,
            title,
            status,
            EXTRACT(EPOCH FROM (NOW() - updated_at))::int as seconds_stuck,
            metadata->>'assignee_expert_id' as assignee
        FROM tasks 
        WHERE metadata->>'source' = 'dashboard_audit'
        ORDER BY updated_at ASC;
    " 2>&1)
    
    echo "$STATUS" | while IFS='|' read -r task_id title status seconds_stuck assignee; do
        task_id=$(echo "$task_id" | xargs)
        title=$(echo "$title" | xargs)
        status=$(echo "$status" | xargs)
        seconds_stuck=$(echo "$seconds_stuck" | xargs)
        assignee=$(echo "$assignee" | xargs)
        
        if [ -z "$task_id" ] || [ "$task_id" = "id" ]; then
            continue
        fi
        
        if [ "$status" = "in_progress" ] && [ "$seconds_stuck" -gt "$MAX_STUCK_TIME" ]; then
            log "⚠️ ЗАДАЧА ЗАСТРЯЛА: $title (ID: $task_id, застряла $seconds_stuck секунд)"
            
            # Проверяем логи worker'а
            WORKER_LOGS=$(docker logs knowledge_os_worker --tail 50 2>&1 | grep -i "$task_id" || echo "")
            if [ -z "$WORKER_LOGS" ]; then
                log "❌ Задача не найдена в логах worker'а - возможно worker не обрабатывает её"
            else
                log "📋 Логи worker'а для задачи: $WORKER_LOGS"
            fi
            
            # Проверяем доступность моделей
            OLLAMA_STATUS=$(curl -s http://localhost:11434/api/tags > /dev/null 2>&1 && echo "OK" || echo "FAIL")
            MLX_STATUS=$(curl -s http://localhost:11435/health > /dev/null 2>&1 && echo "OK" || echo "FAIL")
            
            log "🔧 Статус моделей: Ollama=$OLLAMA_STATUS, MLX=$MLX_STATUS"
            
            # Если модели недоступны - перезапускаем задачу
            if [ "$OLLAMA_STATUS" = "FAIL" ] && [ "$MLX_STATUS" = "FAIL" ]; then
                log "❌ Все модели недоступны! Сбрасываем задачу в pending..."
                docker exec knowledge_postgres psql -U admin -d knowledge_os -c "
                    UPDATE tasks 
                    SET status = 'pending', 
                        updated_at = NOW(),
                        metadata = jsonb_set(metadata, '{retry_count}', COALESCE((metadata->>'retry_count')::int, 0) + 1)
                    WHERE id = '$task_id';
                " 2>&1 | tee -a "$LOG_FILE"
            elif [ "$seconds_stuck" -gt 1800 ]; then
                # Если застряла больше 30 минут - сбрасываем
                log "⏰ Задача застряла больше 30 минут, сбрасываем в pending..."
                docker exec knowledge_postgres psql -U admin -d knowledge_os -c "
                    UPDATE tasks 
                    SET status = 'pending', 
                        updated_at = NOW(),
                        metadata = jsonb_set(metadata, '{stuck_reset}', 'true')
                    WHERE id = '$task_id';
                " 2>&1 | tee -a "$LOG_FILE"
            fi
        elif [ "$status" = "pending" ]; then
            log "⏳ Ожидает обработки: $title (ID: $task_id)"
        elif [ "$status" = "completed" ]; then
            log "✅ Выполнена: $title (ID: $task_id)"
        fi
    done
}

check_worker_health() {
    log "🔍 Проверка health worker'а..."
    
    # Проверяем, что worker запущен
    if ! docker ps | grep -q knowledge_os_worker; then
        log "❌ Worker не запущен! Запускаем..."
        cd /Users/bikos/Documents/atra-web-ide/knowledge_os
        docker-compose up -d knowledge_os_worker
        sleep 5
    fi
    
    # Проверяем последние логи на ошибки
    RECENT_ERRORS=$(docker logs knowledge_os_worker --tail 20 2>&1 | grep -i "error\|exception\|failed" || echo "")
    if [ -n "$RECENT_ERRORS" ]; then
        log "⚠️ Найдены ошибки в worker'е:"
        echo "$RECENT_ERRORS" | head -5 | tee -a "$LOG_FILE"
    fi
}

check_models_availability() {
    log "🔍 Проверка доступности моделей..."
    
    # Ollama
    if curl -s --max-time 5 http://localhost:11434/api/tags > /dev/null 2>&1; then
        OLLAMA_MODELS=$(curl -s http://localhost:11434/api/tags | python3 -c "import sys, json; data=json.load(sys.stdin); print(len(data.get('models', [])))" 2>/dev/null || echo "0")
        log "✅ Ollama: работает ($OLLAMA_MODELS моделей)"
    else
        log "❌ Ollama: недоступен!"
        return 1
    fi
    
    # MLX
    if curl -s --max-time 5 http://localhost:11435/health > /dev/null 2>&1; then
        MLX_HEALTH=$(curl -s http://localhost:11435/health | python3 -c "import sys, json; data=json.load(sys.stdin); print(data.get('status', 'unknown'))" 2>/dev/null || echo "unknown")
        log "✅ MLX: работает (status: $MLX_HEALTH)"
    else
        log "⚠️ MLX: недоступен (может быть нормально, если не используется)"
    fi
    
    return 0
}

check_database_connections() {
    log "🔍 Проверка подключений к БД..."
    
    ACTIVE_CONNECTIONS=$(docker exec knowledge_postgres psql -U admin -d knowledge_os -t -c "
        SELECT COUNT(*) FROM pg_stat_activity WHERE datname = 'knowledge_os';
    " 2>&1 | xargs)
    
    MAX_CONNECTIONS=$(docker exec knowledge_postgres psql -U admin -d knowledge_os -t -c "
        SHOW max_connections;
    " 2>&1 | xargs)
    
    log "📊 Активных подключений: $ACTIVE_CONNECTIONS / $MAX_CONNECTIONS"
    
    if [ "$ACTIVE_CONNECTIONS" -gt 90 ]; then
        log "⚠️ Слишком много подключений! Может быть проблема с пулами."
    fi
}

fix_stuck_tasks() {
    log "🔧 Исправление застрявших задач..."
    
    # Находим задачи, которые в in_progress больше MAX_STUCK_TIME
    STUCK_TASKS=$(docker exec knowledge_postgres psql -U admin -d knowledge_os -t -c "
        SELECT id, title
        FROM tasks 
        WHERE status = 'in_progress'
        AND EXTRACT(EPOCH FROM (NOW() - updated_at))::int > $MAX_STUCK_TIME
        LIMIT 10;
    " 2>&1)
    
    if [ -n "$STUCK_TASKS" ] && [ "$(echo "$STUCK_TASKS" | wc -l)" -gt 1 ]; then
        echo "$STUCK_TASKS" | while IFS='|' read -r task_id title; do
            task_id=$(echo "$task_id" | xargs)
            title=$(echo "$title" | xargs)
            
            if [ -z "$task_id" ] || [ "$task_id" = "id" ]; then
                continue
            fi
            
            log "🔄 Сбрасываем застрявшую задачу: $title (ID: $task_id)"
            docker exec knowledge_postgres psql -U admin -d knowledge_os -c "
                UPDATE tasks 
                SET status = 'pending', 
                    updated_at = NOW(),
                    metadata = jsonb_set(
                        COALESCE(metadata, '{}'::jsonb), 
                        '{stuck_reset_at}', 
                        to_jsonb(NOW()::text)
                    )
                WHERE id = '$task_id';
            " 2>&1 | tee -a "$LOG_FILE"
        done
    else
        log "✅ Застрявших задач не найдено"
    fi
}

main_loop() {
    log "🚀 Запуск автоматического мониторинга задач..."
    log "📋 Параметры: MAX_STUCK_TIME=${MAX_STUCK_TIME}s, CHECK_INTERVAL=${CHECK_INTERVAL}s"
    
    while true; do
        log "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
        
        # 1. Проверка health worker'а
        check_worker_health
        
        # 2. Проверка доступности моделей
        if ! check_models_availability; then
            log "⚠️ Проблемы с моделями, но продолжаем мониторинг..."
        fi
        
        # 3. Проверка подключений к БД
        check_database_connections
        
        # 4. Проверка задач dashboard_audit
        check_dashboard_audit_tasks
        
        # 5. Исправление застрявших задач
        fix_stuck_tasks
        
        # 6. Статистика
        STATS=$(docker exec knowledge_postgres psql -U admin -d knowledge_os -t -c "
            SELECT 
                status,
                COUNT(*) as count
            FROM tasks 
            WHERE metadata->>'source' = 'dashboard_audit'
            GROUP BY status;
        " 2>&1)
        
        log "📊 Статистика dashboard_audit задач:"
        echo "$STATS" | grep -v "^$" | tee -a "$LOG_FILE"
        
        log "⏳ Ожидание ${CHECK_INTERVAL} секунд до следующей проверки..."
        sleep "$CHECK_INTERVAL"
    done
}

# Запуск
main_loop

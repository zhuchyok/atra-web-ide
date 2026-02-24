#!/bin/bash
# Автоматическое обнаружение и исправление ошибок
# Запускается автоматически каждые 10 минут
# Таймаут: максимум 2 минуты на выполнение

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_FILE="/tmp/auto_fix_errors.log"
TIMEOUT=120  # 2 минуты максимум

# Функция с таймаутом
run_with_timeout() {
    timeout $TIMEOUT bash -c "$1" || {
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] ⏱️ Проверка прервана по таймауту ($TIMEOUT сек)" >> "$LOG_FILE"
        exit 0
    }
}

{
    echo "[$(date +'%Y-%m-%d %H:%M:%S')] 🔍 Автоматическая проверка ошибок..."

    # 1. Проверка ошибок в логах worker (быстро, без зависаний)
    WORKER_ERRORS=$(timeout 5 docker logs knowledge_worker --tail 50 2>&1 | grep -E "ERROR|Exception|Traceback" | tail -3 || true)
    if [ -n "$WORKER_ERRORS" ]; then
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] ⚠️ Найдены ошибки в worker (последние 3):"
        echo "$WORKER_ERRORS"
    fi

    # 2. Проверка ошибок в orchestrator (быстро)
    ORCH_ERRORS=$(timeout 5 tail -50 /tmp/orchestrator.log 2>/dev/null | grep -E "ERROR|Exception" | tail -3 || true)
    if [ -n "$ORCH_ERRORS" ]; then
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] ⚠️ Найдены ошибки в orchestrator (последние 3):"
        echo "$ORCH_ERRORS"
    fi

    # 3. Проверка застрявших задач (быстро, с таймаутом)
    STUCK_TASKS=$(timeout 10 docker exec knowledge_postgres psql -U admin -d knowledge_os -t -c "SELECT COUNT(*) FROM tasks WHERE status = 'in_progress' AND updated_at < NOW() - INTERVAL '1 day';" 2>/dev/null | tr -d ' ' || echo "0")
    if [ "$STUCK_TASKS" -gt 0 ] && [ "$STUCK_TASKS" != "0" ]; then
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] 🔧 Найдено $STUCK_TASKS застрявших задач, возвращаю в pending..."
        timeout 10 docker exec knowledge_postgres psql -U admin -d knowledge_os -c "UPDATE tasks SET status = 'pending' WHERE status = 'in_progress' AND updated_at < NOW() - INTERVAL '1 day';" >/dev/null 2>&1 || true
    fi

    # 4. Проверка задач без экспертов (быстро, с таймаутом)
    UNASSIGNED=$(timeout 10 docker exec knowledge_postgres psql -U admin -d knowledge_os -t -c "SELECT COUNT(*) FROM tasks WHERE status = 'pending' AND assignee_expert_id IS NULL;" 2>/dev/null | tr -d ' ' || echo "0")
    if [ "$UNASSIGNED" -gt 50 ] && [ "$UNASSIGNED" != "0" ]; then
        echo "[$(date +'%Y-%m-%d %H:%M:%S')] ⚠️ Найдено $UNASSIGNED задач без экспертов (требуется orchestrator)"
        # НЕ запускаем orchestrator здесь - он уже работает по расписанию
    fi

    echo "[$(date +'%Y-%m-%d %H:%M:%S')] ✅ Проверка завершена"
} >> "$LOG_FILE" 2>&1

# Гарантируем выход
exit 0

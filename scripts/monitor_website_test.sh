#!/bin/bash
# Мониторинг теста создания сайта в реальном времени

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/logs"

echo "🔍 Мониторинг теста создания сайта..."
echo "Нажмите Ctrl+C для выхода"
echo ""

# Находим последний лог
LATEST_LOG=$(ls -t "$LOG_DIR"/task_trace_*.log 2>/dev/null | head -1)

if [ -z "$LATEST_LOG" ]; then
    echo "❌ Логи не найдены"
    exit 1
fi

echo "📄 Отслеживаем: $LATEST_LOG"
echo ""

# Мониторим лог с фильтрацией важных событий
tail -f "$LATEST_LOG" | grep --line-buffered -E "(🚀|✅|❌|РЕЗУЛЬТАТ|COMPLETE|Задача|Сотрудник|Выполнено|Victoria|Veronica|София|Алексей|MODEL SELECTION|сайт|HTML)" | while read line; do
    echo "$(date '+%H:%M:%S') | $line"
done

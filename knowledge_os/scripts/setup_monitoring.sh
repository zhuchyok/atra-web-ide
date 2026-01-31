#!/bin/bash
# Настройка автоматического мониторинга для Knowledge OS

set -e

MONITOR_SCRIPT="/root/knowledge_os/app/enhanced_monitor.py"
CRON_LOG="/root/knowledge_os/logs/cron_monitor.log"

echo "🔧 Настройка автоматического мониторинга..."

# Проверяем наличие скрипта мониторинга
if [ ! -f "$MONITOR_SCRIPT" ]; then
    echo "❌ Скрипт мониторинга не найден: $MONITOR_SCRIPT"
    exit 1
fi

# Проверяем наличие psutil
if ! python3 -c "import psutil" 2>/dev/null; then
    echo "📦 Установка psutil..."
    pip3 install psutil
fi

# Создаем директорию для логов
mkdir -p "$(dirname $CRON_LOG)"

# Добавляем задачу в crontab (каждые 5 минут)
CRON_JOB="*/5 * * * * cd /root/knowledge_os && python3 app/enhanced_monitor.py >> $CRON_LOG 2>&1"

# Проверяем, не добавлена ли уже задача
if crontab -l 2>/dev/null | grep -q "enhanced_monitor.py"; then
    echo "⚠️  Задача мониторинга уже добавлена в crontab"
else
    # Добавляем задачу
    (crontab -l 2>/dev/null; echo "$CRON_JOB") | crontab -
    echo "✅ Задача мониторинга добавлена в crontab (каждые 5 минут)"
fi

# Показываем текущие задачи
echo ""
echo "📋 Текущие задачи crontab:"
crontab -l | grep -E "(monitor|enhanced_monitor)" || echo "  (нет задач)"

echo ""
echo "✅ Настройка автоматического мониторинга завершена!"
echo ""
echo "📝 Проверка мониторинга:"
echo "  - Логи: $CRON_LOG"
echo "  - Логи мониторинга: /root/knowledge_os/logs/monitor.log"
echo ""
echo "🧪 Тестовый запуск мониторинга:"
echo "  cd /root/knowledge_os && python3 app/enhanced_monitor.py"


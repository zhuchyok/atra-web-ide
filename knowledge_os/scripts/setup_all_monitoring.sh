#!/bin/bash
# Полная настройка мониторинга и бэкапов для Knowledge OS

set -e

echo "🚀 Настройка полной системы мониторинга и бэкапов для Knowledge OS"
echo ""

# 1. Настройка автоматических бэкапов
echo "📦 ШАГ 1: Настройка автоматических бэкапов..."
bash "$(dirname "$0")/setup_automated_backups.sh"
echo ""

# 2. Настройка мониторинга
echo "🔍 ШАГ 2: Настройка автоматического мониторинга..."
bash "$(dirname "$0")/setup_monitoring.sh"
echo ""

# 3. Создание директорий
echo "📁 ШАГ 3: Создание необходимых директорий..."
mkdir -p /root/knowledge_os/backups
mkdir -p /root/knowledge_os/logs
echo "✅ Директории созданы"
echo ""

# 4. Проверка зависимостей
echo "📦 ШАГ 4: Проверка зависимостей..."
if ! python3 -c "import psutil" 2>/dev/null; then
    echo "📦 Установка psutil..."
    pip3 install psutil
fi
echo "✅ Зависимости проверены"
echo ""

# 5. Тестовый запуск
echo "🧪 ШАГ 5: Тестовый запуск..."
echo ""
echo "Тестовый запуск бэкапа:"
bash "$(dirname "$0")/backup_db.sh" || echo "⚠️  Бэкап требует настройки (Telegram токен и т.д.)"
echo ""
echo "Тестовый запуск мониторинга:"
cd /root/knowledge_os && python3 app/enhanced_monitor.py || echo "⚠️  Мониторинг требует настройки (переменные окружения)"
echo ""

# 6. Итоговая информация
echo "======================================================================"
echo "✅ НАСТРОЙКА ЗАВЕРШЕНА!"
echo "======================================================================"
echo ""
echo "📋 ЧТО НАСТРОЕНО:"
echo ""
echo "1. ✅ Автоматические бэкапы (ежедневно в 3:00)"
echo "   - Скрипт: /root/knowledge_os/scripts/backup_db.sh"
echo "   - Логи: /root/knowledge_os/logs/cron_backup.log"
echo "   - Бэкапы: /root/knowledge_os/backups/"
echo ""
echo "2. ✅ Автоматический мониторинг (каждые 5 минут)"
echo "   - Скрипт: /root/knowledge_os/app/enhanced_monitor.py"
echo "   - Логи: /root/knowledge_os/logs/monitor.log"
echo "   - Метрики сохраняются в БД (таблица system_metrics)"
echo ""
echo "3. ✅ Восстановление из бэкапа"
echo "   - Скрипт: /root/knowledge_os/scripts/restore_from_backup.sh"
echo ""
echo "📊 МЕТРИКИ МОНИТОРИНГА:"
echo "   - CPU использование"
echo "   - RAM использование"
echo "   - Disk использование"
echo "   - Database connections"
echo "   - API response time"
echo "   - Knowledge nodes count"
echo "   - Experts count"
echo ""
echo "🚨 АЛЕРТЫ:"
echo "   - Отправляются в Telegram при превышении порогов"
echo "   - Пороги: CPU > 85%, RAM > 85%, Disk > 90%"
echo ""
echo "📝 ПРОВЕРКА:"
echo "   - Просмотр задач: crontab -l"
echo "   - Просмотр логов: tail -f /root/knowledge_os/logs/*.log"
echo ""
echo "======================================================================"

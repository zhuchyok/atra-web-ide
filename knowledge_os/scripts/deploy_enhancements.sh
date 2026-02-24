#!/bin/bash
# Скрипт деплоя всех улучшений Singularity 3.5 на сервер

set -e

SERVER="root@185.177.216.15"
SERVER_PATH="/root/knowledge_os"
LOCAL_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "🚀 Деплой улучшений Singularity 3.5 на сервер..."
echo ""

# Проверка подключения
echo "📡 Проверка подключения к серверу..."
if ! ssh -o ConnectTimeout=5 $SERVER "echo 'Connected'" 2>/dev/null; then
    echo "❌ Не удалось подключиться к серверу"
    echo "💡 Убедитесь, что:"
    echo "   1. Сервер доступен: $SERVER"
    echo "   2. SSH ключ настроен или используйте пароль: u44Ww9NmtQj,XG"
    exit 1
fi

echo "✅ Подключение установлено"
echo ""

# Создание директорий на сервере
echo "📁 Создание директорий на сервере..."
ssh $SERVER "mkdir -p $SERVER_PATH/app $SERVER_PATH/scripts $SERVER_PATH/dashboard $SERVER_PATH/db/migrations"
echo "✅ Директории созданы"
echo ""

# Деплой файлов мониторинга
echo "📦 Деплой: Мониторинг и бэкапы..."
scp "$LOCAL_PATH/app/enhanced_monitor.py" "$SERVER:$SERVER_PATH/app/"
scp "$LOCAL_PATH/scripts/setup_automated_backups.sh" "$SERVER:$SERVER_PATH/scripts/"
scp "$LOCAL_PATH/scripts/setup_monitoring.sh" "$SERVER:$SERVER_PATH/scripts/"
scp "$LOCAL_PATH/scripts/setup_all_monitoring.sh" "$SERVER:$SERVER_PATH/scripts/"
scp "$LOCAL_PATH/scripts/restore_from_backup.sh" "$SERVER:$SERVER_PATH/scripts/"
ssh $SERVER "chmod +x $SERVER_PATH/scripts/*.sh"
echo "✅ Мониторинг задеплоен"
echo ""

# Деплой Orchestrator
echo "📦 Деплой: Улучшенный Orchestrator..."
scp "$LOCAL_PATH/app/enhanced_orchestrator.py" "$SERVER:$SERVER_PATH/app/"
scp "$LOCAL_PATH/db/migrations/add_tasks_table.sql" "$SERVER:$SERVER_PATH/db/migrations/"
echo "✅ Orchestrator задеплоен"
echo ""

# Деплой поиска
echo "📦 Деплой: Улучшенный поиск..."
scp "$LOCAL_PATH/app/enhanced_search.py" "$SERVER:$SERVER_PATH/app/"
scp "$LOCAL_PATH/app/main_enhanced.py" "$SERVER:$SERVER_PATH/app/"
echo "✅ Поиск задеплоен"
echo ""

# Деплой иммунитета
echo "📦 Деплой: Расширенный иммунитет..."
scp "$LOCAL_PATH/app/enhanced_immunity.py" "$SERVER:$SERVER_PATH/app/"
echo "✅ Иммунитет задеплоен"
echo ""

# Деплой аналитики
echo "📦 Деплой: Аналитика и Dashboard..."
scp "$LOCAL_PATH/dashboard/enhanced_analytics.py" "$SERVER:$SERVER_PATH/dashboard/"
scp "$LOCAL_PATH/dashboard/app_enhanced.py" "$SERVER:$SERVER_PATH/dashboard/"
echo "✅ Аналитика задеплоен"
echo ""

# Применение миграции БД
echo "📦 Применение миграции БД..."
ssh $SERVER "cd $SERVER_PATH && psql -U admin -d knowledge_os -f db/migrations/add_tasks_table.sql" || echo "⚠️ Миграция требует ручного применения"
echo ""

# Настройка зависимостей
echo "📦 Проверка зависимостей..."
ssh $SERVER "cd $SERVER_PATH && pip3 install psutil 2>/dev/null || echo 'psutil уже установлен'"
echo ""

# Итоговая информация
echo "======================================================================"
echo "✅ ДЕПЛОЙ ЗАВЕРШЕН!"
echo "======================================================================"
echo ""
echo "📋 ЗАДЕПЛОЕНО:"
echo ""
echo "1. ✅ Мониторинг и бэкапы"
echo "   - enhanced_monitor.py"
echo "   - Скрипты настройки"
echo ""
echo "2. ✅ Улучшенный Orchestrator"
echo "   - enhanced_orchestrator.py"
echo "   - Миграция БД (add_tasks_table.sql)"
echo ""
echo "3. ✅ Улучшенный поиск"
echo "   - enhanced_search.py"
echo "   - main_enhanced.py"
echo ""
echo "4. ✅ Расширенный иммунитет"
echo "   - enhanced_immunity.py"
echo ""
echo "5. ✅ Аналитика и Dashboard"
echo "   - enhanced_analytics.py"
echo "   - app_enhanced.py"
echo ""
echo "======================================================================"
echo "📝 СЛЕДУЮЩИЕ ШАГИ:"
echo ""
echo "1. Применить миграцию БД (если не применена автоматически):"
echo "   ssh $SERVER"
echo "   cd /root/knowledge_os"
echo "   psql -U admin -d knowledge_os -f db/migrations/add_tasks_table.sql"
echo ""
echo "2. Настроить мониторинг и бэкапы:"
echo "   ssh $SERVER"
echo "   cd /root/knowledge_os"
echo "   bash scripts/setup_all_monitoring.sh"
echo ""
echo "3. Запустить улучшенный Dashboard:"
echo "   ssh $SERVER"
echo "   cd /root/knowledge_os/dashboard"
echo "   streamlit run app_enhanced.py --server.port 8502"
echo ""
echo "4. Настроить cron для автоматических задач:"
echo "   ssh $SERVER"
echo "   crontab -e"
echo "   # Добавить:"
echo "   */30 * * * * cd /root/knowledge_os && python3 app/enhanced_orchestrator.py"
echo "   0 */6 * * * cd /root/knowledge_os && python3 app/enhanced_immunity.py"
echo "   */5 * * * * cd /root/knowledge_os && python3 app/enhanced_monitor.py"
echo ""
echo "======================================================================"

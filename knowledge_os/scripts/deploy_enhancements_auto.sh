#!/bin/bash
# Скрипт деплоя всех улучшений Singularity 3.5 на сервер (с автоматическим вводом пароля)

set -e

SERVER="root@185.177.216.15"
SERVER_PASSWORD="u44Ww9NmtQj,XG"
SERVER_PATH="/root/knowledge_os"
LOCAL_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Функция для выполнения SSH команд с паролем
ssh_with_password() {
    expect << EOF
set timeout 30
spawn ssh -o StrictHostKeyChecking=no $SERVER "$1"
expect {
    "password:" {
        send "$SERVER_PASSWORD\r"
        exp_continue
    }
    "Password:" {
        send "$SERVER_PASSWORD\r"
        exp_continue
    }
    "yes/no" {
        send "yes\r"
        exp_continue
    }
    eof
}
EOF
}

# Функция для SCP с паролем
scp_with_password() {
    local src="$1"
    local dst="$2"
    expect << EOF
set timeout 60
spawn scp -o StrictHostKeyChecking=no "$src" "$dst"
expect {
    "password:" {
        send "$SERVER_PASSWORD\r"
        exp_continue
    }
    "Password:" {
        send "$SERVER_PASSWORD\r"
        exp_continue
    }
    "yes/no" {
        send "yes\r"
        exp_continue
    }
    eof
}
EOF
}

echo "🚀 Деплой улучшений Singularity 3.5 на сервер..."
echo ""

# Проверка наличия expect
if ! command -v expect &> /dev/null; then
    echo "❌ expect не установлен"
    echo "💡 Установите: brew install expect (macOS) или apt-get install expect (Linux)"
    exit 1
fi

# Проверка подключения
echo "📡 Проверка подключения к серверу..."
if ssh_with_password "echo 'Connected'" 2>&1 | grep -q "Connected"; then
    echo "✅ Подключение установлено"
else
    echo "❌ Не удалось подключиться к серверу"
    exit 1
fi
echo ""

# Создание директорий на сервере
echo "📁 Создание директорий на сервере..."
ssh_with_password "mkdir -p $SERVER_PATH/app $SERVER_PATH/scripts $SERVER_PATH/dashboard $SERVER_PATH/db/migrations"
echo "✅ Директории созданы"
echo ""

# Деплой файлов мониторинга
echo "📦 Деплой: Мониторинг и бэкапы..."
scp_with_password "$LOCAL_PATH/app/enhanced_monitor.py" "$SERVER:$SERVER_PATH/app/"
scp_with_password "$LOCAL_PATH/scripts/setup_automated_backups.sh" "$SERVER:$SERVER_PATH/scripts/"
scp_with_password "$LOCAL_PATH/scripts/setup_monitoring.sh" "$SERVER:$SERVER_PATH/scripts/"
scp_with_password "$LOCAL_PATH/scripts/setup_all_monitoring.sh" "$SERVER:$SERVER_PATH/scripts/"
scp_with_password "$LOCAL_PATH/scripts/restore_from_backup.sh" "$SERVER:$SERVER_PATH/scripts/"
ssh_with_password "chmod +x $SERVER_PATH/scripts/*.sh"
echo "✅ Мониторинг задеплоен"
echo ""

# Деплой Orchestrator
echo "📦 Деплой: Улучшенный Orchestrator..."
scp_with_password "$LOCAL_PATH/app/enhanced_orchestrator.py" "$SERVER:$SERVER_PATH/app/"
scp_with_password "$LOCAL_PATH/db/migrations/add_tasks_table.sql" "$SERVER:$SERVER_PATH/db/migrations/"
echo "✅ Orchestrator задеплоен"
echo ""

# Деплой поиска
echo "📦 Деплой: Улучшенный поиск..."
scp_with_password "$LOCAL_PATH/app/enhanced_search.py" "$SERVER:$SERVER_PATH/app/"
scp_with_password "$LOCAL_PATH/app/main_enhanced.py" "$SERVER:$SERVER_PATH/app/"
echo "✅ Поиск задеплоен"
echo ""

# Деплой иммунитета
echo "📦 Деплой: Расширенный иммунитет..."
scp_with_password "$LOCAL_PATH/app/enhanced_immunity.py" "$SERVER:$SERVER_PATH/app/"
echo "✅ Иммунитет задеплоен"
echo ""

# Деплой аналитики
echo "📦 Деплой: Аналитика и Dashboard..."
scp_with_password "$LOCAL_PATH/dashboard/enhanced_analytics.py" "$SERVER:$SERVER_PATH/dashboard/"
scp_with_password "$LOCAL_PATH/dashboard/app_enhanced.py" "$SERVER:$SERVER_PATH/dashboard/"
echo "✅ Аналитика задеплоен"
echo ""

# Применение миграции БД
echo "📦 Применение миграции БД..."
ssh_with_password "cd $SERVER_PATH && psql -U admin -d knowledge_os -f db/migrations/add_tasks_table.sql" || echo "⚠️ Миграция требует ручного применения"
echo ""

# Настройка зависимостей
echo "📦 Проверка зависимостей..."
ssh_with_password "cd $SERVER_PATH && pip3 install psutil 2>/dev/null || echo 'psutil уже установлен'"
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

#!/bin/bash
# Скрипт для применения всех миграций БД Singularity 4.5

set -e

SERVER="root@185.177.216.15"
SERVER_PASSWORD="u44Ww9NmtQj,XG"
SERVER_PATH="/root/knowledge_os"
DB_NAME="knowledge_os"
DB_USER="admin"

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

echo "🚀 Применение миграций БД Singularity 4.5..."
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

# Список миграций для применения
MIGRATIONS=(
    "add_tasks_table.sql"
    "add_knowledge_links_table.sql"
    "add_contextual_memory.sql"
    "add_webhooks_table.sql"
    "add_security_tables.sql"
    "add_performance_optimizations.sql"
    "add_multilanguage_support.sql"
)

echo "📦 Применение миграций..."
echo ""

# Найти путь к psql
echo "🔍 Поиск psql..."
PSQL_PATH=$(ssh_with_password "which psql || find /usr -name psql 2>/dev/null | head -1" 2>&1 | grep -v "password:" | grep -v "spawn" | grep -v "expect" | head -1 | tr -d '\r\n')

if [ -z "$PSQL_PATH" ]; then
    echo "⚠️  psql не найден в PATH"
    echo "💡 Попробуем найти в стандартных местах..."
    PSQL_PATH="/usr/bin/psql"
fi

echo "✅ Используем: $PSQL_PATH"
echo ""

# Применить каждую миграцию
SUCCESS_COUNT=0
FAILED_COUNT=0

for migration in "${MIGRATIONS[@]}"; do
    echo "📝 Применение: $migration..."
    
    # Проверяем, существует ли файл миграции
    if ssh_with_password "test -f $SERVER_PATH/db/migrations/$migration" 2>&1 | grep -q "Connected"; then
        # Применяем миграцию
        RESULT=$(ssh_with_password "cd $SERVER_PATH && $PSQL_PATH -U $DB_USER -d $DB_NAME -f db/migrations/$migration 2>&1" 2>&1)
        
        if echo "$RESULT" | grep -qi "error\|failed\|fatal"; then
            echo "❌ Ошибка при применении $migration"
            echo "$RESULT" | grep -i "error\|failed\|fatal" | head -3
            FAILED_COUNT=$((FAILED_COUNT + 1))
        else
            echo "✅ $migration применена успешно"
            SUCCESS_COUNT=$((SUCCESS_COUNT + 1))
        fi
    else
        echo "⚠️  Файл $migration не найден на сервере"
        FAILED_COUNT=$((FAILED_COUNT + 1))
    fi
    echo ""
done

# Итоговая информация
echo "======================================================================"
echo "📊 ИТОГИ ПРИМЕНЕНИЯ МИГРАЦИЙ"
echo "======================================================================"
echo ""
echo "✅ Успешно применено: $SUCCESS_COUNT из ${#MIGRATIONS[@]}"
echo "❌ Ошибок: $FAILED_COUNT"
echo ""

if [ $FAILED_COUNT -eq 0 ]; then
    echo "🎉 Все миграции применены успешно!"
else
    echo "⚠️  Некоторые миграции не были применены"
    echo "💡 Проверьте логи выше и примените вручную при необходимости"
fi

echo ""
echo "======================================================================"
echo "📝 ПРОВЕРКА ТАБЛИЦ В БД"
echo "======================================================================"
echo ""

# Проверка созданных таблиц
TABLES=(
    "tasks"
    "knowledge_links"
    "user_preferences"
    "interaction_patterns"
    "webhooks"
    "users"
    "roles"
    "permissions"
    "audit_logs"
    "knowledge_translations"
    "ui_translations"
    "user_language_preferences"
)

echo "🔍 Проверка таблиц..."
for table in "${TABLES[@]}"; do
    RESULT=$(ssh_with_password "cd $SERVER_PATH && $PSQL_PATH -U $DB_USER -d $DB_NAME -c \"SELECT COUNT(*) FROM $table;\" 2>&1" 2>&1)
    
    if echo "$RESULT" | grep -qi "does not exist\|error\|failed"; then
        echo "❌ Таблица $table не существует"
    else
        COUNT=$(echo "$RESULT" | grep -E "^[[:space:]]*[0-9]+" | head -1 | tr -d ' ')
        echo "✅ Таблица $table существует (записей: $COUNT)"
    fi
done

echo ""
echo "======================================================================"


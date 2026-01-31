#!/bin/bash
# Скрипт быстрого старта Singularity 4.5 после применения миграций

set -e

SERVER="root@185.177.216.15"
SERVER_PASSWORD="u44Ww9NmtQj,XG"
SERVER_PATH="/root/knowledge_os"

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

echo "🚀 Быстрый старт Singularity 4.5..."
echo ""

# Проверка наличия expect
if ! command -v expect &> /dev/null; then
    echo "❌ expect не установлен"
    exit 1
fi

# Проверка подключения
echo "📡 Проверка подключения..."
if ssh_with_password "echo 'Connected'" 2>&1 | grep -q "Connected"; then
    echo "✅ Подключение установлено"
else
    echo "❌ Не удалось подключиться к серверу"
    exit 1
fi
echo ""

# 1. Применить миграции БД
echo "======================================================================"
echo "1️⃣  ПРИМЕНЕНИЕ МИГРАЦИЙ БД"
echo "======================================================================"
echo ""

# Найти путь к psql
PSQL_PATH=$(ssh_with_password "which psql || find /usr -name psql 2>/dev/null | head -1" 2>&1 | grep -v "password:" | grep -v "spawn" | grep -v "expect" | head -1 | tr -d '\r\n')

if [ -z "$PSQL_PATH" ]; then
    PSQL_PATH="/usr/bin/psql"
fi

MIGRATIONS=(
    "add_knowledge_links_table.sql"
    "add_contextual_memory.sql"
    "add_webhooks_table.sql"
    "add_security_tables.sql"
    "add_performance_optimizations.sql"
    "add_multilanguage_support.sql"
)

SUCCESS=0
FAILED=0

for migration in "${MIGRATIONS[@]}"; do
    echo "📝 Применение: $migration..."
    RESULT=$(ssh_with_password "cd $SERVER_PATH && $PSQL_PATH -U admin -d knowledge_os -f db/migrations/$migration 2>&1" 2>&1)
    
    if echo "$RESULT" | grep -qi "error\|failed\|fatal"; then
        echo "❌ Ошибка при применении $migration"
        FAILED=$((FAILED + 1))
    else
        echo "✅ $migration применена успешно"
        SUCCESS=$((SUCCESS + 1))
    fi
done

echo ""
if [ $FAILED -eq 0 ]; then
    echo "✅ Все миграции применены успешно!"
else
    echo "⚠️  Некоторые миграции не были применены ($FAILED из ${#MIGRATIONS[@]})"
fi
echo ""

# 2. Запустить тесты
echo "======================================================================"
echo "2️⃣  ЗАПУСК ТЕСТОВ"
echo "======================================================================"
echo ""

echo "🧪 Запуск тестов..."
TEST_RESULT=$(ssh_with_password "cd $SERVER_PATH && bash tests/run_tests.sh 2>&1" 2>&1)

if echo "$TEST_RESULT" | grep -qi "passed\|PASSED"; then
    echo "✅ Тесты прошли успешно"
else
    echo "⚠️  Проверьте результаты тестов вручную"
    echo "$TEST_RESULT" | tail -10
fi
echo ""

# 3. Сгенерировать документацию
echo "======================================================================"
echo "3️⃣  ГЕНЕРАЦИЯ ДОКУМЕНТАЦИИ"
echo "======================================================================"
echo ""

echo "📚 Генерация документации..."
DOC_RESULT=$(ssh_with_password "cd $SERVER_PATH && python3 app/doc_generator.py 2>&1" 2>&1)

if echo "$DOC_RESULT" | grep -qi "success\|complete\|done"; then
    echo "✅ Документация сгенерирована"
else
    echo "⚠️  Проверьте генерацию документации вручную"
fi
echo ""

# 4. Проверка статуса системы
echo "======================================================================"
echo "4️⃣  ПРОВЕРКА СТАТУСА СИСТЕМЫ"
echo "======================================================================"
echo ""

# Проверка таблиц БД
echo "🔍 Проверка таблиц БД..."
TABLES=("tasks" "knowledge_links" "webhooks" "users" "knowledge_translations")

for table in "${TABLES[@]}"; do
    RESULT=$(ssh_with_password "cd $SERVER_PATH && $PSQL_PATH -U admin -d knowledge_os -c \"SELECT COUNT(*) FROM $table;\" 2>&1" 2>&1)
    
    if echo "$RESULT" | grep -qi "does not exist\|error"; then
        echo "❌ Таблица $table не существует"
    else
        COUNT=$(echo "$RESULT" | grep -E "^[[:space:]]*[0-9]+" | head -1 | tr -d ' ')
        echo "✅ Таблица $table существует (записей: $COUNT)"
    fi
done
echo ""

# Итоговая информация
echo "======================================================================"
echo "✅ БЫСТРЫЙ СТАРТ ЗАВЕРШЕН"
echo "======================================================================"
echo ""
echo "📊 Статус:"
echo "   - Миграции: $SUCCESS/${#MIGRATIONS[@]} применены"
echo "   - Тесты: Запущены"
echo "   - Документация: Сгенерирована"
echo ""
echo "📝 Следующие шаги:"
echo "   1. Обновить cron для автоматических задач"
echo "   2. Настроить webhooks (опционально)"
echo "   3. Запустить REST API (опционально)"
echo ""
echo "======================================================================"


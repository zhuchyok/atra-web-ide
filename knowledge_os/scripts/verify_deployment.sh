#!/bin/bash
# Скрипт для проверки работоспособности всех компонентов Singularity 4.5

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

echo "🔍 Проверка работоспособности Singularity 4.5..."
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

# Счетчики
TOTAL_CHECKS=0
PASSED_CHECKS=0
FAILED_CHECKS=0

# Функция проверки
check_file() {
    local file="$1"
    local description="$2"
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    
    # Проверяем существование файла
    RESULT=$(ssh_with_password "test -f $SERVER_PATH/$file && echo 'EXISTS' || echo 'NOT_FOUND'" 2>&1)
    
    if echo "$RESULT" | grep -q "EXISTS"; then
        # Получаем размер файла
        SIZE=$(ssh_with_password "stat -c%s $SERVER_PATH/$file 2>/dev/null || stat -f%z $SERVER_PATH/$file 2>/dev/null || echo '0'" 2>&1 | grep -E "^[0-9]+" | head -1 | tr -d '\r\n')
        if [ ! -z "$SIZE" ] && [ "$SIZE" != "0" ]; then
            echo "✅ $description ($file) - ${SIZE} bytes"
            PASSED_CHECKS=$((PASSED_CHECKS + 1))
        else
            echo "❌ $description ($file) - файл пуст"
            FAILED_CHECKS=$((FAILED_CHECKS + 1))
        fi
    else
        echo "❌ $description ($file) - файл не найден"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
    fi
}

# Проверка модулей
echo "======================================================================"
echo "📦 ПРОВЕРКА МОДУЛЕЙ"
echo "======================================================================"
echo ""

check_file "app/global_scout.py" "Global Scout"
check_file "app/knowledge_graph.py" "Knowledge Graph"
check_file "app/contextual_learner.py" "Contextual Memory"
check_file "app/enhanced_expert_evolver.py" "Expert Evolution"
check_file "app/webhook_manager.py" "Webhook Manager"
check_file "app/rest_api.py" "REST API"
check_file "app/security.py" "Security"
check_file "app/performance_optimizer.py" "Performance Optimizer"
check_file "app/doc_generator.py" "Documentation Generator"
check_file "app/translator.py" "Translator"
check_file "app/main_enhanced.py" "Main Enhanced"
check_file "app/nightly_learner.py" "Nightly Learner"

echo ""

# Проверка миграций
echo "======================================================================"
echo "📦 ПРОВЕРКА МИГРАЦИЙ БД"
echo "======================================================================"
echo ""

check_file "db/migrations/add_knowledge_links_table.sql" "Knowledge Links Migration"
check_file "db/migrations/add_contextual_memory.sql" "Contextual Memory Migration"
check_file "db/migrations/add_webhooks_table.sql" "Webhooks Migration"
check_file "db/migrations/add_security_tables.sql" "Security Migration"
check_file "db/migrations/add_performance_optimizations.sql" "Performance Migration"
check_file "db/migrations/add_multilanguage_support.sql" "Multilanguage Migration"

echo ""

# Проверка тестов
echo "======================================================================"
echo "📦 ПРОВЕРКА ТЕСТОВ"
echo "======================================================================"
echo ""

check_file "tests/conftest.py" "Test Fixtures"
check_file "tests/test_knowledge_graph.py" "Knowledge Graph Tests"
check_file "tests/test_security.py" "Security Tests"
check_file "tests/test_rest_api.py" "REST API Tests"
check_file "tests/test_performance_optimizer.py" "Performance Tests"
check_file "tests/test_e2e.py" "E2E Tests"
check_file "tests/test_load.py" "Load Tests"
check_file "tests/run_tests.sh" "Test Runner"

echo ""

# Проверка зависимостей Python
echo "======================================================================"
echo "📦 ПРОВЕРКА ЗАВИСИМОСТЕЙ"
echo "======================================================================"
echo ""

TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if ssh_with_password "cd $SERVER_PATH && python3 -c 'import httpx; import asyncpg; print(\"OK\")' 2>&1" 2>&1 | grep -q "OK"; then
    echo "✅ httpx и asyncpg установлены"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
    echo "❌ httpx или asyncpg не установлены"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi

TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
if ssh_with_password "cd $SERVER_PATH && python3 -c 'import pytest; print(\"OK\")' 2>&1" 2>&1 | grep -q "OK"; then
    echo "✅ pytest установлен"
    PASSED_CHECKS=$((PASSED_CHECKS + 1))
else
    echo "⚠️  pytest не установлен (требуется для тестов)"
    FAILED_CHECKS=$((FAILED_CHECKS + 1))
fi

echo ""

# Проверка директорий
echo "======================================================================"
echo "📁 ПРОВЕРКА ДИРЕКТОРИЙ"
echo "======================================================================"
echo ""

DIRS=("app" "db/migrations" "tests" "docs/auto_generated")

for dir in "${DIRS[@]}"; do
    TOTAL_CHECKS=$((TOTAL_CHECKS + 1))
    RESULT=$(ssh_with_password "test -d $SERVER_PATH/$dir && echo 'EXISTS' || echo 'NOT_FOUND'" 2>&1)
    if echo "$RESULT" | grep -q "EXISTS"; then
        COUNT=$(ssh_with_password "ls -1 $SERVER_PATH/$dir 2>/dev/null | wc -l" 2>&1 | grep -E "^[0-9]+" | head -1 | tr -d '\r\n')
        echo "✅ $dir (файлов: $COUNT)"
        PASSED_CHECKS=$((PASSED_CHECKS + 1))
    else
        echo "❌ $dir - директория не найдена"
        FAILED_CHECKS=$((FAILED_CHECKS + 1))
    fi
done

echo ""

# Итоговая статистика
echo "======================================================================"
echo "📊 ИТОГОВАЯ СТАТИСТИКА"
echo "======================================================================"
echo ""
echo "Всего проверок: $TOTAL_CHECKS"
echo "✅ Успешно: $PASSED_CHECKS"
echo "❌ Ошибок: $FAILED_CHECKS"
echo ""

if [ $FAILED_CHECKS -eq 0 ]; then
    echo "🎉 Все компоненты на месте и готовы к работе!"
    echo ""
    echo "📝 Следующие шаги:"
    echo "   1. Применить миграции БД: bash scripts/apply_all_migrations.sh"
    echo "   2. Запустить тесты: bash tests/run_tests.sh"
    echo "   3. Сгенерировать документацию: python3 app/doc_generator.py"
else
    echo "⚠️  Обнаружены проблемы. Проверьте список выше."
fi

echo ""
echo "======================================================================"


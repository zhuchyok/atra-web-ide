#!/bin/bash
# Скрипт деплоя всех улучшений Singularity 4.5 на сервер (улучшения #6-15)

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

echo "🚀 Деплой улучшений Singularity 4.5 (улучшения #6-15) на сервер..."
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
ssh_with_password "mkdir -p $SERVER_PATH/app $SERVER_PATH/db/migrations $SERVER_PATH/tests $SERVER_PATH/docs/auto_generated"
echo "✅ Директории созданы"
echo ""

# --- УЛУЧШЕНИЕ #6: Global Scout ---
echo "📦 Деплой: Улучшение #6 - Global Scout..."
scp_with_password "$LOCAL_PATH/app/global_scout.py" "$SERVER:$SERVER_PATH/app/"
echo "✅ Global Scout задеплоен"
echo ""

# --- УЛУЧШЕНИЕ #7: Knowledge Graph ---
echo "📦 Деплой: Улучшение #7 - Knowledge Graph..."
scp_with_password "$LOCAL_PATH/app/knowledge_graph.py" "$SERVER:$SERVER_PATH/app/"
scp_with_password "$LOCAL_PATH/db/migrations/add_knowledge_links_table.sql" "$SERVER:$SERVER_PATH/db/migrations/"
echo "✅ Knowledge Graph задеплоен"
echo ""

# --- УЛУЧШЕНИЕ #8: Contextual Memory ---
echo "📦 Деплой: Улучшение #8 - Contextual Memory..."
scp_with_password "$LOCAL_PATH/app/contextual_learner.py" "$SERVER:$SERVER_PATH/app/"
scp_with_password "$LOCAL_PATH/db/migrations/add_contextual_memory.sql" "$SERVER:$SERVER_PATH/db/migrations/"
echo "✅ Contextual Memory задеплоен"
echo ""

# --- УЛУЧШЕНИЕ #9: Expert Evolution ---
echo "📦 Деплой: Улучшение #9 - Expert Evolution..."
scp_with_password "$LOCAL_PATH/app/enhanced_expert_evolver.py" "$SERVER:$SERVER_PATH/app/"
echo "✅ Expert Evolution задеплоен"
echo ""

# --- УЛУЧШЕНИЕ #10: Webhooks & REST API ---
echo "📦 Деплой: Улучшение #10 - Webhooks & REST API..."
scp_with_password "$LOCAL_PATH/app/webhook_manager.py" "$SERVER:$SERVER_PATH/app/"
scp_with_password "$LOCAL_PATH/app/rest_api.py" "$SERVER:$SERVER_PATH/app/"
scp_with_password "$LOCAL_PATH/db/migrations/add_webhooks_table.sql" "$SERVER:$SERVER_PATH/db/migrations/"
echo "✅ Webhooks & REST API задеплоен"
echo ""

# --- УЛУЧШЕНИЕ #11: Security ---
echo "📦 Деплой: Улучшение #11 - Security..."
scp_with_password "$LOCAL_PATH/app/security.py" "$SERVER:$SERVER_PATH/app/"
scp_with_password "$LOCAL_PATH/db/migrations/add_security_tables.sql" "$SERVER:$SERVER_PATH/db/migrations/"
echo "✅ Security задеплоен"
echo ""

# --- УЛУЧШЕНИЕ #12: Performance Optimization ---
echo "📦 Деплой: Улучшение #12 - Performance Optimization..."
scp_with_password "$LOCAL_PATH/app/performance_optimizer.py" "$SERVER:$SERVER_PATH/app/"
scp_with_password "$LOCAL_PATH/db/migrations/add_performance_optimizations.sql" "$SERVER:$SERVER_PATH/db/migrations/"
echo "✅ Performance Optimization задеплоен"
echo ""

# --- УЛУЧШЕНИЕ #13: Auto-documentation ---
echo "📦 Деплой: Улучшение #13 - Auto-documentation..."
scp_with_password "$LOCAL_PATH/app/doc_generator.py" "$SERVER:$SERVER_PATH/app/"
ssh_with_password "mkdir -p $SERVER_PATH/docs/auto_generated"
echo "✅ Auto-documentation задеплоен"
echo ""

# --- УЛУЧШЕНИЕ #14: Automated Testing ---
echo "📦 Деплой: Улучшение #14 - Automated Testing..."
scp_with_password "$LOCAL_PATH/tests/__init__.py" "$SERVER:$SERVER_PATH/tests/"
scp_with_password "$LOCAL_PATH/tests/conftest.py" "$SERVER:$SERVER_PATH/tests/"
scp_with_password "$LOCAL_PATH/tests/test_knowledge_graph.py" "$SERVER:$SERVER_PATH/tests/"
scp_with_password "$LOCAL_PATH/tests/test_security.py" "$SERVER:$SERVER_PATH/tests/"
scp_with_password "$LOCAL_PATH/tests/test_rest_api.py" "$SERVER:$SERVER_PATH/tests/"
scp_with_password "$LOCAL_PATH/tests/test_performance_optimizer.py" "$SERVER:$SERVER_PATH/tests/"
scp_with_password "$LOCAL_PATH/tests/test_e2e.py" "$SERVER:$SERVER_PATH/tests/"
scp_with_password "$LOCAL_PATH/tests/test_load.py" "$SERVER:$SERVER_PATH/tests/"
scp_with_password "$LOCAL_PATH/tests/run_tests.sh" "$SERVER:$SERVER_PATH/tests/"
if [ -f "$LOCAL_PATH/pytest.ini" ]; then
    scp_with_password "$LOCAL_PATH/pytest.ini" "$SERVER:$SERVER_PATH/"
fi
ssh_with_password "chmod +x $SERVER_PATH/tests/run_tests.sh"
echo "✅ Automated Testing задеплоен"
echo ""

# --- УЛУЧШЕНИЕ #15: Multilanguage ---
echo "📦 Деплой: Улучшение #15 - Multilanguage..."
scp_with_password "$LOCAL_PATH/app/translator.py" "$SERVER:$SERVER_PATH/app/"
scp_with_password "$LOCAL_PATH/db/migrations/add_multilanguage_support.sql" "$SERVER:$SERVER_PATH/db/migrations/"
echo "✅ Multilanguage задеплоен"
echo ""

# --- ОБНОВЛЕННЫЕ ФАЙЛЫ ---
echo "📦 Деплой: Обновленные файлы..."
scp_with_password "$LOCAL_PATH/app/main_enhanced.py" "$SERVER:$SERVER_PATH/app/"
scp_with_password "$LOCAL_PATH/app/nightly_learner.py" "$SERVER:$SERVER_PATH/app/"
echo "✅ Обновленные файлы задеплоены"
echo ""

# Применение миграций БД
echo "📦 Применение миграций БД..."
echo "⚠️  Миграции требуют ручного применения (psql может быть не в PATH)"
echo ""
echo "Миграции для применения:"
echo "  1. add_knowledge_links_table.sql"
echo "  2. add_contextual_memory.sql"
echo "  3. add_webhooks_table.sql"
echo "  4. add_security_tables.sql"
echo "  5. add_performance_optimizations.sql"
echo "  6. add_multilanguage_support.sql"
echo ""

# Настройка зависимостей
echo "📦 Проверка зависимостей..."
ssh_with_password "cd $SERVER_PATH && pip3 install httpx asyncpg 2>/dev/null || echo 'Зависимости уже установлены'"
echo ""

# Итоговая информация
echo "======================================================================"
echo "✅ ДЕПЛОЙ SINGULARITY 4.5 ЗАВЕРШЕН!"
echo "======================================================================"
echo ""
echo "📋 ЗАДЕПЛОЕНО (улучшения #6-15):"
echo ""
echo "6.  ✅ Global Scout (global_scout.py)"
echo "7.  ✅ Knowledge Graph (knowledge_graph.py + миграция)"
echo "8.  ✅ Contextual Memory (contextual_learner.py + миграция)"
echo "9.  ✅ Expert Evolution (enhanced_expert_evolver.py)"
echo "10. ✅ Webhooks & REST API (webhook_manager.py, rest_api.py + миграция)"
echo "11. ✅ Security (security.py + миграция)"
echo "12. ✅ Performance Optimization (performance_optimizer.py + миграция)"
echo "13. ✅ Auto-documentation (doc_generator.py)"
echo "14. ✅ Automated Testing (tests/ + pytest.ini)"
echo "15. ✅ Multilanguage (translator.py + миграция)"
echo ""
echo "📝 ОБНОВЛЕННЫЕ ФАЙЛЫ:"
echo "   - main_enhanced.py (интеграция всех улучшений)"
echo "   - nightly_learner.py (ФАЗА 8: Auto-Translation)"
echo ""
echo "======================================================================"
echo "📝 СЛЕДУЮЩИЕ ШАГИ:"
echo ""
echo "1. Применить миграции БД:"
echo "   ssh $SERVER"
echo "   cd /root/knowledge_os"
echo "   psql -U admin -d knowledge_os -f db/migrations/add_knowledge_links_table.sql"
echo "   psql -U admin -d knowledge_os -f db/migrations/add_contextual_memory.sql"
echo "   psql -U admin -d knowledge_os -f db/migrations/add_webhooks_table.sql"
echo "   psql -U admin -d knowledge_os -f db/migrations/add_security_tables.sql"
echo "   psql -U admin -d knowledge_os -f db/migrations/add_performance_optimizations.sql"
echo "   psql -U admin -d knowledge_os -f db/migrations/add_multilanguage_support.sql"
echo ""
echo "2. Запустить тесты:"
echo "   ssh $SERVER"
echo "   cd /root/knowledge_os"
echo "   bash tests/run_tests.sh"
echo ""
echo "3. Сгенерировать документацию:"
echo "   ssh $SERVER"
echo "   cd /root/knowledge_os"
echo "   python3 app/doc_generator.py"
echo ""
echo "4. Обновить cron для новых задач:"
echo "   ssh $SERVER"
echo "   crontab -e"
echo "   # Добавить:"
echo "   # Global Scout (каждые 12 часов)"
echo "   0 */12 * * * cd /root/knowledge_os && python3 app/global_scout.py"
echo "   # Auto-Translation (каждые 24 часа)"
echo "   0 2 * * * cd /root/knowledge_os && python3 -c 'from app.translator import run_auto_translation_cycle; import asyncio; asyncio.run(run_auto_translation_cycle())'"
echo ""
echo "======================================================================"

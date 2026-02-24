#!/bin/bash
# Настройка автоматического обновления .cursorrules

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

echo "🔧 Настройка автоматического обновления .cursorrules..."
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

# Задача обновления .cursorrules (после nightly_learner, в 4:00)
echo "======================================================================"
echo "📝 НАСТРОЙКА АВТОМАТИЧЕСКОГО ОБНОВЛЕНИЯ .CURSORRULES"
echo "======================================================================"
echo ""

CURSORRULES_SCRIPT="$SERVER_PATH/app/cursorrules_generator.py"
CRON_CURSORRULES="0 4 * * * cd $SERVER_PATH && python3 app/cursorrules_generator.py >> logs/cursorrules_update.log 2>&1"

# Проверяем и добавляем задачу
RESULT=$(ssh_with_password "crontab -l 2>/dev/null | grep -q 'cursorrules_generator' && echo 'EXISTS' || echo 'NOT_FOUND'" 2>&1)

if echo "$RESULT" | grep -q "EXISTS"; then
    echo "✅ Задача автоматического обновления .cursorrules уже настроена"
else
    ssh_with_password "(crontab -l 2>/dev/null; echo '$CRON_CURSORRULES') | crontab -" 2>&1 > /dev/null
    echo "✅ Задача автоматического обновления .cursorrules добавлена (ежедневно в 4:00)"
    echo "   📝 .cursorrules будет обновляться автоматически после nightly_learner"
fi
echo ""

# Итоговая информация
echo "======================================================================"
echo "✅ НАСТРОЙКА ЗАВЕРШЕНА!"
echo "======================================================================"
echo ""
echo "📝 .cursorrules будет обновляться:"
echo "   - Автоматически через nightly_learner (ФАЗА 9)"
echo "   - Отдельно в cron (ежедневно в 4:00)"
echo ""
echo "📊 Что обновляется:"
echo "   - Список экспертов из БД"
echo "   - Уровни экспертов (на основе знаний и метрик)"
echo "   - Обязанности экспертов"
echo "   - Топ знаний каждого эксперта"
echo "   - Домены знаний"
echo "   - Статистика (количество экспертов, знаний и т.д.)"
echo ""
echo "🧪 Тестовый запуск:"
echo "   ssh $SERVER"
echo "   cd $SERVER_PATH && python3 app/cursorrules_generator.py"
echo ""
echo "📝 Логи:"
echo "   - $SERVER_PATH/logs/cursorrules_update.log"
echo ""
echo "======================================================================"

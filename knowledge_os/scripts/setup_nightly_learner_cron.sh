#!/bin/bash
# Настройка ежедневного запуска nightly_learner для обучения всех экспертов

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

echo "🔧 Настройка ежедневного обучения всех экспертов..."
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

# Задача ежедневного обучения (ежедневно в 3:00)
echo "======================================================================"
echo "📚 НАСТРОЙКА ЕЖЕДНЕВНОГО ОБУЧЕНИЯ ЭКСПЕРТОВ"
echo "======================================================================"
echo ""

NIGHTLY_LEARNER_SCRIPT="$SERVER_PATH/app/nightly_learner.py"
CRON_NIGHTLY_LEARNER="0 3 * * * cd $SERVER_PATH && python3 app/nightly_learner.py >> logs/nightly_learner.log 2>&1"

# Проверяем и добавляем задачу
RESULT=$(ssh_with_password "crontab -l 2>/dev/null | grep -q 'nightly_learner.py' && echo 'EXISTS' || echo 'NOT_FOUND'" 2>&1)

if echo "$RESULT" | grep -q "EXISTS"; then
    echo "✅ Задача ежедневного обучения уже настроена"
else
    ssh_with_password "(crontab -l 2>/dev/null; echo '$CRON_NIGHTLY_LEARNER') | crontab -" 2>&1 > /dev/null
    echo "✅ Задача ежедневного обучения добавлена (ежедневно в 3:00)"
    echo "   📚 Все активные эксперты будут обучаться каждый день"
fi
echo ""

# Итоговая информация
echo "======================================================================"
echo "✅ НАСТРОЙКА ЗАВЕРШЕНА!"
echo "======================================================================"
echo ""
echo "📚 ЕЖЕДНЕВНОЕ ОБУЧЕНИЕ:"
echo "   - Время: ежедневно в 3:00 UTC"
echo "   - Скрипт: nightly_learner.py"
echo "   - Что делает:"
echo "     ✅ Обучает ВСЕХ активных экспертов"
echo "     ✅ Пропускает экспертов, которые обучались < 24 часов назад"
echo "     ✅ Определяет пробелы в знаниях каждого эксперта"
echo "     ✅ Исследует новые технологии и тренды"
echo "     ✅ Сохраняет знания в БД"
echo "     ✅ Запускает Совет Экспертов для важных знаний"
echo "     ✅ Обновляет last_learned_at для каждого эксперта"
echo ""
echo "📊 СТАТИСТИКА:"
echo "   - Всего экспертов в БД: (определяется автоматически)"
echo "   - Активных экспертов: (определяется автоматически)"
echo "   - Обучается каждый день: все активные (кто не обучался < 24ч)"
echo ""
echo "🧪 Тестовый запуск:"
echo "   ssh $SERVER"
echo "   cd $SERVER_PATH && python3 app/nightly_learner.py"
echo ""
echo "📝 Логи:"
echo "   - $SERVER_PATH/logs/nightly_learner.log"
echo ""
echo "======================================================================"

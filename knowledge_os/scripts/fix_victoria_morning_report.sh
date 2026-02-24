#!/bin/bash
# Скрипт для проверки и исправления утреннего отчета Виктории

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

echo "🔧 Проверка и исправление утреннего отчета Виктории..."
echo ""

# Проверка наличия expect
if ! command -v expect &> /dev/null; then
    echo "❌ expect не установлен. Установите: brew install expect (macOS) или apt-get install expect (Linux)"
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

# 1. Проверка cron задачи
echo "======================================================================"
echo "1️⃣  ПРОВЕРКА CRON ЗАДАЧИ"
echo "======================================================================"
echo ""

CRON_CHECK=$(ssh_with_password "crontab -l 2>/dev/null | grep -E 'victoria_morning_report'" 2>&1)

if echo "$CRON_CHECK" | grep -q "victoria_morning_report"; then
    echo "✅ Cron задача найдена:"
    echo "$CRON_CHECK" | grep -v "password:" | grep -v "spawn" | grep "victoria_morning_report"
else
    echo "❌ Cron задача не найдена!"
    echo ""
    echo "📋 Добавление cron задачи..."

    MORNING_REPORT_SCRIPT="$SERVER_PATH/app/victoria_morning_report.py"
    CRON_MORNING_REPORT="0 8 * * * cd $SERVER_PATH && python3 $MORNING_REPORT_SCRIPT >> logs/morning_report.log 2>&1"

    ssh_with_password "(crontab -l 2>/dev/null; echo '$CRON_MORNING_REPORT') | crontab -" 2>&1 > /dev/null
    echo "✅ Cron задача добавлена (ежедневно в 8:00)"
fi
echo ""

# 2. Проверка файла скрипта
echo "======================================================================"
echo "2️⃣  ПРОВЕРКА ФАЙЛА СКРИПТА"
echo "======================================================================"
echo ""

SCRIPT_CHECK=$(ssh_with_password "test -f $SERVER_PATH/app/victoria_morning_report.py && echo 'EXISTS' || echo 'NOT_FOUND'" 2>&1)

if echo "$SCRIPT_CHECK" | grep -q "EXISTS"; then
    echo "✅ Файл скрипта существует: $SERVER_PATH/app/victoria_morning_report.py"
else
    echo "❌ Файл скрипта не найден: $SERVER_PATH/app/victoria_morning_report.py"
    echo "⚠️  Нужно задеплоить файл на сервер"
fi
echo ""

# 3. Проверка логов
echo "======================================================================"
echo "3️⃣  ПРОВЕРКА ЛОГОВ"
echo "======================================================================"
echo ""

LOG_FILE="$SERVER_PATH/logs/morning_report.log"
LOG_CHECK=$(ssh_with_password "tail -20 $LOG_FILE 2>/dev/null || echo 'LOG_NOT_FOUND'" 2>&1)

if echo "$LOG_CHECK" | grep -q "LOG_NOT_FOUND"; then
    echo "⚠️  Лог файл не найден (это нормально, если скрипт еще не запускался)"
else
    echo "📋 Последние 20 строк лога:"
    echo "$LOG_CHECK" | grep -v "password:" | grep -v "spawn" | tail -20
fi
echo ""

# 4. Тестовый запуск
echo "======================================================================"
echo "4️⃣  ТЕСТОВЫЙ ЗАПУСК"
echo "======================================================================"
echo ""

read -p "Запустить тестовый запуск скрипта сейчас? (y/N): " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "🚀 Запуск тестового выполнения..."
    TEST_RESULT=$(ssh_with_password "cd $SERVER_PATH && python3 app/victoria_morning_report.py 2>&1" 2>&1)

    echo "📋 Результат:"
    echo "$TEST_RESULT" | grep -v "password:" | grep -v "spawn" | tail -30

    if echo "$TEST_RESULT" | grep -q "✅"; then
        echo ""
        echo "✅ Тестовый запуск успешен!"
    else
        echo ""
        echo "⚠️  Возможны ошибки в тестовом запуске. Проверьте логи выше."
    fi
else
    echo "⏭️  Тестовый запуск пропущен"
fi
echo ""

# 5. Итоговая информация
echo "======================================================================"
echo "✅ ПРОВЕРКА ЗАВЕРШЕНА"
echo "======================================================================"
echo ""
echo "📋 Следующие шаги:"
echo ""
echo "1. Проверить cron задачу вручную:"
echo "   ssh $SERVER"
echo "   crontab -l | grep victoria_morning_report"
echo ""
echo "2. Проверить логи:"
echo "   ssh $SERVER"
echo "   tail -f $SERVER_PATH/logs/morning_report.log"
echo ""
echo "3. Запустить вручную для теста:"
echo "   ssh $SERVER"
echo "   cd $SERVER_PATH && python3 app/victoria_morning_report.py"
echo ""
echo "4. Проверить время следующего запуска:"
echo "   ssh $SERVER"
echo "   crontab -l | grep victoria_morning_report"
echo "   # Задача запускается ежедневно в 8:00 UTC"
echo ""
echo "======================================================================"

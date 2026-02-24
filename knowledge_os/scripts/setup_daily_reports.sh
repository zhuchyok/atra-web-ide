#!/bin/bash
# Настройка ежедневных отчетов и бэкапов для Knowledge OS

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

echo "🔧 Настройка ежедневных отчетов и бэкапов..."
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

# 1. Настройка ежедневных бэкапов (ежедневно в 3:00)
echo "======================================================================"
echo "1️⃣  НАСТРОЙКА ЕЖЕДНЕВНЫХ БЭКАПОВ"
echo "======================================================================"
echo ""

BACKUP_SCRIPT="$SERVER_PATH/scripts/backup_db.sh"
CRON_BACKUP="0 3 * * * bash $BACKUP_SCRIPT >> $SERVER_PATH/logs/cron_backup.log 2>&1"

# Проверяем и добавляем задачу бэкапа
RESULT=$(ssh_with_password "crontab -l 2>/dev/null | grep -q 'backup_db.sh' && echo 'EXISTS' || echo 'NOT_FOUND'" 2>&1)

if echo "$RESULT" | grep -q "EXISTS"; then
    echo "✅ Задача ежедневного бэкапа уже настроена"
else
    ssh_with_password "(crontab -l 2>/dev/null; echo '$CRON_BACKUP') | crontab -" 2>&1 > /dev/null
    echo "✅ Задача ежедневного бэкапа добавлена (ежедневно в 3:00)"
    echo "   📦 Бэкапы будут отправляться в Telegram автоматически"
fi
echo ""

# 2. Настройка утреннего отчета Викторияии (ежедневно в 8:00)
echo "======================================================================"
echo "2️⃣  НАСТРОЙКА УТРЕННЕГО ОТЧЕТА ВИКТОРИИ"
echo "======================================================================"
echo ""

MORNING_REPORT_SCRIPT="$SERVER_PATH/app/victoria_morning_report.py"
CRON_MORNING_REPORT="0 8 * * * cd $SERVER_PATH && python3 $MORNING_REPORT_SCRIPT >> logs/morning_report.log 2>&1"

# Проверяем и добавляем задачу утреннего отчета
RESULT=$(ssh_with_password "crontab -l 2>/dev/null | grep -q 'victoria_morning_report' && echo 'EXISTS' || echo 'NOT_FOUND'" 2>&1)

if echo "$RESULT" | grep -q "EXISTS"; then
    echo "✅ Задача утреннего отчета уже настроена"
else
    ssh_with_password "(crontab -l 2>/dev/null; echo '$CRON_MORNING_REPORT') | crontab -" 2>&1 > /dev/null
    echo "✅ Задача утреннего отчета добавлена (ежедневно в 8:00)"
    echo "   📊 Отчет будет отправляться в Telegram автоматически"
fi
echo ""

# 3. Настройка ежедневных webhook отчетов (ежедневно в 20:00)
echo "======================================================================"
echo "3️⃣  НАСТРОЙКА ЕЖЕДНЕВНЫХ WEBHOOK ОТЧЕТОВ"
echo "======================================================================"
echo ""

WEBHOOK_REPORT_SCRIPT="$SERVER_PATH/app/webhook_manager.py"
CRON_WEBHOOK_REPORT="0 20 * * * cd $SERVER_PATH && python3 -c 'from app.webhook_manager import run_webhook_reports; import asyncio; asyncio.run(run_webhook_reports())' >> logs/webhook_reports.log 2>&1"

# Проверяем и добавляем задачу webhook отчетов
RESULT=$(ssh_with_password "crontab -l 2>/dev/null | grep -q 'run_webhook_reports' && echo 'EXISTS' || echo 'NOT_FOUND'" 2>&1)

if echo "$RESULT" | grep -q "EXISTS"; then
    echo "✅ Задача webhook отчетов уже настроена"
else
    ssh_with_password "(crontab -l 2>/dev/null; echo '$CRON_WEBHOOK_REPORT') | crontab -" 2>&1 > /dev/null
    echo "✅ Задача webhook отчетов добавлена (ежедневно в 20:00)"
    echo "   📊 Отчеты будут отправляться через настроенные webhooks"
fi
echo ""

# 4. Показать все настроенные задачи
echo "======================================================================"
echo "📋 НАСТРОЕННЫЕ ЗАДАЧИ CRON"
echo "======================================================================"
echo ""

CRON_JOBS=$(ssh_with_password "crontab -l 2>/dev/null | grep -E '(backup|victoria_morning_report|webhook|knowledge_os)'" 2>&1)

if [ ! -z "$CRON_JOBS" ]; then
    echo "$CRON_JOBS" | grep -v "password:" | grep -v "spawn" | while read -r line; do
        if [ ! -z "$line" ]; then
            echo "  ✅ $line"
        fi
    done
else
    echo "  (нет задач)"
fi

echo ""
echo "======================================================================"
echo "✅ НАСТРОЙКА ЕЖЕДНЕВНЫХ ОТЧЕТОВ И БЭКАПОВ ЗАВЕРШЕНА!"
echo "======================================================================"
echo ""
echo "📊 РАСПИСАНИЕ ОТЧЕТОВ:"
echo ""
echo "  🌙 Бэкапы БД:"
echo "     - Время: ежедневно в 3:00"
echo "     - Куда: Telegram (CHAT_ID: 556251171)"
echo "     - Что: SQL дамп базы данных (сжатый)"
echo ""
echo "  🌅 Утренний отчет Викторияии:"
echo "     - Время: ежедневно в 8:00"
echo "     - Куда: Telegram (CHAT_ID: 556251171)"
echo "     - Что: Стратегический доклад с OKR, ROI, новыми знаниями"
echo ""
echo "  🌆 Вечерний webhook отчет:"
echo "     - Время: ежедневно в 20:00"
echo "     - Куда: Настроенные webhooks (Slack, Discord, Telegram)"
echo "     - Что: Статистика за день (новые знания, задачи, взаимодействия)"
echo ""
echo "======================================================================"
echo "📝 ПРОВЕРКА:"
echo ""
echo "Просмотреть текущие задачи:"
echo "  ssh $SERVER"
echo "  crontab -l | grep -E '(backup|victoria|webhook)'"
echo ""
echo "Тестовый запуск бэкапа:"
echo "  ssh $SERVER"
echo "  bash $SERVER_PATH/scripts/backup_db.sh"
echo ""
echo "Тестовый запуск утреннего отчета:"
echo "  ssh $SERVER"
echo "  cd $SERVER_PATH && python3 app/victoria_morning_report.py"
echo ""
echo "Логи:"
echo "  - Бэкапы: $SERVER_PATH/logs/cron_backup.log"
echo "  - Утренние отчеты: $SERVER_PATH/logs/morning_report.log"
echo "  - Webhook отчеты: $SERVER_PATH/logs/webhook_reports.log"
echo ""
echo "======================================================================"

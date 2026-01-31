#!/bin/bash
# Скрипт для деплоя на сервер через SSH с автоматическим вводом пароля

set -e

SERVER="root@185.177.216.15"
PASSWORD="u44Ww9NmtQj,XG"
REMOTE_DIR="/root/atra"
SCRIPT_NAME="update_and_check_bot.sh"

echo "=================================================================================="
echo "👥 КОМАНДА ИЗ 13 ЭКСПЕРТОВ - ДЕПЛОЙ НА СЕРВЕР"
echo "=================================================================================="
echo ""

# Проверяем наличие expect
if ! command -v expect &> /dev/null; then
    echo "❌ expect не установлен. Установите: brew install expect (macOS) или apt-get install expect (Linux)"
    exit 1
fi

# Создаем временный expect скрипт
EXPECT_SCRIPT=$(mktemp)
cat > $EXPECT_SCRIPT << 'EXPEOF'
#!/usr/bin/expect -f
set timeout 30
set server [lindex $argv 0]
set password [lindex $argv 1]
set remote_dir [lindex $argv 2]
set script_name [lindex $argv 3]

# Копируем скрипт
spawn scp scripts/$script_name $server:$remote_dir/
expect {
    "password:" {
        send "$password\r"
        exp_continue
    }
    "yes/no" {
        send "yes\r"
        exp_continue
    }
    eof
}

# Запускаем скрипт на сервере
spawn ssh $server "cd $remote_dir && chmod +x $script_name && ./$script_name"
expect {
    "password:" {
        send "$password\r"
        exp_continue
    }
    "yes/no" {
        send "yes\r"
        exp_continue
    }
    eof
}

wait
EXPEOF

chmod +x $EXPECT_SCRIPT

# Запускаем expect скрипт
echo "📤 Копируем скрипт на сервер..."
$EXPECT_SCRIPT $SERVER "$PASSWORD" $REMOTE_DIR $SCRIPT_NAME

# Удаляем временный файл
rm -f $EXPECT_SCRIPT

echo ""
echo "=================================================================================="
echo "✅ ДЕПЛОЙ ЗАВЕРШЕН"
echo "=================================================================================="


#!/bin/bash

# Скрипт для загрузки файлов на сервер
# Автоматически загружает все необходимые файлы

SERVER_IP="185.177.216.15"
SERVER_USER="root"
SERVER_PASSWORD="u44Ww9NmtQj,XG"
SERVER_PATH="/root/atra"

echo "📤 Загрузка файлов на сервер"
echo "============================"

# Функция для загрузки файла
upload_file() {
    local file="$1"
    echo "📤 Загрузка $file..."

    expect << EOF
spawn scp -o StrictHostKeyChecking=no $file $SERVER_USER@$SERVER_IP:$SERVER_PATH/
expect "password:"
send "$SERVER_PASSWORD\r"
expect eof
EOF

    if [ $? -eq 0 ]; then
        echo "✅ $file загружен успешно"
    else
        echo "❌ Ошибка загрузки $file"
    fi
}

# Загружаем все необходимые файлы
upload_file "check_database_structure.py"
upload_file "check_telegram_bot.py"
upload_file "fix_server_complete.py"
upload_file "manual_dca_fix.py"
upload_file "update_server_dca_fix.py"
upload_file "quick_server_update.sh"

echo ""
echo "✅ Все файлы загружены на сервер!"
echo ""
echo "Теперь подключитесь к серверу и выполните:"
echo "ssh root@185.177.216.15"
echo "cd /root/atra"
echo "python3 fix_server_complete.py"

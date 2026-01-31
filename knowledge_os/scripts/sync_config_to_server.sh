#!/bin/bash

# Синхронизация config.py на сервер

SERVER_IP="185.177.216.15"
SERVER_USER="root"
SERVER_PASSWORD="u44Ww9NmtQj,XG"
SERVER_PATH="/root/atra"

echo "🔄 Синхронизация config.py на сервер"
echo "===================================="
echo ""

# Загружаем config.py
echo "📤 Загрузка config.py..."
expect << EOF
spawn scp -o StrictHostKeyChecking=no config.py $SERVER_USER@$SERVER_IP:$SERVER_PATH/
expect "password:"
send "$SERVER_PASSWORD\r"
expect eof
EOF

if [ $? -eq 0 ]; then
    echo "✅ config.py загружен успешно"
else
    echo "❌ Ошибка загрузки config.py"
    exit 1
fi

echo ""
echo "✅ Конфигурация синхронизирована!"
echo ""
echo "🔄 Перезапустите бота:"
echo "./restart_bot_on_server.sh"


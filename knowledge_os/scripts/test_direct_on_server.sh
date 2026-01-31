#!/bin/bash

# Скрипт для прямого тестирования дашборда на сервере
# Тестирует функцию получения сигналов напрямую

SERVER_IP="185.177.216.15"
SERVER_USER="root"
SERVER_PASSWORD="u44Ww9NmtQj,XG"
SERVER_PATH="/root/atra"

echo "🧪 Прямое тестирование дашборда на сервере"
echo "=========================================="

# Загружаем скрипт тестирования
echo "📤 Загрузка скрипта тестирования..."

expect << EOF
spawn scp -o StrictHostKeyChecking=no test_dashboard_direct.py $SERVER_USER@$SERVER_IP:$SERVER_PATH/
expect "password:"
send "$SERVER_PASSWORD\r"
expect eof
EOF

# Выполняем тестирование на сервере
expect << EOF
spawn ssh -o StrictHostKeyChecking=no $SERVER_USER@$SERVER_IP
expect "password:"
send "$SERVER_PASSWORD\r"
expect "# "

# Переходим в директорию проекта
send "cd $SERVER_PATH\r"
expect "# "

# Выполняем прямое тестирование
send "python3 test_dashboard_direct.py\r"
expect "# "

# Выходим
send "exit\r"
expect eof
EOF

echo ""
echo "✅ Прямое тестирование завершено!"

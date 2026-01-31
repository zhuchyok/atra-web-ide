#!/bin/bash

# Скрипт для проверки данных дашборда на сервере
# Проверяет, что именно возвращает дашборд и почему пусто

SERVER_IP="185.177.216.15"
SERVER_USER="root"
SERVER_PASSWORD="u44Ww9NmtQj,XG"
SERVER_PATH="/root/atra"

echo "🔍 Проверка данных дашборда на сервере"
echo "====================================="

# Загружаем скрипт проверки
echo "📤 Загрузка скрипта проверки..."

expect << EOF
spawn scp -o StrictHostKeyChecking=no check_dashboard_data.py $SERVER_USER@$SERVER_IP:$SERVER_PATH/
expect "password:"
send "$SERVER_PASSWORD\r"
expect eof
EOF

# Выполняем проверку на сервере
expect << EOF
spawn ssh -o StrictHostKeyChecking=no $SERVER_USER@$SERVER_IP
expect "password:"
send "$SERVER_PASSWORD\r"
expect "# "

# Переходим в директорию проекта
send "cd $SERVER_PATH\r"
expect "# "

# Выполняем проверку данных
send "python3 check_dashboard_data.py\r"
expect "# "

# Проверяем статус дашборда
send "ps aux | grep dashboard\r"
expect "# "

# Проверяем логи дашборда
send "cd web && tail -n 10 dashboard.log\r"
expect "# "

# Выходим
send "exit\r"
expect eof
EOF

echo ""
echo "✅ Проверка данных завершена!"

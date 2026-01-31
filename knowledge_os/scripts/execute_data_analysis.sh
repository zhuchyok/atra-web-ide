#!/bin/bash

# Скрипт для выполнения детального анализа данных дашборда на сервере
# Анализирует все источники данных и определяет правильный

SERVER_IP="185.177.216.15"
SERVER_USER="root"
SERVER_PASSWORD="u44Ww9NmtQj,XG"
SERVER_PATH="/root/atra"

echo "🔍 Детальный анализ данных дашборда на сервере"
echo "=============================================="

# Загружаем скрипт анализа
echo "📤 Загрузка скрипта анализа..."

expect << EOF
spawn scp -o StrictHostKeyChecking=no analyze_dashboard_data.py $SERVER_USER@$SERVER_IP:$SERVER_PATH/
expect "password:"
send "$SERVER_PASSWORD\r"
expect eof
EOF

# Выполняем анализ на сервере
expect << EOF
spawn ssh -o StrictHostKeyChecking=no $SERVER_USER@$SERVER_IP
expect "password:"
send "$SERVER_PASSWORD\r"
expect "# "

# Переходим в директорию проекта
send "cd $SERVER_PATH\r"
expect "# "

# Выполняем детальный анализ
send "python3 analyze_dashboard_data.py\r"
expect "# "

# Выходим
send "exit\r"
expect eof
EOF

echo ""
echo "✅ Анализ данных завершен!"
echo "📊 Проверьте результаты выше для определения правильного источника данных"

#!/bin/bash

# Скрипт для проверки состояния дашборда

SERVER_IP="185.177.216.15"
SERVER_USER="root"
SERVER_PASSWORD="u44Ww9NmtQj,XG"
SERVER_PATH="/root/atra"

echo "🔍 Проверка состояния дашборда"
echo "============================="

expect << EOF
spawn ssh -o StrictHostKeyChecking=no $SERVER_USER@$SERVER_IP
expect "password:"
send "$SERVER_PASSWORD\r"
expect "# "

# Проверяем процесс дашборда
send "echo '🔍 Проверка процесса дашборда:'\r"
expect "# "
send "ps aux | grep dashboard | grep -v grep\r"
expect "# "

# Проверяем порт 5000
send "echo '\\n🔍 Проверка порта 5000:'\r"
expect "# "
send "netstat -tulpn | grep :5000 || echo 'Порт 5000 не слушается'\r"
expect "# "

# Проверяем логи дашборда
send "echo '\\n📋 Последние логи дашборда:'\r"
expect "# "
send "cd $SERVER_PATH/web && tail -n 20 dashboard.log 2>/dev/null || echo 'Нет лог-файла'\r"
expect "# "

# Проверяем существование файла dashboard.py
send "echo '\\n📁 Проверка файла dashboard.py:'\r"
expect "# "
send "ls -lh $SERVER_PATH/web/dashboard.py\r"
expect "# "

# Проверяем базу данных
send "echo '\\n💾 Проверка базы данных:'\r"
expect "# "
send "ls -lh $SERVER_PATH/trading.db\r"
expect "# "

# Проверяем доступность локально
send "echo '\\n🌐 Тест локального доступа:'\r"
expect "# "
send "curl -s http://localhost:5000/api/stats 2>&1 | head -5 || echo 'API недоступен'\r"
expect "# "

# Выходим
send "exit\r"
expect eof
EOF

echo ""
echo "✅ Проверка завершена"

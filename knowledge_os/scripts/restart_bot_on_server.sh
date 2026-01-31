#!/bin/bash

# Скрипт для перезапуска бота на сервере после исправлений

SERVER_IP="185.177.216.15"
SERVER_USER="root"
SERVER_PASSWORD="u44Ww9NmtQj,XG"
SERVER_PATH="/root/atra"

echo "🔄 Перезапуск бота на сервере"
echo "=============================="
echo ""

expect << EOF
spawn ssh -o StrictHostKeyChecking=no $SERVER_USER@$SERVER_IP
expect "password:"
send "$SERVER_PASSWORD\r"
expect "# "
send "cd $SERVER_PATH\r"
expect "# "
send "pkill -f main.py\r"
expect "# "
sleep 2
send "nohup python3 main.py > /dev/null 2>&1 &\r"
expect "# "
send "echo '✅ Бот перезапущен'\r"
expect "# "
send "ps aux | grep main.py | grep -v grep\r"
expect "# "
send "exit\r"
expect eof
EOF

echo ""
echo "✅ Бот перезапущен на сервере"
echo ""
echo "Проверить статус бота можно командой:"
echo "ssh root@$SERVER_IP 'ps aux | grep main.py | grep -v grep'"


#!/bin/bash

# Скрипт для перезапуска дашборда

SERVER_IP="185.177.216.15"
SERVER_USER="root"
SERVER_PASSWORD="u44Ww9NmtQj,XG"
SERVER_PATH="/root/atra"

echo "🔄 Перезапуск дашборда"
echo "====================="

expect << EOF
spawn ssh -o StrictHostKeyChecking=no $SERVER_USER@$SERVER_IP
expect "password:"
send "$SERVER_PASSWORD\r"
expect "# "

# Переходим в директорию проекта
send "cd $SERVER_PATH/web\r"
expect "# "

# Останавливаем старый процесс
send "echo '🛑 Останавливаем старый процесс...'\r"
expect "# "
send "pkill -f 'dashboard.py' || echo 'Процесс не найден'\r"
expect "# "

# Ждем немного
send "sleep 2\r"
expect "# "

# Проверяем, что процесс остановлен
send "ps aux | grep dashboard | grep -v grep || echo 'Процесс остановлен'\r"
expect "# "

# Запускаем новый процесс
send "echo '\\n🚀 Запускаем новый процесс...'\r"
expect "# "
send "nohup python3 dashboard.py > dashboard.log 2>&1 &\r"
expect "# "

# Ждем запуска
send "sleep 5\r"
expect "# "

# Проверяем, что процесс запущен
send "echo '\\n✅ Проверка процесса:'\r"
expect "# "
send "ps aux | grep dashboard | grep -v grep\r"
expect "# "

# Проверяем доступность API
send "echo '\\n🌐 Тест API:'\r"
expect "# "
send "curl -s http://localhost:5000/api/stats | head -10\r"
expect "# "

# Проверяем главную страницу
send "echo '\\n📊 Тест главной страницы:'\r"
expect "# "
send "curl -s http://localhost:5000/ | head -10\r"
expect "# "

# Проверяем последние логи
send "echo '\\n📋 Последние логи:'\r"
expect "# "
send "tail -n 10 dashboard.log\r"
expect "# "

# Выходим
send "exit\r"
expect eof
EOF

echo ""
echo "✅ Перезапуск завершен"
echo "🌐 Откройте в браузере: http://$SERVER_IP:5000"

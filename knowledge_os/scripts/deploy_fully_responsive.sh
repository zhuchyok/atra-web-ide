#!/bin/bash

# Скрипт для развертывания полностью адаптивного дашборда

SERVER_IP="185.177.216.15"
SERVER_USER="root"
SERVER_PASSWORD="u44Ww9NmtQj,XG"
SERVER_PATH="/root/atra"

echo "📱 Развертывание полностью адаптивного дашборда"
echo "============================================="

# Загружаем скрипт исправления
echo "📤 Загрузка скрипта исправления адаптивности..."

expect << EOF
spawn scp -o StrictHostKeyChecking=no fix_dashboard_fully_responsive.py $SERVER_USER@$SERVER_IP:$SERVER_PATH/
expect "password:"
send "$SERVER_PASSWORD\r"
expect eof
EOF

# Исправляем и перезапускаем дашборд
expect << EOF
spawn ssh -o StrictHostKeyChecking=no $SERVER_USER@$SERVER_IP
expect "password:"
send "$SERVER_PASSWORD\r"
expect "# "

# Переходим в директорию проекта
send "cd $SERVER_PATH\r"
expect "# "

# Останавливаем дашборд
send "echo '🛑 Останавливаем дашборд...'\r"
expect "# "
send "pkill -f 'dashboard.py' || true\r"
expect "# "

send "sleep 2\r"
expect "# "

# Применяем полную адаптивность
send "echo '\\n📱 Применяем полную адаптивность...'\r"
expect "# "
send "python3 fix_dashboard_fully_responsive.py\r"
expect "# "

# Запускаем дашборд
send "echo '\\n🚀 Запускаем дашборд...'\r"
expect "# "
send "cd web\r"
expect "# "
send "nohup python3 dashboard.py > dashboard.log 2>&1 &\r"
expect "# "

send "sleep 5\r"
expect "# "

# Проверяем процесс
send "echo '\\n✅ Проверка процесса:'\r"
expect "# "
send "ps aux | grep dashboard | grep -v grep\r"
expect "# "

# Проверяем размер файла dashboard.py
send "echo '\\n📁 Размер dashboard.py:'\r"
expect "# "
send "ls -lh dashboard.py\r"
expect "# "

# Проверяем API
send "echo '\\n🌐 Тест API:'\r"
expect "# "
send "curl -s http://localhost:5000/api/stats\r"
expect "# "

# Проверяем логи
send "echo '\\n📋 Последние логи:'\r"
expect "# "
send "tail -n 5 dashboard.log\r"
expect "# "

# Выходим
send "exit\r"
expect eof
EOF

echo ""
echo "✅ Полностью адаптивный дашборд развернут!"
echo "🌐 Откройте в браузере: http://$SERVER_IP:5000"
echo "📱 Протестируйте на разных устройствах:"
echo "   • Desktop (>1200px)"
echo "   • Laptop (992px-1200px)"
echo "   • Tablet (768px-992px)"
echo "   • Mobile (576px-768px)"
echo "   • Small Mobile (<576px)"

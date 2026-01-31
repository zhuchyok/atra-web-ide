#!/bin/bash

# Скрипт для автоматического развертывания дашборда на удаленном сервере
SERVER="185.177.216.15"
USER="root"
PASSWORD="u44Ww9NmtQj,XG"

echo "🚀 Развертывание ATRA Dashboard на сервере $SERVER..."

# Создаем архив
echo "📦 Создаем архив проекта..."
tar -czf atra_dashboard.tar.gz web/ rest_api.py main.py *.py *.json *.md deploy_dashboard.sh 2>/dev/null

# Загружаем архив на сервер
echo "📤 Загружаем файлы на сервер..."
expect << EOF
spawn scp atra_dashboard.tar.gz $USER@$SERVER:/root/
expect "password:"
send "$PASSWORD\r"
expect eof
EOF

# Подключаемся к серверу и разворачиваем
echo "🔧 Разворачиваем на сервере..."
expect << EOF
spawn ssh $USER@$SERVER
expect "password:"
send "$PASSWORD\r"
expect "#"

send "cd /root\r"
expect "#"

send "mkdir -p atra\r"
expect "#"

send "cd atra\r"
expect "#"

send "tar -xzf ../atra_dashboard.tar.gz\r"
expect "#"

send "chmod +x deploy_dashboard.sh\r"
expect "#"

send "pip3 install flask flask-cors\r"
expect "#"

send "./deploy_dashboard.sh\r"
expect "#"

send "netstat -tlnp | grep -E '(5002|8080)'\r"
expect "#"

send "exit\r"
expect eof
EOF

echo "✅ Развертывание завершено!"
echo "📊 Dashboard: http://$SERVER:5002"
echo "🔗 REST API: http://$SERVER:8080"

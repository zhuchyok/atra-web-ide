#!/bin/bash

# Скрипт для развертывания профессионального дашборда
# С графиками, аналитикой и расширенной функциональностью

SERVER_IP="185.177.216.15"
SERVER_USER="root"
SERVER_PASSWORD="u44Ww9NmtQj,XG"
SERVER_PATH="/root/atra"

echo "🚀 Развертывание профессионального дашборда"
echo "=========================================="

# Загружаем скрипт создания
echo "📤 Загрузка скрипта создания профессионального дашборда..."

expect << EOF
spawn scp -o StrictHostKeyChecking=no create_professional_dashboard.py $SERVER_USER@$SERVER_IP:$SERVER_PATH/
expect "password:"
send "$SERVER_PASSWORD\r"
expect eof
EOF

# Создаем и запускаем профессиональный дашборд
expect << EOF
spawn ssh -o StrictHostKeyChecking=no $SERVER_USER@$SERVER_IP
expect "password:"
send "$SERVER_PASSWORD\r"
expect "# "

# Переходим в директорию проекта
send "cd $SERVER_PATH\r"
expect "# "

# Останавливаем старый дашборд
send "pkill -f 'dashboard.py' || true\r"
expect "# "

# Создаем профессиональный дашборд
send "python3 create_professional_dashboard.py\r"
expect "# "

# Переходим в директорию web
send "cd web\r"
expect "# "

# Запускаем профессиональный дашборд в фоне
send "nohup python3 dashboard.py > dashboard.log 2>&1 &\r"
expect "# "

# Ждем запуска
send "sleep 5\r"
expect "# "

# Проверяем, что дашборд запущен
send "ps aux | grep dashboard\r"
expect "# "

# Тестируем API
send "cd .. && python3 test_dashboard_api.py\r"
expect "# "

# Проверяем веб-интерфейс
send "curl -s http://localhost:5000/ | head -20\r"
expect "# "

# Проверяем новые API endpoints
send "curl -s http://localhost:5000/api/stats\r"
expect "# "

send "curl -s http://localhost:5000/api/portfolio\r"
expect "# "

# Проверяем логи
send "cd web && tail -n 10 dashboard.log\r"
expect "# "

# Выходим
send "exit\r"
expect eof
EOF

echo ""
echo "✅ Профессиональный дашборд развернут!"
echo "🌐 Откройте в браузере: http://$SERVER_IP:5000"
echo "📊 Новые возможности:"
echo "   • Статистика и метрики"
echo "   • Интерактивные графики Chart.js"
echo "   • Аналитика портфолио"
echo "   • Профессиональный дизайн"
echo "   • Адаптивная верстка"
echo "   • Автообновление каждые 30 секунд"

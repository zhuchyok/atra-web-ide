#!/bin/bash

# Скрипт для создания полноценного веб-дашборда
# Создает дашборд с красивым HTML интерфейсом

SERVER_IP="185.177.216.15"
SERVER_USER="root"
SERVER_PASSWORD="u44Ww9NmtQj,XG"
SERVER_PATH="/root/atra"

echo "🔧 Создание полноценного веб-дашборда"
echo "===================================="

# Загружаем скрипт создания
echo "📤 Загрузка скрипта создания..."

expect << EOF
spawn scp -o StrictHostKeyChecking=no create_web_dashboard.py $SERVER_USER@$SERVER_IP:$SERVER_PATH/
expect "password:"
send "$SERVER_PASSWORD\r"
expect eof
EOF

# Создаем и запускаем веб-дашборд
expect << EOF
spawn ssh -o StrictHostKeyChecking=no $SERVER_USER@$SERVER_IP
expect "password:"
send "$SERVER_PASSWORD\r"
expect "# "

# Переходим в директорию проекта
send "cd $SERVER_PATH\r"
expect "# "

# Останавливаем дашборд
send "pkill -f 'dashboard.py' || true\r"
expect "# "

# Создаем веб-дашборд
send "python3 create_web_dashboard.py\r"
expect "# "

# Переходим в директорию web
send "cd web\r"
expect "# "

# Запускаем дашборд в фоне
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

# Проверяем логи
send "cd web && tail -n 5 dashboard.log\r"
expect "# "

# Выходим
send "exit\r"
expect eof
EOF

echo ""
echo "✅ Полноценный веб-дашборд создан и запущен!"
echo "🌐 Откройте в браузере: http://$SERVER_IP:5000"
echo "📊 Теперь будет красивый веб-интерфейс с сигналами!"
echo "🔄 Автообновление каждые 30 секунд"

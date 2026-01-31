#!/bin/bash

# Скрипт для восстановления и запуска дашборда
# Восстанавливает рабочий дашборд и запускает его

SERVER_IP="185.177.216.15"
SERVER_USER="root"
SERVER_PASSWORD="u44Ww9NmtQj,XG"
SERVER_PATH="/root/atra"

echo "🔄 Восстановление и запуск дашборда"
echo "=================================="

# Загружаем скрипт восстановления
echo "📤 Загрузка скрипта восстановления..."

expect << EOF
spawn scp -o StrictHostKeyChecking=no restore_and_fix_dashboard.py $SERVER_USER@$SERVER_IP:$SERVER_PATH/
expect "password:"
send "$SERVER_PASSWORD\r"
expect eof
EOF

# Восстанавливаем и запускаем дашборд
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

# Восстанавливаем дашборд
send "python3 restore_and_fix_dashboard.py\r"
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

# Проверяем логи
send "tail -n 10 dashboard.log\r"
expect "# "

# Тестируем API
send "cd .. && python3 test_dashboard_api.py\r"
expect "# "

# Выходим
send "exit\r"
expect eof
EOF

echo ""
echo "✅ Дашборд восстановлен и запущен!"
echo "🌐 Проверьте: http://$SERVER_IP:5000"
echo "📊 Показывает последние 5 сигналов из users_data"
echo "📊 Для проверки логов: ssh $SERVER_USER@$SERVER_IP 'cd $SERVER_PATH/web && tail -f dashboard.log'"

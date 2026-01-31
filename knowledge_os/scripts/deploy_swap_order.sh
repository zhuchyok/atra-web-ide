#!/bin/bash

# Скрипт для изменения порядка TP1 и количества

SERVER_IP="185.177.216.15"
SERVER_USER="root"
SERVER_PASSWORD="u44Ww9NmtQj,XG"
SERVER_PATH="/root/atra"

echo "🔄 Изменение порядка TP1 и количества"
echo "====================================="

# Загружаем скрипт
echo "📤 Загрузка скрипта..."

expect << EOF
spawn scp -o StrictHostKeyChecking=no swap_tp1_qty_order.py $SERVER_USER@$SERVER_IP:$SERVER_PATH/
expect "password:"
send "$SERVER_PASSWORD\r"
expect eof
EOF

# Применяем изменения
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

# Меняем порядок полей
send "echo '\\n🔄 Меняем порядок TP1 и количества...'\r"
expect "# "
send "python3 swap_tp1_qty_order.py\r"
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

# Проверяем API
send "echo '\\n🌐 Тест API:'\r"
expect "# "
send "curl -s http://localhost:5000/api/signals | head -200\r"
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
echo "✅ Порядок полей изменен!"
echo "🌐 Откройте в браузере: http://$SERVER_IP:5000"
echo "📊 Новый порядок:"
echo "   1. Цена входа"
echo "   2. TP1 ← изменено"
echo "   3. Количество ← изменено"
echo "   4. TP2"
echo "   5. Статус"

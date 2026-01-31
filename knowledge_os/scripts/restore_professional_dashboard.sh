#!/bin/bash

# Скрипт для восстановления профессионального дашборда

SERVER_IP="185.177.216.15"
SERVER_USER="root"
SERVER_PASSWORD="u44Ww9NmtQj,XG"
SERVER_PATH="/root/atra"

echo "🔄 Восстановление профессионального дашборда"
echo "=========================================="

expect << EOF
spawn ssh -o StrictHostKeyChecking=no $SERVER_USER@$SERVER_IP
expect "password:"
send "$SERVER_PASSWORD\r"
expect "# "

# Переходим в директорию проекта
send "cd $SERVER_PATH\r"
expect "# "

# Проверяем резервные копии
send "echo '📁 Проверка резервных копий:'\r"
expect "# "
send "ls -lht professional_dashboard_backup_* 2>/dev/null | head -5\r"
expect "# "

# Проверяем текущий dashboard.py
send "echo '\\n📋 Размер текущего dashboard.py:'\r"
expect "# "
send "ls -lh web/dashboard.py\r"
expect "# "

# Проверяем содержимое (первые строки)
send "echo '\\n🔍 Начало файла dashboard.py:'\r"
expect "# "
send "head -20 web/dashboard.py\r"
expect "# "

# Останавливаем дашборд
send "echo '\\n🛑 Останавливаем дашборд...'\r"
expect "# "
send "pkill -f 'dashboard.py' || true\r"
expect "# "

send "sleep 2\r"
expect "# "

# Восстанавливаем профессиональный дашборд
send "echo '\\n🔄 Восстанавливаем профессиональный дашборд...'\r"
expect "# "
send "python3 create_professional_dashboard.py\r"
expect "# "

# Запускаем дашборд
send "echo '\\n🚀 Запускаем профессиональный дашборд...'\r"
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

# Тестируем API сигналов
send "echo '\\n🌐 Тест API сигналов:'\r"
expect "# "
send "curl -s http://localhost:5000/api/signals | python3 -c 'import sys, json; data = json.load(sys.stdin); print(f\"Сигналов: {len(data)}\"); [print(f\"  {i+1}. {s[\\\"symbol\\\"]} - {s[\\\"signal\\\"]} - {s[\\\"entry_price\\\"]}\") for i, s in enumerate(data[:5])]'\r"
expect "# "

# Проверяем логи
send "echo '\\n📋 Последние логи:'\r"
expect "# "
send "tail -n 10 dashboard.log\r"
expect "# "

# Выходим
send "exit\r"
expect eof
EOF

echo ""
echo "✅ Восстановление завершено"
echo "🌐 Откройте в браузере: http://$SERVER_IP:5000"

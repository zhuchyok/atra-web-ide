#!/bin/bash
# Скрипт деплоя дашборда на сервер

SERVER="root@185.177.216.15"
SERVER_PASSWORD="u44Ww9NmtQj,XG"
SERVER_PATH="/root/knowledge_os/dashboard"
LOCAL_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Функция для выполнения SSH команд с паролем
ssh_with_password() {
    expect << EOF
set timeout 30
spawn ssh -o StrictHostKeyChecking=no $SERVER "$1"
expect {
    "password:" {
        send "$SERVER_PASSWORD\r"
        exp_continue
    }
    "Password:" {
        send "$SERVER_PASSWORD\r"
        exp_continue
    }
    "yes/no" {
        send "yes\r"
        exp_continue
    }
    eof
}
EOF
}

# Функция для SCP с паролем
scp_with_password() {
    local src="$1"
    local dst="$2"
    expect << EOF
set timeout 60
spawn scp -o StrictHostKeyChecking=no "$src" "$dst"
expect {
    "password:" {
        send "$SERVER_PASSWORD\r"
        exp_continue
    }
    "Password:" {
        send "$SERVER_PASSWORD\r"
        exp_continue
    }
    "yes/no" {
        send "yes\r"
        exp_continue
    }
    eof
}
EOF
}

echo "🚀 Деплой обновленного дашборда на сервер..."

# Копируем файлы
scp_with_password "$LOCAL_PATH/knowledge_os/dashboard/app.py" "$SERVER:$SERVER_PATH/app.py"
scp_with_password "$LOCAL_PATH/knowledge_os/dashboard/app_enhanced.py" "$SERVER:$SERVER_PATH/app_enhanced.py"

echo "✅ Файлы скопированы"

# Перезапускаем дашборд
echo "🔄 Перезапуск дашборда..."
ssh_with_password "pkill -f 'streamlit run app.py' || true"
ssh_with_password "cd $SERVER_PATH && nohup /usr/bin/python3 -m streamlit run app.py --server.port 5002 --server.address 0.0.0.0 > dashboard.log 2>&1 &"

echo "✨ Деплой завершен! Дашборд должен быть доступен по адресу http://185.177.216.15:5002/"

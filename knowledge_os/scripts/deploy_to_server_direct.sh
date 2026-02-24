#!/usr/bin/expect -f
# Прямой деплой на сервер с выполнением команд

set timeout 60
set server "185.177.216.15"
set user "root"
set password "u44Ww9NmtQj,XG"

spawn ssh -o StrictHostKeyChecking=no $user@$server

expect {
    "password:" {
        send "$password\r"
        exp_continue
    }
    "yes/no" {
        send "yes\r"
        exp_continue
    }
    "# " {
        send "cd /root/atra\r"
        expect "# "

        send "echo '=================================================================================='\r"
        expect "# "
        send "echo '👥 КОМАНДА ИЗ 13 ЭКСПЕРТОВ - ОБНОВЛЕНИЕ БОТА'\r"
        expect "# "
        send "echo '=================================================================================='\r"
        expect "# "

        # Шаг 1: Останавливаем бота
        send "echo ''\r"
        expect "# "
        send "echo '📋 ШАГ 1: Остановка бота'\r"
        expect "# "
        send "systemctl stop myproject.service 2>/dev/null || true\r"
        expect "# "
        send "pkill -f 'signal_live.py' 2>/dev/null || true\r"
        expect "# "
        send "pkill -f 'main.py' 2>/dev/null || true\r"
        expect "# "
        send "sleep 2\r"
        expect "# "

        # Шаг 2: Обновляем код
        send "echo ''\r"
        expect "# "
        send "echo '📋 ШАГ 2: Обновление кода с git'\r"
        expect "# "
        send "git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || git pull\r"
        expect "# "

        # Шаг 3: Проверяем конфигурацию
        send "echo ''\r"
        expect "# "
        send "echo '📋 ШАГ 3: Проверка конфигурации'\r"
        expect "# "
        send "python3 << 'PYEOF'\r"
        expect "# "
        send "import sys\r"
        expect "# "
        send "sys.path.insert(0, '/root/atra')\r"
        expect "# "
        send "try:\r"
        expect "# "
        send "    from config import USE_VP_FILTER, USE_VWAP_FILTER, USE_ORDER_FLOW_FILTER\r"
        expect "# "
        send "    print(f'VP Filter: {\"✅\" if USE_VP_FILTER else \"❌\"}')\r"
        expect "# "
        send "    print(f'VWAP Filter: {\"✅\" if USE_VWAP_FILTER else \"❌\"}')\r"
        expect "# "
        send "    print(f'Order Flow: {\"✅\" if USE_ORDER_FLOW_FILTER else \"❌\"}')\r"
        expect "# "
        send "except Exception as e:\r"
        expect "# "
        send "    print(f'Ошибка: {e}')\r"
        expect "# "
        send "PYEOF\r"
        expect "# "

        # Шаг 4: Запускаем бота
        send "echo ''\r"
        expect "# "
        send "echo '📋 ШАГ 4: Запуск бота'\r"
        expect "# "
        send "systemctl start myproject.service 2>/dev/null || (cd /root/atra && nohup python3 signal_live.py > signal_live.log 2>&1 &)\r"
        expect "# "
        send "sleep 5\r"
        expect "# "

        # Шаг 5: Проверяем статус
        send "echo ''\r"
        expect "# "
        send "echo '📋 ШАГ 5: Проверка статуса'\r"
        expect "# "
        send "ps aux | grep -E '(signal_live|main\\.py)' | grep -v grep || echo 'Процессы не найдены'\r"
        expect "# "

        # Шаг 6: Проверяем логи
        send "echo ''\r"
        expect "# "
        send "echo '📋 ШАГ 6: Последние строки логов'\r"
        expect "# "
        send "tail -20 /root/atra/signal_live.log 2>/dev/null || tail -20 /root/atra/logs/signal_live.log 2>/dev/null || echo 'Лог не найден'\r"
        expect "# "

        # Шаг 7: Проверяем БД
        send "echo ''\r"
        expect "# "
        send "echo '📋 ШАГ 7: Проверка базы данных'\r"
        expect "# "
        send "python3 << 'PYEOF'\r"
        expect "# "
        send "import sqlite3\r"
        expect "# "
        send "import os\r"
        expect "# "
        send "db_path = '/root/atra/trading.db'\r"
        expect "# "
        send "if os.path.exists(db_path):\r"
        expect "# "
        send "    conn = sqlite3.connect(db_path)\r"
        expect "# "
        send "    cursor = conn.cursor()\r"
        expect "# "
        send "    cursor.execute('SELECT COUNT(*) FROM signals WHERE datetime(ts) > datetime(\\\"now\\\", \\\"-24 hours\\\")')\r"
        expect "# "
        send "    signals_24h = cursor.fetchone()[0]\r"
        expect "# "
        send "    print(f'Сигналов за 24ч: {signals_24h}')\r"
        expect "# "
        send "    cursor.execute('SELECT COUNT(*) FROM active_signals WHERE status = \\\"active\\\"')\r"
        expect "# "
        send "    active = cursor.fetchone()[0]\r"
        expect "# "
        send "    print(f'Активных сигналов: {active}')\r"
        expect "# "
        send "    conn.close()\r"
        expect "# "
        send "else:\r"
        expect "# "
        send "    print('База данных не найдена')\r"
        expect "# "
        send "PYEOF\r"
        expect "# "

        send "echo ''\r"
        expect "# "
        send "echo '=================================================================================='\r"
        expect "# "
        send "echo '✅ ОБНОВЛЕНИЕ ЗАВЕРШЕНО'\r"
        expect "# "
        send "echo '=================================================================================='\r"
        expect "# "

        send "exit\r"
        expect eof
    }
    timeout {
        puts "Timeout waiting for prompt"
        exit 1
    }
}

wait

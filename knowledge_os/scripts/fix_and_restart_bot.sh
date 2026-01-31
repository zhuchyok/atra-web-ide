#!/usr/bin/expect -f
# Исправление ошибки и перезапуск бота

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
        send "echo '🔧 ИСПРАВЛЕНИЕ ОШИБКИ И ПЕРЕЗАПУСК БОТА'\r"
        expect "# "
        send "echo '=================================================================================='\r"
        expect "# "
        
        # Обновляем код
        send "echo ''\r"
        expect "# "
        send "echo '📋 ШАГ 1: Обновление кода'\r"
        expect "# "
        send "git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || git pull\r"
        expect "# "
        
        # Исправляем ошибку вручную (на случай если git pull не сработал)
        send "echo '📋 ШАГ 2: Исправление ошибки в cumulative_delta.py'\r"
        expect "# "
        send "sed -i \"s/from typing import Optional, Tuple/from typing import Optional, Tuple, Dict, Any/\" /root/atra/src/analysis/order_flow/cumulative_delta.py 2>/dev/null || true\r"
        expect "# "
        
        # Останавливаем бота
        send "echo ''\r"
        expect "# "
        send "echo '📋 ШАГ 3: Остановка бота'\r"
        expect "# "
        send "pkill -f 'signal_live.py' 2>/dev/null || true\r"
        expect "# "
        send "pkill -f 'main.py' 2>/dev/null || true\r"
        expect "# "
        send "sleep 2\r"
        expect "# "
        
        # Запускаем бота
        send "echo ''\r"
        expect "# "
        send "echo '📋 ШАГ 4: Запуск бота'\r"
        expect "# "
        send "cd /root/atra && nohup python3 signal_live.py > signal_live.log 2>&1 &\r"
        expect "# "
        send "sleep 5\r"
        expect "# "
        
        # Проверяем
        send "echo ''\r"
        expect "# "
        send "echo '📋 ШАГ 5: Проверка статуса'\r"
        expect "# "
        send "ps aux | grep -E '(signal_live|main\\.py)' | grep -v grep || echo '❌ Бот не запущен'\r"
        expect "# "
        
        send "echo ''\r"
        expect "# "
        send "echo '📋 ШАГ 6: Последние 10 строк логов'\r"
        expect "# "
        send "tail -10 /root/atra/signal_live.log 2>/dev/null | tail -10\r"
        expect "# "
        
        send "echo ''\r"
        expect "# "
        send "echo '=================================================================================='\r"
        expect "# "
        send "echo '✅ ГОТОВО'\r"
        expect "# "
        send "echo '=================================================================================='\r"
        expect "# "
        
        send "exit\r"
        expect eof
    }
    timeout {
        puts "Timeout"
        exit 1
    }
}

wait


#!/usr/bin/expect -f
# Автоматический запуск системы на продакшн сервере
# Использование: ./scripts/auto_start_production.sh

set timeout 30
set server "root@185.177.216.15"
set password "u44Ww9NmtQj,XG"

spawn ssh -o StrictHostKeyChecking=no $server

expect {
    "password:" {
        send "$password\r"
        exp_continue
    }
    "Password:" {
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
        
        send "ps aux | grep 'python.*main.py' | grep -v grep\r"
        expect "# "
        
        send "if ps aux | grep -q 'python.*main.py' | grep -v grep; then kill -SIGTERM \$(ps aux | grep 'python.*main.py' | grep -v grep | awk '{print \$2}') 2>/dev/null; sleep 5; fi\r"
        expect "# "
        
        send "sed -i 's/^ATRA_ENV=.*/ATRA_ENV=prod/' env 2>/dev/null || true\r"
        expect "# "
        
        send "mkdir -p logs\r"
        expect "# "
        
        send "nohup python3 main.py > logs/atra.log 2>&1 &\r"
        expect "# "
        
        send "sleep 5\r"
        expect "# "
        
        send "ps aux | grep 'python.*main.py' | grep -v grep\r"
        expect "# "
        
        send "echo '=== ПРОВЕРКА ЛОГОВ ==='\r"
        expect "# "
        
        send "if [ -f logs/atra.log ] && [ -s logs/atra.log ]; then tail -30 logs/atra.log; else echo 'Лог-файл еще создается...'; sleep 3; if [ -f logs/atra.log ]; then tail -30 logs/atra.log; else echo 'Лог-файл не создан'; fi; fi\r"
        expect "# "
        
        send "exit\r"
        expect eof
    }
    timeout {
        puts "Timeout при подключении"
        exit 1
    }
}


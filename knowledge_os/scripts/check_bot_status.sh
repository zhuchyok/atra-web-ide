#!/usr/bin/expect -f
# Быстрая проверка статуса бота

set timeout 30
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
        send "echo '📊 СТАТУС БОТА'\r"
        expect "# "
        send "echo '=================================================================================='\r"
        expect "# "
        
        # Процессы
        send "echo ''\r"
        expect "# "
        send "echo '1️⃣ ПРОЦЕССЫ:'\r"
        expect "# "
        send "ps aux | grep -E '(signal_live|main\\.py)' | grep -v grep || echo '❌ Бот не запущен'\r"
        expect "# "
        
        # Диск
        send "echo ''\r"
        expect "# "
        send "echo '2️⃣ ДИСК:'\r"
        expect "# "
        send "df -h / | tail -1\r"
        expect "# "
        
        # Последние логи
        send "echo ''\r"
        expect "# "
        send "echo '3️⃣ ПОСЛЕДНИЕ 5 СТРОК ЛОГОВ:'\r"
        expect "# "
        send "tail -5 /root/atra/signal_live.log 2>/dev/null || echo 'Лог не найден'\r"
        expect "# "
        
        # Сигналы
        send "echo ''\r"
        expect "# "
        send "echo '4️⃣ СИГНАЛЫ В БД:'\r"
        expect "# "
        send "python3 -c \"import sqlite3; conn = sqlite3.connect('/root/atra/trading.db'); c = conn.cursor(); c.execute('SELECT COUNT(*) FROM signals WHERE datetime(ts) > datetime(\\\"now\\\", \\\"-1 hour\\\")'); print(f'За час: {c.fetchone()[0]}'); c.execute('SELECT COUNT(*) FROM signals WHERE datetime(ts) > datetime(\\\"now\\\", \\\"-24 hours\\\")'); print(f'За 24ч: {c.fetchone()[0]}'); conn.close()\" 2>/dev/null || echo 'Ошибка проверки БД'\r"
        expect "# "
        
        send "echo ''\r"
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


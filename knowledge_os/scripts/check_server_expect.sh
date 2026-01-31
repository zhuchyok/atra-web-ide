#!/usr/bin/expect -f

set timeout 30

spawn ssh root@185.177.216.15

expect {
    "password:" {
        send "u44Ww9NmtQj,XG\r"
    }
    "yes/no" {
        send "yes\r"
        exp_continue
    }
}

expect "root@*" {
    send "cd /root/atra\r"
}

expect "root@*" {
    send "echo '=== СТАТУС СЕРВЕРА ==='\r"
}

expect "root@*" {
    send "ps aux | grep main.py | grep -v grep | wc -l\r"
}

expect "root@*" {
    send "tail -10 system_improved.log\r"
}

expect "root@*" {
    send "python3 -c \"import sqlite3; conn = sqlite3.connect('trading.db'); cursor = conn.cursor(); cursor.execute('SELECT COUNT(*) FROM telemetry_cycles WHERE datetime(ts) >= datetime(\\\"now\\\", \\\"-1 hours\\\")'); print(f'Циклов за час: {cursor.fetchone()[0]}'); conn.close()\"\r"
}

expect "root@*" {
    send "grep -c callback_build system_improved.log\r"
}

expect "root@*" {
    send "exit\r"
}

expect eof

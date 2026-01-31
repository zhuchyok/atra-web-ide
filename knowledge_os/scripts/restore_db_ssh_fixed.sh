#!/usr/bin/expect -f
set timeout 120
set server "185.177.216.15"
set user "root"
set password "u44Ww9NmtQj,XG"

# Копируем скрипт на сервер
spawn scp -o StrictHostKeyChecking=no scripts/restore_db_on_server.py $user@$server:/root/atra/restore_db_temp.py

expect {
    "password:" {
        send "$password\r"
        exp_continue
    }
    "yes/no" {
        send "yes\r"
        exp_continue
    }
    eof
}

wait

# Выполняем скрипт на сервере
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
        send "python3 restore_db_temp.py\r"
        expect "# "
        send "rm -f restore_db_temp.py\r"
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


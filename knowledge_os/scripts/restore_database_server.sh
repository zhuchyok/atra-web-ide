#!/usr/bin/expect -f
# Скрипт восстановления БД на сервере
# Команда: Роман (Database Engineer), Сергей (DevOps Engineer)

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
        send "echo '🔧 ВОССТАНОВЛЕНИЕ БАЗЫ ДАННЫХ'\r"
        expect "# "
        send "echo '=================================================================================='\r"
        expect "# "

        # Проверка существования БД
        send "echo ''\r"
        expect "# "
        send "echo '📊 ШАГ 1: Проверка базы данных'\r"
        expect "# "
        send "if [ -f /root/atra/trading.db ]; then echo '✅ БД найдена'; ls -lh /root/atra/trading.db; else echo '❌ БД не найдена'; fi\r"
        expect "# "

        # Создание бэкапа
        send "echo ''\r"
        expect "# "
        send "echo '📊 ШАГ 2: Создание бэкапа'\r"
        expect "# "
        send "mkdir -p /root/atra/backups\r"
        expect "# "
        send "cp /root/atra/trading.db /root/atra/backups/trading.db.backup.$(date +%Y%m%d_%H%M%S) 2>/dev/null && echo '✅ Бэкап создан' || echo '⚠️ Ошибка создания бэкапа'\r"
        expect "# "

        # Попытка восстановления через Python
        send "echo ''\r"
        expect "# "
        send "echo '📊 ШАГ 3: Попытка восстановления'\r"
        expect "# "
        send "cd /root/atra && python3 scripts/restore_database.py 2>&1 | tail -30\r"
        expect "# "

        # Проверка результата
        send "echo ''\r"
        expect "# "
        send "echo '📊 ШАГ 4: Проверка результата'\r"
        expect "# "
        send "python3 << 'PYEOF'\r"
        send "import sqlite3\r"
        send "try:\r"
        send "    conn = sqlite3.connect('/root/atra/trading.db')\r"
        send "    cursor = conn.cursor()\r"
        send "    cursor.execute('PRAGMA integrity_check')\r"
        send "    result = cursor.fetchone()\r"
        send "    if result and result[0] == 'ok':\r"
        send "        print('✅ База данных целостна')\r"
        send "    else:\r"
        send "        print(f'❌ База данных повреждена: {result}')\r"
        send "    conn.close()\r"
        send "except Exception as e:\r"
        send "    print(f'❌ Ошибка: {e}')\r"
        send "PYEOF\r"
        expect "# "

        send "echo ''\r"
        expect "# "
        send "echo '=================================================================================='\r"
        expect "# "
        send "echo '✅ ВОССТАНОВЛЕНИЕ ЗАВЕРШЕНО'\r"
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

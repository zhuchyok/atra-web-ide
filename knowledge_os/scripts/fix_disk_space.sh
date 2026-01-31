#!/usr/bin/expect -f
# Скрипт для очистки диска на сервере

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
        send "echo '🧹 ОЧИСТКА ДИСКА'\r"
        expect "# "
        send "echo '=================================================================================='\r"
        expect "# "
        
        # Проверяем текущее использование
        send "df -h /\r"
        expect "# "
        
        # Удаляем старые логи
        send "echo ''\r"
        expect "# "
        send "echo '📋 Удаление старых логов...'\r"
        expect "# "
        send "find /root/atra/logs -name '*.log.*' -mtime +7 -delete 2>/dev/null || true\r"
        expect "# "
        send "find /root/atra -name '*.log.*' -mtime +7 -delete 2>/dev/null || true\r"
        expect "# "
        
        # Удаляем старые бэкапы
        send "echo '📋 Удаление старых бэкапов...'\r"
        expect "# "
        send "find /root/atra/backups -name '*.db_*' -mtime +7 -delete 2>/dev/null || true\r"
        expect "# "
        
        # Очищаем кэш
        send "echo '📋 Очистка кэша...'\r"
        expect "# "
        send "rm -rf /root/atra/cache/* 2>/dev/null || true\r"
        expect "# "
        send "find /root/atra -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true\r"
        expect "# "
        
        # Очищаем временные файлы
        send "echo '📋 Очистка временных файлов...'\r"
        expect "# "
        send "rm -rf /tmp/atra_* 2>/dev/null || true\r"
        expect "# "
        send "rm -rf /root/atra/.pytest_cache 2>/dev/null || true\r"
        expect "# "
        
        # Проверяем размер после очистки
        send "echo ''\r"
        expect "# "
        send "echo '📊 Использование диска после очистки:'\r"
        expect "# "
        send "df -h /\r"
        expect "# "
        
        # Завершаем обновление git
        send "echo ''\r"
        expect "# "
        send "echo '📋 Завершение обновления git...'\r"
        expect "# "
        send "cd /root/atra && git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || git pull\r"
        expect "# "
        
        # Проверяем статус бота
        send "echo ''\r"
        expect "# "
        send "echo '📋 Проверка статуса бота...'\r"
        expect "# "
        send "ps aux | grep -E '(signal_live|main\\.py)' | grep -v grep || echo 'Бот не запущен'\r"
        expect "# "
        
        send "echo ''\r"
        expect "# "
        send "echo '=================================================================================='\r"
        expect "# "
        send "echo '✅ ОЧИСТКА ЗАВЕРШЕНА'\r"
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


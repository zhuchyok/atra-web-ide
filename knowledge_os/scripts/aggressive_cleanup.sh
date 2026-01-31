#!/usr/bin/expect -f
# Агрессивная очистка диска

set timeout 120
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
        send "echo '🧹 АГРЕССИВНАЯ ОЧИСТКА ДИСКА'\r"
        expect "# "
        send "echo '=================================================================================='\r"
        expect "# "
        
        # Находим самые большие файлы
        send "echo '📊 Поиск больших файлов...'\r"
        expect "# "
        send "du -sh /root/atra/* 2>/dev/null | sort -hr | head -10\r"
        expect "# "
        
        # Удаляем все старые логи (не только старше 7 дней)
        send "echo ''\r"
        expect "# "
        send "echo '📋 Удаление ВСЕХ старых логов...'\r"
        expect "# "
        send "find /root/atra/logs -name '*.log.*' -delete 2>/dev/null || true\r"
        expect "# "
        send "find /root/atra -name '*.log.*' -delete 2>/dev/null || true\r"
        expect "# "
        send "find /root/atra -name '*.log' -size +100M -delete 2>/dev/null || true\r"
        expect "# "
        
        # Удаляем все старые бэкапы
        send "echo '📋 Удаление ВСЕХ старых бэкапов...'\r"
        expect "# "
        send "find /root/atra/backups -name '*.db_*' -delete 2>/dev/null || true\r"
        expect "# "
        send "rm -rf /root/atra/backups/*.db_* 2>/dev/null || true\r"
        expect "# "
        
        # Удаляем большие файлы данных
        send "echo '📋 Удаление больших файлов данных...'\r"
        expect "# "
        send "find /root/atra/data -name '*.csv' -size +50M -delete 2>/dev/null || true\r"
        expect "# "
        
        # Очищаем git объекты
        send "echo '📋 Очистка git...'\r"
        expect "# "
        send "cd /root/atra && git gc --prune=now 2>/dev/null || true\r"
        expect "# "
        send "rm -rf /root/atra/.git/objects/pack/*.pack.old 2>/dev/null || true\r"
        expect "# "
        
        # Очищаем все кэши
        send "echo '📋 Очистка всех кэшей...'\r"
        expect "# "
        send "rm -rf /root/atra/cache/* 2>/dev/null || true\r"
        expect "# "
        send "rm -rf /root/atra/__pycache__ 2>/dev/null || true\r"
        expect "# "
        send "find /root/atra -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true\r"
        expect "# "
        send "find /root/atra -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true\r"
        expect "# "
        send "rm -rf /root/atra/htmlcov 2>/dev/null || true\r"
        expect "# "
        
        # Проверяем размер после очистки
        send "echo ''\r"
        expect "# "
        send "echo '📊 Использование диска после очистки:'\r"
        expect "# "
        send "df -h /\r"
        expect "# "
        
        # Пробуем завершить git pull с минимальным использованием места
        send "echo ''\r"
        expect "# "
        send "echo '📋 Попытка завершить git pull...'\r"
        expect "# "
        send "cd /root/atra && git fetch --depth=1 2>/dev/null || true\r"
        expect "# "
        send "cd /root/atra && git reset --hard origin/main 2>/dev/null || git reset --hard origin/master 2>/dev/null || true\r"
        expect "# "
        
        # Проверяем статус бота
        send "echo ''\r"
        expect "# "
        send "echo '📋 Проверка статуса бота...'\r"
        expect "# "
        send "ps aux | grep -E '(signal_live|main\\.py)' | grep -v grep || echo 'Бот не запущен'\r"
        expect "# "
        
        # Проверяем последние логи
        send "echo ''\r"
        expect "# "
        send "echo '📋 Последние 10 строк логов:'\r"
        expect "# "
        send "tail -10 /root/atra/signal_live.log 2>/dev/null || echo 'Лог не найден'\r"
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


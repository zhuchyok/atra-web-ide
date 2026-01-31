#!/bin/bash
# Быстрый перезапуск бота на прод-сервере

echo "🔄 ПЕРЕЗАПУСК БОТА НА ПРОД-СЕРВЕРЕ"
echo "=================================="
echo ""
echo "Выполните эти команды на сервере (ssh root@185.177.216.15):"
echo ""
echo "cd /root/atra"
echo "pkill -9 -f main.py"
echo "sleep 2"
echo "rm -f *.lock telegram_*.lock .telegram_*"
echo "export ATRA_ENV=prod"
echo "nohup python3 main.py > server.log 2>&1 &"
echo "sleep 3"
echo "ps aux | grep main.py | grep -v grep"
echo "tail -20 server.log"
echo ""
echo "Или одной командой:"
echo "cd /root/atra && pkill -9 -f main.py && sleep 2 && rm -f *.lock && export ATRA_ENV=prod && nohup python3 main.py > server.log 2>&1 & sleep 3 && ps aux | grep main.py | grep -v grep && tail -20 server.log"


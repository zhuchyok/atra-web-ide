#!/bin/bash
# Скрипт для обновления кода и запуска бота на сервере

SERVER="root@185.177.216.15"
REMOTE_DIR="~/atra"

echo "🚀 ОБНОВЛЕНИЕ И ЗАПУСК БОТА НА СЕРВЕРЕ"
echo "========================================"

# Команды для выполнения на сервере
COMMANDS="
cd $REMOTE_DIR && \
echo '📥 Обновление кода с git...' && \
git pull && \
echo '🛑 Остановка старого процесса (если запущен)...' && \
pkill -f 'signal_live.py' || true && \
sleep 2 && \
echo '🚀 Запуск бота...' && \
nohup python3 signal_live.py > signal_live.log 2>&1 & \
sleep 3 && \
echo '✅ Проверка процессов...' && \
ps aux | grep -E '(signal_live|main\.py)' | grep -v grep && \
echo '📋 Последние строки лога:' && \
tail -5 signal_live.log 2>/dev/null || echo 'Лог еще не создан'
"

# Выполняем команды на сервере
ssh -o StrictHostKeyChecking=no $SERVER "$COMMANDS"

echo ""
echo "✅ Готово! Проверьте статус:"
echo "   ssh $SERVER 'cd $REMOTE_DIR && python3 check_signals_status.py'"

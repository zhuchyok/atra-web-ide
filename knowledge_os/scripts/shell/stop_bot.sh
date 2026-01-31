#!/bin/bash
# Скрипт для остановки ATRA бота

echo "🛑 Остановка бота..."
# Останавливаем все процессы main.py
pkill -f 'python3.*main.py' 2>/dev/null
sleep 2

# Очищаем lock файлы
rm -f /tmp/atra_tg_poll_*.lock atra.lock 2>/dev/null

# Проверяем, что процесс остановлен
if ps aux | grep 'python3.*main.py' | grep -v grep > /dev/null; then
    echo "⚠️ Некоторые процессы все еще запущены, принудительная остановка..."
    pkill -9 -f 'python3.*main.py' 2>/dev/null
    sleep 1
fi

if ps aux | grep 'python3.*main.py' | grep -v grep > /dev/null; then
    echo "❌ Не удалось остановить бот"
    exit 1
else
    echo "✅ Бот остановлен, lock файлы очищены"
fi

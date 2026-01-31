#!/bin/bash
# Принудительная остановка всех процессов бота

echo "🛑 Принудительная остановка всех процессов бота..."

# Останавливаем все процессы main.py
pkill -9 -f 'python3.*main.py' 2>/dev/null
pkill -9 -f 'python.*main.py' 2>/dev/null
pkill -9 -f 'main.py' 2>/dev/null

sleep 1

# Очищаем lock файлы
rm -f /tmp/atra_tg_poll_*.lock atra.lock bot.pid 2>/dev/null

# Проверяем результат
if ps aux | grep -E 'python.*main.py|main.py' | grep -v grep > /dev/null; then
    echo "⚠️ Некоторые процессы все еще запущены:"
    ps aux | grep -E 'python.*main.py|main.py' | grep -v grep
    echo ""
    echo "Попытка принудительной остановки через PID..."
    ps aux | grep -E 'python.*main.py|main.py' | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null
    sleep 1
fi

if ps aux | grep -E 'python.*main.py|main.py' | grep -v grep > /dev/null; then
    echo "❌ Не удалось остановить все процессы"
    exit 1
else
    echo "✅ Все процессы остановлены, lock файлы очищены"
fi

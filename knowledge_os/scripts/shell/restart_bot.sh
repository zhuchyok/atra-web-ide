#!/bin/bash
cd "$(dirname "$0")"

echo "🔄 Перезапуск бота ATRA..."
echo ""

# Останавливаем все процессы
echo "⏹️  Останавливаю процессы..."
pkill -f 'python.*main.py' 2>/dev/null
pkill -f 'python3.*main.py' 2>/dev/null
sleep 2

# Удаляем lock файлы
echo "🗑️  Удаляю lock файлы..."
rm -f *.pid bot_*.pid 2>/dev/null

# Запускаем бота
echo "🚀 Запускаю бота..."
LOGFILE="bot_restart_$(date +%Y%m%d_%H%M%S).log"
nohup python3 main.py > "$LOGFILE" 2>&1 &
BOT_PID=$!
echo $BOT_PID > bot.pid

sleep 3

# Проверяем статус
if ps -p $BOT_PID > /dev/null 2>&1; then
    echo "✅ Бот успешно запущен!"
    echo "   PID: $BOT_PID"
    echo "   Лог: $LOGFILE"
    echo ""
    echo "📊 Последние строки лога:"
    echo "---"
    tail -20 "$LOGFILE" 2>/dev/null | tail -10
else
    echo "❌ Бот не запустился!"
    echo "   Проверьте лог: $LOGFILE"
    echo ""
    echo "📊 Последние строки лога:"
    echo "---"
    tail -30 "$LOGFILE" 2>/dev/null | tail -20
fi

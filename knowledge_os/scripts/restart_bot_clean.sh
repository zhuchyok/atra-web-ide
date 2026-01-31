#!/bin/bash

echo "🔄 ПЕРЕЗАПУСК БОТА ATRA"
echo "======================"

# 1. Остановить все процессы
echo "🛑 Остановка всех процессов main.py..."
pkill -9 -f main.py
sleep 2

# Проверить, что остановлены
if ps aux | grep main.py | grep -v grep > /dev/null; then
    echo "⚠️  Некоторые процессы ещё работают"
    ps aux | grep main.py | grep -v grep
else
    echo "✅ Все процессы остановлены"
fi

# 2. Очистить блокировки
echo ""
echo "🧹 Очистка файлов блокировки..."
rm -f atra.lock
echo "✅ Файлы блокировки удалены"

# 3. Запустить бота
echo ""
echo "🚀 Запуск бота..."
cd ~/Documents/GITHUB/atra
nohup python3 main.py > main.log 2>&1 &
sleep 3

# 4. Проверить статус
echo ""
echo "📊 Проверка статуса:"
if ps aux | grep main.py | grep -v grep > /dev/null; then
    echo "✅ Бот запущен:"
    ps aux | grep main.py | grep -v grep | head -1
    PID=$(ps aux | grep main.py | grep -v grep | head -1 | awk '{print $2}')
    echo ""
    echo "📝 PID: $PID"
    echo "📋 Лог: tail -f main.log"
    echo "🔍 Мониторинг: tail -f system_improved.log"
else
    echo "❌ Бот не запущен! Проверьте логи:"
    echo "   tail -100 main.log"
fi

echo ""
echo "✅ Готово!"

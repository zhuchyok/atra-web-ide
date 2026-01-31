#!/bin/bash

echo "🔥 ПРИНУДИТЕЛЬНАЯ ОЧИСТКА ВСЕХ ПРОЦЕССОВ..."

# Получаем все PID процессов main.py
PIDS=$(ps aux | grep "python.*main.py" | grep -v grep | awk '{print $2}')

if [ -z "$PIDS" ]; then
    echo "✅ Нет процессов main.py для остановки"
else
    echo "🗑️ Найдено процессов: $(echo $PIDS | wc -w)"
    
    # Убиваем все процессы
    for pid in $PIDS; do
        echo "💀 Убиваем процесс $pid..."
        kill -9 $pid 2>/dev/null || true
    done
    
    # Ждем
    sleep 3
    
    # Проверяем остались ли процессы
    REMAINING=$(ps aux | grep "python.*main.py" | grep -v grep | wc -l)
    if [ $REMAINING -gt 0 ]; then
        echo "⚠️ Осталось $REMAINING процессов, применяем force kill..."
        ps aux | grep "python.*main.py" | grep -v grep | awk '{print $2}' | xargs sudo kill -9 2>/dev/null || true
    fi
fi

# Удаляем lock файл
echo "🔓 Удаляем lock файл..."
rm -f atra.lock

# Финальная проверка
sleep 2
FINAL_COUNT=$(ps aux | grep "python.*main.py" | grep -v grep | wc -l)
echo "📊 Финальное количество процессов: $FINAL_COUNT"

if [ $FINAL_COUNT -eq 0 ]; then
    echo "✅ ВСЕ ПРОЦЕССЫ ОСТАНОВЛЕНЫ!"
else
    echo "❌ Остались процессы: $FINAL_COUNT"
fi

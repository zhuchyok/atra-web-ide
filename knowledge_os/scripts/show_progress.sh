#!/bin/bash
# Скрипт для показа прогресса оптимизации

LOG_FILE="/tmp/optimization_current.log"

echo "📊 МОНИТОРИНГ ПРОГРЕССА ОПТИМИЗАЦИИ"
echo "=================================="
echo ""

while true; do
    if [ -f "$LOG_FILE" ]; then
        clear
        echo "📊 ПРОГРЕСС ОПТИМИЗАЦИИ"
        echo "=================================="
        echo ""
        tail -30 "$LOG_FILE" 2>/dev/null | grep -E "Прогресс|завершен|Тестируем|комб|симв|ETHUSDT|BNBUSDT|SOLUSDT|ADAUSDT|СТАТИСТИКА|ЛУЧШИЕ|█|░|✅|⚠️|❌" | tail -20
        echo ""
        echo "=================================="
        echo "Обновление каждые 5 секунд... (Ctrl+C для выхода)"
    else
        echo "⏳ Ожидание запуска оптимизации..."
    fi
    sleep 5
done

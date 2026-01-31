#!/bin/bash
# Скрипт для показа прогресса оптимизации в реальном времени

LOG_FILE="/tmp/opt_realtime.log"
SCRIPT="scripts/optimize_symbol_params_with_ai.py"

cd /Users/zhuchyok/Documents/GITHUB/atra/atra
source venv/bin/activate

# Запускаем оптимизацию в фоне
echo "🚀 Запуск оптимизации..."
python3 "$SCRIPT" > "$LOG_FILE" 2>&1 &
OPT_PID=$!
echo "✅ PID: $OPT_PID"
echo ""

# Показываем прогресс каждые 3 секунды
while kill -0 $OPT_PID 2>/dev/null; do
    clear
    echo "═══════════════════════════════════════════════════════════"
    echo "📊 ПРОГРЕСС ОПТИМИЗАЦИИ (обновление каждые 3 сек)"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    
    if [ -f "$LOG_FILE" ]; then
        # Показываем последние 25 строк
        tail -25 "$LOG_FILE"
    else
        echo "⏳ Ожидание запуска..."
    fi
    
    echo ""
    echo "═══════════════════════════════════════════════════════════"
    echo "⏱️  PID: $OPT_PID | Нажмите Ctrl+C для выхода"
    echo "═══════════════════════════════════════════════════════════"
    
    sleep 3
done

echo ""
echo "✅ Оптимизация завершена!"
if [ -f "$LOG_FILE" ]; then
    echo ""
    echo "📊 Финальный результат:"
    tail -30 "$LOG_FILE"
fi


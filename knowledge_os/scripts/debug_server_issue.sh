#!/bin/bash

echo "🔍 ДИАГНОСТИКА ПРОБЛЕМЫ НА СЕРВЕРЕ"
echo "=================================="

# Проверяем количество записей в базе данных
echo "📊 Проверка базы данных..."
if [ -f "trading.db" ]; then
    SIGNAL_COUNT=$(sqlite3 trading.db "SELECT COUNT(*) FROM signals_log;" 2>/dev/null || echo "0")
    echo "📈 Записей в signals_log: $SIGNAL_COUNT"

    if [ "$SIGNAL_COUNT" -gt 0 ]; then
        echo "✅ База данных содержит сигналы"
        echo "📋 Последние 3 записи:"
        sqlite3 trading.db "SELECT symbol, entry_time, result FROM signals_log ORDER BY created_at DESC LIMIT 3;"
    else
        echo "⚠️ База данных пуста"
    fi
else
    echo "❌ База данных trading.db не найдена"
fi

echo ""

# Проверяем активные процессы
echo "🔄 Проверка активных процессов..."
PROCESS_COUNT=$(ps aux | grep "python.*main.py" | grep -v grep | wc -l)
if [ "$PROCESS_COUNT" -gt 0 ]; then
    echo "✅ Система запущена ($PROCESS_COUNT процессов)"
    echo "📋 Процессы:"
    ps aux | grep "python.*main.py" | grep -v grep | head -2
else
    echo "❌ Система не запущена"
fi

echo ""

# Проверяем логи на наличие ошибок
echo "📝 Проверка последних ошибок в логах..."
if [ -f "system_improved.log" ]; then
    echo "🔍 Последние ошибки insert_signal_log:"
    tail -100 system_improved.log | grep -i "insert_signal_log.*error" | tail -3
    echo ""
    echo "🔍 Последние ошибки SQL:"
    tail -100 system_improved.log | grep -i "sql.*error" | tail -3
else
    echo "⚠️ Лог файл system_improved.log не найден"
fi

echo ""

# Проверяем, есть ли сигналы в других таблицах
echo "📊 Проверка других таблиц..."
if [ -f "trading.db" ]; then
    ACTIVE_SIGNALS=$(sqlite3 trading.db "SELECT COUNT(*) FROM active_signals;" 2>/dev/null || echo "0")
    SIGNALS=$(sqlite3 trading.db "SELECT COUNT(*) FROM signals;" 2>/dev/null || echo "0")
    echo "📈 Активных сигналов: $ACTIVE_SIGNALS"
    echo "📈 Записей в signals: $SIGNALS"
fi

echo ""
echo "💡 Рекомендации:"
echo "1. Если база данных пуста - проверьте генерацию сигналов"
echo "2. Если есть ошибки SQL - проверьте структуру базы данных"
echo "3. Если система не запущена - перезапустите систему"

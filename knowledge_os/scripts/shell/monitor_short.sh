#!/bin/bash
# Автоматический мониторинг SHORT сигналов

echo "🔍 Мониторинг SHORT сигналов - $(date)"
echo ""

# Проверяем, запущен ли бот
if ! ps aux | grep 'python.*main.py' | grep -v grep > /dev/null; then
    echo "❌ Бот не запущен!"
    exit 1
fi

echo "✅ Бот работает"
echo ""

# Проверяем последние SHORT сигналы
echo "📊 Последние SHORT сигналы (последние 10):"
tail -10000 bot.log | grep -E 'SHORT.*паттерн|SELL.*паттерн' | tail -10
echo ""

# Проверяем детальное логирование
echo "📋 Детальное логирование SHORT (последние 20):"
tail -10000 bot.log | grep -E '\[SHORT Alt-2\]|\[QUALITY CHECK\].*SHORT|\[QUALITY BLOCK\].*SHORT|\[QUALITY PASS\].*SHORT|\[CONFIDENCE BLOCK\].*SHORT|\[VOLUME QUALITY\].*SHORT|\[VOLUME BLOCK\].*SHORT|\[VOLUME PASS\].*SHORT|\[MTF CHECK\].*SHORT|\[MTF BLOCK\].*SHORT|\[MTF PASS\].*SHORT|\[SIGNAL GENERATED\].*SHORT' | tail -20
echo ""

# Статистика
SHORT_COUNT=$(tail -10000 bot.log | grep -c 'SHORT.*паттерн')
DETAILED_COUNT=$(tail -10000 bot.log | grep -c '\[SHORT Alt-2\]')
QUALITY_COUNT=$(tail -10000 bot.log | grep -c '\[QUALITY CHECK\].*SHORT')
BLOCKED_COUNT=$(tail -10000 bot.log | grep -c -E '\[QUALITY BLOCK\].*SHORT|\[CONFIDENCE BLOCK\].*SHORT|\[VOLUME BLOCK\].*SHORT|\[MTF BLOCK\].*SHORT')

echo "📊 Статистика (последние 10000 строк логов):"
echo "  • SHORT сигналов: $SHORT_COUNT"
echo "  • Детальных записей [SHORT Alt-2]: $DETAILED_COUNT"
echo "  • Quality проверок: $QUALITY_COUNT"
echo "  • Блокировок: $BLOCKED_COUNT"
echo ""

if [ "$SHORT_COUNT" -gt 0 ] && [ "$DETAILED_COUNT" -eq 0 ]; then
    echo "⚠️ ВНИМАНИЕ: Есть SHORT сигналы, но нет детального логирования!"
    echo "   Возможно, бот не был перезапущен после изменений"
fi

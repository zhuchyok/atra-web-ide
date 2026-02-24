#!/bin/bash
# Скрипт для мониторинга блокировок сигналов в реальном времени

echo "🔍 МОНИТОРИНГ БЛОКИРОВОК СИГНАЛОВ"
echo "=================================="
echo ""
echo "📊 Отслеживаемые события:"
echo "  - [DIRECTION CHECK] - проверка направления"
echo "  - [QUALITY PASS/BLOCK] - проверка качества"
echo "  - [RSI FILTER] - проверка RSI"
echo "  - [VOLUME BLOCK] - блокировка по объему"
echo "  - [BREAKOUT BLOCK] - блокировка по ложному пробою"
echo "  - [MTF BLOCK/PASS] - проверка MTF"
echo "  - [SEND_SIGNAL BLOCK] - блокировка при отправке"
echo ""
echo "Нажмите Ctrl+C для выхода"
echo ""

tail -f bot.log | grep --line-buffered -E "\[DIRECTION CHECK\]|\[QUALITY|\[RSI FILTER\]|\[VOLUME BLOCK\]|\[BREAKOUT BLOCK\]|\[MTF|\[SEND_SIGNAL BLOCK\]|NO SIGNAL" | while IFS= read -r line; do
    timestamp=$(date '+%H:%M:%S')

    # Цветовая маркировка
    if echo "$line" | grep -q "BLOCK\|NO SIGNAL\|🚫"; then
        echo -e "\033[31m[$timestamp] $line\033[0m"
    elif echo "$line" | grep -q "PASS\|✅\|SUCCESS"; then
        echo -e "\033[32m[$timestamp] $line\033[0m"
    elif echo "$line" | grep -q "WARNING\|⚠️"; then
        echo -e "\033[33m[$timestamp] $line\033[0m"
    else
        echo "[$timestamp] $line"
    fi
done

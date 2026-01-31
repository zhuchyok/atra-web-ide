#!/bin/bash
# -*- coding: utf-8 -*-
# Детальный анализ Direction Check блокировок

LOG_FILE="bot.log"
HOURS=${1:-6}

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║           ДЕТАЛЬНЫЙ АНАЛИЗ DIRECTION CHECK                          ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Период: последние $HOURS часов"
echo ""

# Используем tail для последних N часов
lines_per_hour=1000
tail_lines=$((HOURS * lines_per_hour))

echo "📊 СТАТИСТИКА DIRECTION CHECK:"
echo ""

# Общая статистика
total_direction_checks=$(tail -n ${tail_lines} "$LOG_FILE" 2>/dev/null | grep -i "DIRECTION CHECK" | wc -l | tr -d ' ')
blocked_2_4=$(tail -n ${tail_lines} "$LOG_FILE" 2>/dev/null | grep -i "DIRECTION CHECK.*2/4" | wc -l | tr -d ' ')
blocked_1_4=$(tail -n ${tail_lines} "$LOG_FILE" 2>/dev/null | grep -i "DIRECTION CHECK.*1/4" | wc -l | tr -d ' ')
passed_3_4=$(tail -n ${tail_lines} "$LOG_FILE" 2>/dev/null | grep -i "DIRECTION CHECK.*3/4" | wc -l | tr -d ' ')
passed_4_4=$(tail -n ${tail_lines} "$LOG_FILE" 2>/dev/null | grep -i "DIRECTION CHECK.*4/4" | wc -l | tr -d ' ')

echo "Всего проверок Direction Check: $total_direction_checks"
echo "  ✅ Прошли (3/4): $passed_3_4"
echo "  ✅ Прошли (4/4): $passed_4_4"
echo "  ❌ Заблокированы (2/4): $blocked_2_4"
echo "  ❌ Заблокированы (1/4): $blocked_1_4"
echo ""

# Анализ отсутствующих подтверждений
echo "📋 АНАЛИЗ ОТСУТСТВУЮЩИХ ПОДТВЕРЖДЕНИЙ:"
echo ""

# EMA alignment
ema_alignment_missing=$(tail -n ${tail_lines} "$LOG_FILE" 2>/dev/null | grep -i "Отсутствуют.*EMA alignment" | wc -l | tr -d ' ')
echo "  ❌ EMA alignment отсутствует: $ema_alignment_missing раз"

# RSI < 50
rsi_missing=$(tail -n ${tail_lines} "$LOG_FILE" 2>/dev/null | grep -i "Отсутствуют.*RSI" | wc -l | tr -d ' ')
echo "  ❌ RSI < 50 отсутствует: $rsi_missing раз"

# MACD > Signal
macd_missing=$(tail -n ${tail_lines} "$LOG_FILE" 2>/dev/null | grep -i "Отсутствуют.*MACD" | wc -l | tr -d ' ')
echo "  ❌ MACD > Signal отсутствует: $macd_missing раз"

# Price > EMA
price_ema_missing=$(tail -n ${tail_lines} "$LOG_FILE" 2>/dev/null | grep -i "Отсутствуют.*Price" | wc -l | tr -d ' ')
echo "  ❌ Price > EMA отсутствует: $price_ema_missing раз"

echo ""

# Анализ прошедших подтверждений
echo "✅ ПОДТВЕРЖДЕНИЯ, КОТОРЫЕ ПРОХОДЯТ:"
echo ""

price_above_ema=$(tail -n ${tail_lines} "$LOG_FILE" 2>/dev/null | grep -i "BUY CONFIRM.*Price above EMA" | wc -l | tr -d ' ')
macd_above_signal=$(tail -n ${tail_lines} "$LOG_FILE" 2>/dev/null | grep -i "BUY CONFIRM.*MACD above signal" | wc -l | tr -d ' ')
ema_alignment_pass=$(tail -n ${tail_lines} "$LOG_FILE" 2>/dev/null | grep -i "BUY CONFIRM.*EMA alignment" | wc -l | tr -d ' ')
rsi_pass=$(tail -n ${tail_lines} "$LOG_FILE" 2>/dev/null | grep -i "BUY CONFIRM.*RSI" | wc -l | tr -d ' ')

echo "  ✅ Price > EMA: $price_above_ema раз"
echo "  ✅ MACD > Signal: $macd_above_signal раз"
echo "  ✅ EMA alignment: $ema_alignment_pass раз"
echo "  ✅ RSI < 50: $rsi_pass раз"
echo ""

# Примеры блокировок
echo "📋 ПРИМЕРЫ ЗАБЛОКИРОВАННЫХ СИГНАЛОВ:"
echo ""
tail -n ${tail_lines} "$LOG_FILE" 2>/dev/null | grep -B3 "DIRECTION CHECK.*2/4" | grep -E "\[.*USDT\]|паттерн|Отсутствуют" | head -15
echo ""

# Примеры прошедших
echo "✅ ПРИМЕРЫ ПРОШЕДШИХ СИГНАЛОВ (3/4):"
echo ""
tail -n ${tail_lines} "$LOG_FILE" 2>/dev/null | grep -B3 "DIRECTION CHECK.*3/4" | grep -E "\[.*USDT\]|паттерн|BUY CONFIRM" | head -15
echo ""

# Анализ паттернов
echo "📊 АНАЛИЗ ПО ТИПАМ ПАТТЕРНОВ:"
echo ""

classic_blocked=$(tail -n ${tail_lines} "$LOG_FILE" 2>/dev/null | grep -B2 "DIRECTION CHECK.*2/4" | grep -i "classic" | wc -l | tr -d ' ')
alt1_blocked=$(tail -n ${tail_lines} "$LOG_FILE" 2>/dev/null | grep -B2 "DIRECTION CHECK.*2/4" | grep -i "альтернативный паттерн 1\|alternative.*1" | wc -l | tr -d ' ')
alt2_blocked=$(tail -n ${tail_lines} "$LOG_FILE" 2>/dev/null | grep -B2 "DIRECTION CHECK.*2/4" | grep -i "альтернативный паттерн 2\|alternative.*2" | wc -l | tr -d ' ')

echo "  Classic паттерн заблокирован: $classic_blocked раз"
echo "  Alternative 1 заблокирован: $alt1_blocked раз"
echo "  Alternative 2 заблокирован: $alt2_blocked раз"
echo ""

# Топ символов по блокировкам
echo "📊 ТОП-10 СИМВОЛОВ ПО БЛОКИРОВКАМ DIRECTION CHECK:"
echo ""
tail -n ${tail_lines} "$LOG_FILE" 2>/dev/null | grep -B1 "DIRECTION CHECK.*2/4\|DIRECTION CHECK.*1/4" | grep -oE "\[.*USDT\]" | sort | uniq -c | sort -rn | head -10 | awk '{printf "  %-15s %5s раз\n", $2, $1}'
echo ""

# Выводы
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                          ВЫВОДЫ                                     ║"
echo "╠══════════════════════════════════════════════════════════════════════╣"
echo "║                                                                      ║"

if [ "$ema_alignment_missing" -gt "$rsi_missing" ]; then
    echo "║ 1. Основная проблема: EMA alignment не проходит                 ║"
    echo "║    → EMA Fast НЕ выше EMA Slow для большинства сигналов         ║"
    echo "║    → Возможно, рынок в боковом тренде или медвежьем             ║"
else
    echo "║ 1. Основная проблема: RSI >= 50 (не перекуплен)                 ║"
    echo "║    → RSI слишком высокий для BUY сигналов                       ║"
    echo "║    → Возможно, рынок уже перекуплен                             ║"
fi

echo "║                                                                      ║"
echo "║ 2. Price > EMA и MACD > Signal проходят чаще всего                 ║"
echo "║    → Эти условия выполняются в большинстве случаев                  ║"
echo "║                                                                      ║"

if [ "$passed_3_4" -gt 0 ]; then
    pass_rate=$(echo "scale=2; $passed_3_4 * 100 / ($total_direction_checks + 1)" | bc)
    echo "║ 3. Процент прохождения: $pass_rate%                               ║"
    echo "║    → $passed_3_4 из $total_direction_checks проходят Direction Check           ║"
else
    echo "║ 3. Процент прохождения: 0%                                        ║"
    echo "║    → Все сигналы блокируются на Direction Check                  ║"
fi

echo "║                                                                      ║"
echo "║ 4. Требуется 3 из 4 подтверждений                                   ║"
echo "║    → Текущие требования строгие, но обоснованные                    ║"
echo "║                                                                      ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# Рекомендации
echo "💡 РЕКОМЕНДАЦИИ:"
echo ""
echo "1. Проверить текущее состояние рынка:"
echo "   - Если рынок в боковом тренде → это нормально"
echo "   - Если рынок в медвежьем тренде → BUY сигналы должны блокироваться"
echo ""
echo "2. Проверить настройки EMA:"
echo "   - EMA Fast должна быть выше EMA Slow для BUY"
echo "   - Текущие настройки: EMA Fast (20), EMA Slow (50)"
echo ""
echo "3. Проверить RSI:"
echo "   - Для BUY требуется RSI < 50"
echo "   - Если RSI > 50 → рынок перекуплен, BUY не рекомендуется"
echo ""
echo "4. Анализ успешных сигналов:"
echo "   - Проверить, какие символы проходят Direction Check"
echo "   - Сравнить их индикаторы с заблокированными"
echo ""


#!/bin/bash
# -*- coding: utf-8 -*-
# Статистика по фильтрам и стадиям обработки сигналов

# Цвета
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

LOG_FILE="bot.log"
HOURS=${1:-6}  # По умолчанию 6 часов

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║        СТАТИСТИКА ФИЛЬТРОВ И СТАДИЙ ОБРАБОТКИ СИГНАЛОВ             ║"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""
echo "Период: последние $HOURS часов"
echo ""

# Получаем временную метку для фильтрации
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS
    CUTOFF_TIME=$(date -v-${HOURS}H +"%Y-%m-%d" 2>/dev/null)
    CUTOFF_HOUR=$(date -v-${HOURS}H +"%H" 2>/dev/null)
else
    # Linux
    CUTOFF_TIME=$(date -d "$HOURS hours ago" +"%Y-%m-%d")
    CUTOFF_HOUR=$(date -d "$HOURS hours ago" +"%H")
fi

CURRENT_TIME=$(date +"%Y-%m-%d %H:%M:%S")
echo "Временной диапазон: $CUTOFF_TIME (последние $HOURS часов) - $CURRENT_TIME"
echo ""

if [ ! -f "$LOG_FILE" ]; then
    echo "❌ Лог файл не найден: $LOG_FILE"
    exit 1
fi

# Функция для подсчета строк (по последним N часам)
count_lines() {
    local pattern="$1"
    # Используем tail для последних N часов (приблизительно)
    local lines_per_hour=1000  # Примерное количество строк в час
    local tail_lines=$((HOURS * lines_per_hour))
    local grep_result=$(tail -n ${tail_lines} "$LOG_FILE" 2>/dev/null | grep -i "$pattern" | wc -l | tr -d ' ')
    echo "$grep_result"
}

# Функция для подсчета уникальных символов
count_unique_symbols() {
    local pattern="$1"
    grep -i "$pattern" "$LOG_FILE" 2>/dev/null | awk -v cutoff="$CUTOFF_TIME" '$1" "$2 >= cutoff' | grep -oE '[A-Z]{2,10}USDT' | sort -u | wc -l | tr -d ' '
}

# Подсчитываем статистику
echo "📊 ПОДСЧЕТ СТАТИСТИКИ..."
echo ""

# Общая статистика
total_processed=$(count_lines "generate_signal вернул")
total_none=$(count_lines "generate_signal вернул None")
total_signals=$(count_lines "SEND_SIGNAL SUCCESS")

# Стадии фильтрации
stage_insufficient_bars=$(count_lines "Недостаточно баров")
stage_max_circles=$(count_lines "Максимальный риск.*кружков")
stage_validation_pass=$(count_lines "validation.*✅ ПРОЙДЕН")
stage_ai_score_pass=$(count_lines "ai_score.*✅ ПРОЙДЕН")
stage_ai_score_fail=$(count_lines "ai_score.*❌|ai_score.*BLOCK")
stage_anomaly_pass=$(count_lines "anomaly_filter.*✅ ПРОЙДЕН")
stage_anomaly_fail=$(count_lines "anomaly_filter.*❌|anomaly_filter.*BLOCK")
stage_volume_pass=$(count_lines "volume.*✅ ПРОЙДЕН")
stage_volume_fail=$(count_lines "volume.*❌|volume.*BLOCK")
stage_volatility_pass=$(count_lines "volatility.*✅ ПРОЙДЕН")
stage_volatility_fail=$(count_lines "volatility.*❌|volatility.*BLOCK")
stage_ema_pattern_pass=$(count_lines "ema_pattern.*✅ ПРОЙДЕН")
stage_ema_pattern_fail=$(count_lines "ema_pattern.*❌|ema_pattern.*BLOCK")
stage_btc_filter_pass=$(count_lines "BTC FILTER.*✅|тренд совпадает")
stage_btc_block=$(count_lines "BTC.*тренд.*блок|BTC.*блок")
stage_direction_check_fail=$(count_lines "DIRECTION CHECK.*недостаточно подтверждений")
stage_direction_check_pass=$(count_lines "DIRECTION CHECK.*✅ ПРОЙДЕН|calculate_direction_confidence.*✅ ПРОЙДЕН")
stage_rsi_warning=$(count_lines "RSI warning")
stage_quality_block=$(count_lines "QUALITY BLOCK")
stage_quality_pass=$(count_lines "QUALITY.*✅ ПРОЙДЕН")
stage_mtf_block=$(count_lines "MTF.*BLOCK|MTF.*блок")
stage_mtf_pass=$(count_lines "MTF.*✅ ПРОЙДЕН")
stage_correlation_block=$(count_lines "КОРРЕЛЯЦИЯ.*блок|correlation.*block")
stage_portfolio_block=$(count_lines "ПОРТФЕЛЬ.*блок|portfolio.*block")
stage_duplicate_block=$(count_lines "дубликат|duplicate.*signal")

# AUTO режим
auto_check=$(count_lines "AUTO CHECK")
auto_execute=$(count_lines "AUTO.*открыт автоматически")
auto_failed=$(count_lines "AUTO.*не удалось открыть")

# Формируем таблицу
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                    ОБЩАЯ СТАТИСТИКА                                  ║"
echo "╠══════════════════════════════════════════════════════════════════════╣"
printf "║ %-50s %8s ║\n" "Обработано символов" "$total_processed"
printf "║ %-50s %8s ║\n" "Сигналов не сгенерировано (None)" "$total_none"
printf "║ %-50s %8s ║\n" "Сигналов успешно отправлено" "$total_signals"
printf "║ %-50s %8.2f%% ║\n" "Процент успешных сигналов" "$(echo "scale=2; $total_signals * 100 / ($total_processed + 1)" | bc)"
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║              СТАДИИ ФИЛЬТРАЦИИ (ПОРЯДОК ОБРАБОТКИ)                  ║"
echo "╠══════════════════════════════════════════════════════════════════════╣"

# Стадия 1: Validation
if [ "$stage_validation_pass" -gt 0 ]; then
    printf "║ %-50s %8s ║\n" "1. Validation (проверка данных)" "$stage_validation_pass"
fi

# Стадия 2: AI Score
ai_score_total=$((stage_ai_score_pass + stage_ai_score_fail))
if [ "$ai_score_total" -gt 0 ]; then
    printf "║ %-50s %8s ║\n" "2. AI Score - всего проверок" "$ai_score_total"
    printf "║   ├─ ПРОЙДЕНО                          %8s ║\n" "$stage_ai_score_pass"
    printf "║   └─ ЗАБЛОКИРОВАНО                      %8s ║\n" "$stage_ai_score_fail"
fi

# Стадия 3: Anomaly Filter
anomaly_total=$((stage_anomaly_pass + stage_anomaly_fail))
if [ "$anomaly_total" -gt 0 ]; then
    printf "║ %-50s %8s ║\n" "3. Anomaly Filter - всего проверок" "$anomaly_total"
    printf "║   ├─ ПРОЙДЕНО                          %8s ║\n" "$stage_anomaly_pass"
    printf "║   └─ ЗАБЛОКИРОВАНО                      %8s ║\n" "$stage_anomaly_fail"
fi

# Стадия 4: Volume
volume_total=$((stage_volume_fail + stage_volume_pass))
if [ "$volume_total" -gt 0 ]; then
    printf "║ %-50s %8s ║\n" "4. Volume - всего проверок" "$volume_total"
    printf "║   ├─ ПРОЙДЕНО                          %8s ║\n" "$stage_volume_pass"
    printf "║   └─ ЗАБЛОКИРОВАНО                      %8s ║\n" "$stage_volume_fail"
fi

# Стадия 5: Volatility
volatility_total=$((stage_volatility_fail + stage_volatility_pass))
if [ "$volatility_total" -gt 0 ]; then
    printf "║ %-50s %8s ║\n" "5. Volatility - всего проверок" "$volatility_total"
    printf "║   ├─ ПРОЙДЕНО                          %8s ║\n" "$stage_volatility_pass"
    printf "║   └─ ЗАБЛОКИРОВАНО                      %8s ║\n" "$stage_volatility_fail"
fi

# Стадия 6: EMA Pattern
ema_pattern_total=$((stage_ema_pattern_pass + stage_ema_pattern_fail))
if [ "$ema_pattern_total" -gt 0 ]; then
    printf "║ %-50s %8s ║\n" "6. EMA Pattern - всего проверок" "$ema_pattern_total"
    printf "║   ├─ ПРОЙДЕНО                          %8s ║\n" "$stage_ema_pattern_pass"
    printf "║   └─ ЗАБЛОКИРОВАНО                      %8s ║\n" "$stage_ema_pattern_fail"
fi

# Стадия 7: BTC Filter
if [ "$stage_btc_filter_pass" -gt 0 ] || [ "$stage_btc_block" -gt 0 ]; then
    printf "║ %-50s %8s ║\n" "7. BTC Filter - пройдено" "$stage_btc_filter_pass"
    printf "║ %-50s %8s ║\n" "   BTC Filter - заблокировано" "$stage_btc_block"
fi

# Стадия 8: Недостаточно данных
if [ "$stage_insufficient_bars" -gt 0 ] || [ "$stage_max_circles" -gt 0 ]; then
    printf "║ %-50s %8s ║\n" "8. Недостаточно баров/данных" "$stage_insufficient_bars"
    printf "║ %-50s %8s ║\n" "   Максимальный риск (5 кружков)" "$stage_max_circles"
fi

# Стадия 9: Direction Check
direction_check_total=$((stage_direction_check_fail + stage_direction_check_pass))
if [ "$direction_check_total" -gt 0 ]; then
    printf "║ %-50s %8s ║\n" "9. Direction Check - всего проверок" "$direction_check_total"
    printf "║   ├─ ПРОЙДЕНО                          %8s ║\n" "$stage_direction_check_pass"
    printf "║   └─ ЗАБЛОКИРОВАНО                      %8s ║\n" "$stage_direction_check_fail"
fi

# Стадия 10: RSI Warning
if [ "$stage_rsi_warning" -gt 0 ]; then
    printf "║ %-50s %8s ║\n" "10. RSI Warning (предупреждение)" "$stage_rsi_warning"
fi

# Стадия 11: Quality Score
quality_total=$((stage_quality_block + stage_quality_pass))
if [ "$quality_total" -gt 0 ]; then
    printf "║ %-50s %8s ║\n" "11. Quality Score - всего проверок" "$quality_total"
    printf "║   ├─ ПРОЙДЕНО                          %8s ║\n" "$stage_quality_pass"
    printf "║   └─ ЗАБЛОКИРОВАНО                      %8s ║\n" "$stage_quality_block"
fi

# Стадия 12: MTF Confirmation
mtf_total=$((stage_mtf_block + stage_mtf_pass))
if [ "$mtf_total" -gt 0 ]; then
    printf "║ %-50s %8s ║\n" "12. MTF Confirmation - всего проверок" "$mtf_total"
    printf "║   ├─ ПРОЙДЕНО                          %8s ║\n" "$stage_mtf_pass"
    printf "║   └─ ЗАБЛОКИРОВАНО                      %8s ║\n" "$stage_mtf_block"
fi

# Стадия 13: Correlation Risk
if [ "$stage_correlation_block" -gt 0 ]; then
    printf "║ %-50s %8s ║\n" "13. Correlation Risk блокировка" "$stage_correlation_block"
fi

# Стадия 14: Portfolio Risk
if [ "$stage_portfolio_block" -gt 0 ]; then
    printf "║ %-50s %8s ║\n" "14. Portfolio Risk блокировка" "$stage_portfolio_block"
fi

# Стадия 15: Duplicate Signal
if [ "$stage_duplicate_block" -gt 0 ]; then
    printf "║ %-50s %8s ║\n" "15. Дубликат сигнала" "$stage_duplicate_block"
fi

echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# AUTO режим статистика
if [ "$auto_check" -gt 0 ]; then
    echo "╔══════════════════════════════════════════════════════════════════════╗"
    echo "║                      АВТО-РЕЖИМ                                      ║"
    echo "╠══════════════════════════════════════════════════════════════════════╣"
    printf "║ %-50s %8s ║\n" "Проверок авто-режима" "$auto_check"
    printf "║ %-50s %8s ║\n" "Успешно открыто автоматически" "$auto_execute"
    printf "║ %-50s %8s ║\n" "Ошибок авто-исполнения" "$auto_failed"
    if [ "$auto_check" -gt 0 ]; then
        auto_success_rate=$(echo "scale=2; $auto_execute * 100 / ($auto_check + 1)" | bc)
        printf "║ %-50s %7.2f%% ║\n" "Процент успешных авто-исполнений" "$auto_success_rate"
    fi
    echo "╚══════════════════════════════════════════════════════════════════════╝"
    echo ""
fi

# Топ заблокированных на каждом этапе
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║              ТОП-5 СИМВОЛОВ ПО ЗАБЛОКИРОВАННЫМ СТАДИЯМ               ║"
echo "╠══════════════════════════════════════════════════════════════════════╣"

# Находим топ символов по каждой стадии блокировки
echo "DIRECTION CHECK блокировки:"
grep -i "DIRECTION CHECK.*недостаточно" "$LOG_FILE" 2>/dev/null | awk -v cutoff="$CUTOFF_TIME" '$1" "$2 >= cutoff' | grep -oE '[A-Z]{2,10}USDT' | sort | uniq -c | sort -rn | head -5 | awk '{printf "  %-15s %5s раз\n", $2, $1}'
echo ""

echo "QUALITY BLOCK:"
grep -i "QUALITY BLOCK" "$LOG_FILE" 2>/dev/null | awk -v cutoff="$CUTOFF_TIME" '$1" "$2 >= cutoff' | grep -oE '[A-Z]{2,10}USDT' | sort | uniq -c | sort -rn | head -5 | awk '{printf "  %-15s %5s раз\n", $2, $1}'
echo ""

echo "VOLUME блокировки:"
grep -i "volume.*❌\|volume.*BLOCK" "$LOG_FILE" 2>/dev/null | awk -v cutoff="$CUTOFF_TIME" '$1" "$2 >= cutoff' | grep -oE '[A-Z]{2,10}USDT' | sort | uniq -c | sort -rn | head -5 | awk '{printf "  %-15s %5s раз\n", $2, $1}'
echo ""

echo "VOLATILITY блокировки:"
grep -i "volatility.*❌\|volatility.*BLOCK" "$LOG_FILE" 2>/dev/null | awk -v cutoff="$CUTOFF_TIME" '$1" "$2 >= cutoff' | grep -oE '[A-Z]{2,10}USDT' | sort | uniq -c | sort -rn | head -5 | awk '{printf "  %-15s %5s раз\n", $2, $1}'
echo ""

echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# Итоговая статистика
echo "╔══════════════════════════════════════════════════════════════════════╗"
echo "║                    ИТОГОВАЯ СТАТИСТИКА                               ║"
echo "╠══════════════════════════════════════════════════════════════════════╣"

total_blocks=$((stage_insufficient_bars + stage_max_circles + stage_btc_block + stage_ai_score_fail + stage_anomaly_fail + stage_direction_check_fail + stage_quality_block + stage_volume_fail + stage_volatility_fail + stage_ema_pattern_fail + stage_mtf_block + stage_correlation_block + stage_portfolio_block + stage_duplicate_block))

printf "║ %-50s %8s ║\n" "Всего обработано" "$total_processed"
printf "║ %-50s %8s ║\n" "Всего заблокировано на стадиях" "$total_blocks"
printf "║ %-50s %8s ║\n" "Успешно прошло все фильтры" "$total_signals"
if [ "$total_processed" -gt 0 ]; then
    block_rate=$(echo "scale=2; $total_blocks * 100 / ($total_processed + 1)" | bc)
    success_rate=$(echo "scale=2; $total_signals * 100 / ($total_processed + 1)" | bc)
    printf "║ %-50s %7.2f%% ║\n" "Процент блокировок" "$block_rate"
    printf "║ %-50s %7.2f%% ║\n" "Процент успешных сигналов" "$success_rate"
fi
echo "╚══════════════════════════════════════════════════════════════════════╝"
echo ""

# Информация о времени
echo "Статистика обновлена: $(date +"%Y-%m-%d %H:%M:%S")"
echo ""

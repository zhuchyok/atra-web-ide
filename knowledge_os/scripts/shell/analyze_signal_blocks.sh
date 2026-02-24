#!/bin/bash
# Скрипт для анализа блокировок сигналов за последние N часов

HOURS=${1:-6}  # По умолчанию 6 часов
LOG_FILE="bot.log"

echo "📊 АНАЛИЗ БЛОКИРОВОК СИГНАЛОВ (последние $HOURS часов)"
echo "========================================================"
echo ""

# Количество строк в логе за последние N часов
SINCE_TIME=$(date -v-${HOURS}H +"%Y-%m-%d %H:%M" 2>/dev/null || date -d "$HOURS hours ago" +"%Y-%m-%d %H:%M" 2>/dev/null)

echo "📈 СТАТИСТИКА БЛОКИРОВОК:"
echo ""

# Direction Check
DIRECTION_PASS=$(tail -10000 "$LOG_FILE" | grep -c "✅.*DIRECTION CHECK.*3/4")
DIRECTION_BLOCK=$(tail -10000 "$LOG_FILE" | grep -c "DIRECTION CHECK.*2/4\|недостаточно подтверждений")
echo "  Direction Check:"
echo "    ✅ Прошло (3/4): $DIRECTION_PASS"
echo "    🚫 Заблокировано (2/4): $DIRECTION_BLOCK"

# Quality Score
QUALITY_PASS=$(tail -10000 "$LOG_FILE" | grep -c "QUALITY PASS")
QUALITY_BLOCK=$(tail -10000 "$LOG_FILE" | grep -c "QUALITY BLOCK")
echo ""
echo "  Quality Score:"
echo "    ✅ Прошло: $QUALITY_PASS"
echo "    🚫 Заблокировано: $QUALITY_BLOCK"

# RSI Warning
RSI_BLOCK=$(tail -10000 "$LOG_FILE" | grep -c "RSI.*FILTER\|RSI.*не пройден\|RSI.*опасной")
echo ""
echo "  RSI Warning:"
echo "    🚫 Заблокировано: $RSI_BLOCK"

# Volume Quality
VOLUME_BLOCK=$(tail -10000 "$LOG_FILE" | grep -c "VOLUME BLOCK")
echo ""
echo "  Volume Quality:"
echo "    🚫 Заблокировано: $VOLUME_BLOCK"

# False Breakout
BREAKOUT_BLOCK=$(tail -10000 "$LOG_FILE" | grep -c "BREAKOUT BLOCK")
echo ""
echo "  False Breakout:"
echo "    🚫 Заблокировано: $BREAKOUT_BLOCK"

# MTF Confirmation
MTF_PASS=$(tail -10000 "$LOG_FILE" | grep -c "MTF PASS")
MTF_BLOCK=$(tail -10000 "$LOG_FILE" | grep -c "MTF BLOCK")
echo ""
echo "  MTF Confirmation:"
echo "    ✅ Прошло: $MTF_PASS"
echo "    🚫 Заблокировано: $MTF_BLOCK"

# Send Signal
SEND_BLOCK=$(tail -10000 "$LOG_FILE" | grep -c "SEND_SIGNAL BLOCK")
SEND_SUCCESS=$(tail -10000 "$LOG_FILE" | grep -c "SEND_SIGNAL SUCCESS\|PRODUCTION.*отправлен")
echo ""
echo "  Send Signal:"
echo "    ✅ Успешно отправлено: $SEND_SUCCESS"
echo "    🚫 Заблокировано: $SEND_BLOCK"

# NO SIGNAL
NO_SIGNAL=$(tail -10000 "$LOG_FILE" | grep -c "NO SIGNAL.*generate_signal вернул None")
echo ""
echo "  No Signal:"
echo "    🚫 Вернул None: $NO_SIGNAL"

echo ""
echo "========================================================"
echo "📋 ТОП-5 СИМВОЛОВ С БЛОКИРОВКАМИ:"
echo ""
tail -10000 "$LOG_FILE" | grep -E "BLOCK|NO SIGNAL" | grep -oE "\[.*USDT\]" | sort | uniq -c | sort -rn | head -5

echo ""
echo "========================================================"
echo "📊 ДЕТАЛЬНЫЙ АНАЛИЗ QUALITY SCORE:"
echo ""
tail -10000 "$LOG_FILE" | grep "QUALITY BLOCK" | grep -oE "Quality score [0-9.]+" | sort | uniq -c | sort -rn

echo ""
echo "========================================================"
echo "✅ Анализ завершен!"

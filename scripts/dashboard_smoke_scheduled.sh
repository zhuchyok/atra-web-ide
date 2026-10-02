#!/bin/bash
# Ежедневный smoke-тест дашборда ATRA (8501) с Telegram-алертом при провале.
# Ставится launchd-джобой com.atra.dashboard-smoke (09:15 ежедневно).

set -o pipefail
ROOT="/Users/bikos/Documents/atra-web-ide"
LOG="$ROOT/logs/dashboard_smoke_last.log"
PY="$ROOT/.venv/bin/python"

mkdir -p "$ROOT/logs"
echo "=== $(date '+%Y-%m-%d %H:%M:%S') ===" > "$LOG"

source "$ROOT/.env" 2>/dev/null

if "$PY" "$ROOT/scripts/dashboard_smoke_test.py" 2>&1 | tee -a "$LOG" | grep -q "Smoke-тест пройден"; then
    echo "$(date) - smoke OK" >> "$LOG"
    exit 0
fi

echo "$(date) - smoke FAILED" >> "$LOG"
if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_USER_ID" ]; then
    FAILURES=$(grep -E "^❌" "$LOG" | head -10 | tr '\n' '\n' | tail -c 3000)
    curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
        -d "chat_id=$TELEGRAM_USER_ID" \
        --data-urlencode "text=🧯 ATRA: провален smoke-тест дашборда (8501)
$FAILURES" > /dev/null
fi
exit 1

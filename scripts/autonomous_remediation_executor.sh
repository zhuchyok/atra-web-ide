#!/bin/bash
# [SINGULARITY 24.0] Autonomous Remediation Executor
# Этот скрипт запускает команды по восстановлению, сгенерированные Викторией.
# Работает полностью локально на Mac Studio.

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PENDING_CMD="$SCRIPT_DIR/pending_remediation.sh"
LOG_FILE="$SCRIPT_DIR/../logs/remediation.log"

echo "[$(date)] 🔍 Checking for pending remediation commands..." >> "$LOG_FILE"

if [ -f "$PENDING_CMD" ]; then
    echo "[$(date)] ⚡ Found remediation script. Executing..." >> "$LOG_FILE"

    # Запускаем команды восстановления
    bash "$PENDING_CMD" >> "$LOG_FILE" 2>&1

    # После выполнения удаляем файл, чтобы не зациклиться
    mv "$PENDING_CMD" "$PENDING_CMD.done"

    echo "[$(date)] ✅ Remediation complete." >> "$LOG_FILE"

    # Опционально: уведомление в Telegram (если есть интернет)
    # python3 "$SCRIPT_DIR/test_tg_notifications.py" "⚡ Автономное восстановление выполнено. Лог: logs/remediation.log"
else
    echo "[$(date)] 💤 No pending commands." >> "$LOG_FILE"
fi

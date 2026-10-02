#!/bin/bash
# Ежедневный бэкап knowledge_os (pg_dump) с ротацией (хранить 14).
# launchd: com.atra.db-backup (03:30 ежедневно). Telegram-алерт при провале.

set -o pipefail
ROOT="/Users/bikos/Documents/atra-web-ide"
BACKUP_DIR="$ROOT/backups/db"
KEEP=14
STAMP=$(date '+%Y%m%d_%H%M')
FILE="$BACKUP_DIR/knowledge_os_$STAMP.sql.gz"

mkdir -p "$BACKUP_DIR"
source "$ROOT/.env" 2>/dev/null

if docker exec knowledge_postgres pg_dump -U admin knowledge_os | gzip > "$FILE"; then
    SIZE=$(du -h "$FILE" | cut -f1)
    # проверяем, что дамп не пустой и читается
    if [ "$(stat -f%z "$FILE")" -lt 10000 ]; then
        echo "$(date) - ERROR: dump подозрительно мал: $FILE ($SIZE)" >> "$ROOT/logs/db_backup.log"
        curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
            -d "chat_id=$TELEGRAM_USER_ID" \
            --data-urlencode "text=🧯 ATRA: бэкап БД подозрительно мал ($SIZE) — проверь knowledge_postgres" > /dev/null
        exit 1
    fi
    # ротация: оставить последние KEEP
    ls -t "$BACKUP_DIR"/knowledge_os_*.sql.gz 2>/dev/null | tail -n +$((KEEP + 1)) | xargs rm -f 2>/dev/null
    echo "$(date) - OK: $FILE ($SIZE)" >> "$ROOT/logs/db_backup.log"
else
    echo "$(date) - ERROR: pg_dump failed" >> "$ROOT/logs/db_backup.log"
    curl -s -X POST "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage" \
        -d "chat_id=$TELEGRAM_USER_ID" \
        --data-urlencode "text=🧯 ATRA: ночной бэкап БД провалился — проверь knowledge_postgres" > /dev/null
    exit 1
fi

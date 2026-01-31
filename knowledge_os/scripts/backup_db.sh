#!/bin/bash
# Configuration
BACKUP_DIR="/root/knowledge_os/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/db_backup_$TIMESTAMP.sql"
GZ_FILE="${BACKUP_FILE}.gz"
TELEGRAM_TOKEN="8422371257:AAEwgSCvSv637QqDsi-EAayVYj8dsENsLbU"
CHAT_ID="556251171"

# Create backup directory if not exists
mkdir -p $BACKUP_DIR

echo "--- Backup Started: $(date) ---"

# Dump database
PGPASSWORD=secret pg_dump -U admin -h localhost -d knowledge_os > $BACKUP_FILE
if [ $? -eq 0 ]; then
    echo "Database dump successful."
else
    echo "Database dump FAILED."
    exit 1
fi

# Compress backup
gzip $BACKUP_FILE
echo "Compression completed: $GZ_FILE"

# Send to Telegram (only if this is the largest backup file today)
echo "Checking for duplicate backups today..."
TODAY_BACKUPS=$(find $BACKUP_DIR -name "db_backup_$(date +%Y%m%d)*.sql.gz" -type f 2>/dev/null)
LARGEST_BACKUP=""
LARGEST_SIZE=0

# Find the largest backup file from today
for backup in $TODAY_BACKUPS; do
    SIZE=$(stat -f%z "$backup" 2>/dev/null || stat -c%s "$backup" 2>/dev/null || echo 0)
    if [ "$SIZE" -gt "$LARGEST_SIZE" ]; then
        LARGEST_SIZE=$SIZE
        LARGEST_BACKUP="$backup"
    fi
done

# Only send if this is the largest backup today
CURRENT_SIZE=$(stat -f%z "$GZ_FILE" 2>/dev/null || stat -c%s "$GZ_FILE" 2>/dev/null || echo 0)
if [ "$GZ_FILE" = "$LARGEST_BACKUP" ] || [ "$CURRENT_SIZE" -ge "$LARGEST_SIZE" ]; then
    echo "Sending to Telegram (largest backup today: $(numfmt --to=iec-i --suffix=B $CURRENT_SIZE 2>/dev/null || echo "${CURRENT_SIZE} bytes"))..."
    CAPTION="📦 <b>Knowledge OS: Daily Database Backup</b>
📅 Date: $(date '+%Y-%m-%d %H:%M:%S')
📂 File: $(basename $GZ_FILE)
💾 Size: $(numfmt --to=iec-i --suffix=B $CURRENT_SIZE 2>/dev/null || echo "${CURRENT_SIZE} bytes")
🔐 Status: SECURE"

    curl -F document=@"$GZ_FILE" \
         -F caption="$CAPTION" \
         -F parse_mode="HTML" \
         "https://api.telegram.org/bot$TELEGRAM_TOKEN/sendDocument?chat_id=$CHAT_ID"

    if [ $? -eq 0 ]; then
        echo "Telegram delivery successful."
    else
        echo "Telegram delivery FAILED."
    fi
else
    echo "Skipping Telegram delivery: found larger backup today ($(basename $LARGEST_BACKUP), $(numfmt --to=iec-i --suffix=B $LARGEST_SIZE 2>/dev/null || echo "${LARGEST_SIZE} bytes"))"
    echo "Current backup size: $(numfmt --to=iec-i --suffix=B $CURRENT_SIZE 2>/dev/null || echo "${CURRENT_SIZE} bytes")"
fi

# Keep only last 7 days of backups locally
find $BACKUP_DIR -name "db_backup_*.sql.gz" -mtime +7 -delete

# Cloud sync to S3 (if configured)
if command -v rclone &> /dev/null && [ -f "/root/.config/rclone/rclone.conf" ]; then
    echo "Starting cloud sync to S3..."
    rclone sync $BACKUP_DIR knowledge_os_s3:backups/ --progress
    echo "Cloud sync completed."
else
    echo "Cloud sync skipped: rclone not configured."
fi

echo "--- Backup Finished: $(date) ---"

#!/bin/bash
# Configuration
KNOWLEDGE_OS_DIR="/root/knowledge_os"
BACKUP_DIR="$KNOWLEDGE_OS_DIR/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
TEMP_DIR="/tmp/brain_backup_$TIMESTAMP"
BUNDLE_FILE="$BACKUP_DIR/brain_recovery_$TIMESTAMP.tar.gz"

TELEGRAM_TOKEN="8422371257:AAEwgSCvSv637QqDsi-EAayVYj8dsENsLbU"
CHAT_ID="556251171"

mkdir -p $BACKUP_DIR
mkdir -p $TEMP_DIR

echo "--- Enhanced Backup Started: $(date) ---"

# 1. Dump Database
echo "Dumping database..."
PGPASSWORD=secret pg_dump -U admin -h localhost -d knowledge_os > $TEMP_DIR/db_dump.sql

# 2. Collect metadata
echo "Collecting system metadata..."
cp $KNOWLEDGE_OS_DIR/app/requirements.txt $TEMP_DIR/
ps aux | grep python3 > $TEMP_DIR/running_processes.txt

# 3. Create Bundle
echo "Creating recovery bundle..."
tar -czf $BUNDLE_FILE -C $TEMP_DIR .

# 4. Get System Stats for Telegram
EXPERT_COUNT=$(PGPASSWORD=secret psql -U admin -h localhost -d knowledge_os -t -A -c "SELECT count(*) FROM experts")
KNOWLEDGE_COUNT=$(PGPASSWORD=secret psql -U admin -h localhost -d knowledge_os -t -A -c "SELECT count(*) FROM knowledge_nodes")

# 5. Send to Telegram
echo "Sending to Telegram..."
CAPTION="🚀 <b>KNOWLEDGE OS: RECOVERY BUNDLE</b>
━━━━━━━━━━━━━━━━━━━━━━━━
👥 Experts: <b>$EXPERT_COUNT</b>
🧠 Knowledge: <b>$KNOWLEDGE_COUNT nodes</b>
📂 Bundle: <code>$(basename $BUNDLE_FILE)</code>
🛠 Restore command: 
<code>python3 scripts/restore_brain.py backups/$(basename $BUNDLE_FILE)</code>
━━━━━━━━━━━━━━━━━━━━━━━━
📅 <i>$(date '+%Y-%m-%d %H:%M:%S')</i>"

curl -F document=@"$BUNDLE_FILE" \
     -F caption="$CAPTION" \
     -F parse_mode="HTML" \
     "https://api.telegram.org/bot$TELEGRAM_TOKEN/sendDocument?chat_id=$CHAT_ID"

# Cleanup
rm -rf $TEMP_DIR
find $BACKUP_DIR -name "brain_recovery_*.tar.gz" -mtime +14 -delete

echo "--- Enhanced Backup Finished ---"


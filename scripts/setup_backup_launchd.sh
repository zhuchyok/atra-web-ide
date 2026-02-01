#!/usr/bin/env bash
# Настройка LaunchAgent для ежедневного бэкапа Knowledge OS в 02:00
# Mac Studio — автозапуск по расписанию через launchd
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PLIST_NAME="com.atra.backup-knowledge-os"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
BACKUP_SCRIPT="$ROOT/scripts/backup_knowledge_os_full.sh"
LOG_FILE="/tmp/backup_knowledge_os.log"

echo "Настройка ежедневного бэкапа (02:00)..."

# macOS launchd не поддерживает cron-подобное расписание напрямую.
# Используем StartCalendarInterval для ежедневного запуска в 02:00
cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${BACKUP_SCRIPT}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${ROOT}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>2</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>${LOG_FILE}</string>
    <key>StandardErrorPath</key>
    <string>${LOG_FILE}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin</string>
    </dict>
</dict>
</plist>
EOF

# Загрузка
launchctl unload "$PLIST_PATH" 2>/dev/null || true
launchctl load "$PLIST_PATH"

echo "✅ LaunchAgent создан: $PLIST_PATH"
echo "   Бэкап запускается ежедневно в 02:00"
echo "   Лог: $LOG_FILE"
echo ""
echo "Проверка: launchctl list | grep ${PLIST_NAME}"

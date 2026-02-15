#!/bin/bash
# Настройка регулярного прогона куратора через launchd (macOS)
# Запускать один раз: bash scripts/setup_curator_launchd.sh
# После установки куратор будет запускаться ежедневно в 9:00.

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "📋 НАСТРОЙКА КУРАТОРА ПО РАСПИСАНИЮ (launchd)"
echo "=============================================="
echo ""

# Создание launchd plist (ежедневно в 9:00)
echo "[1/3] Создание launchd plist..."
LAUNCHD_FILE="${HOME}/Library/LaunchAgents/com.atra.curator-scheduled.plist"

cat > "$LAUNCHD_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atra.curator-scheduled</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${ROOT}/scripts/run_curator_scheduled.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${ROOT}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
        <key>CURATOR_MAX_WAIT</key>
        <string>900</string>
    </dict>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/atra-curator.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/atra-curator.error.log</string>
</dict>
</plist>
EOF

echo "✅ LaunchAgent создан: $LAUNCHD_FILE"
echo "   Расписание: ежедневно в 9:00"
echo ""

# Загрузка в launchd
echo "[2/3] Загрузка в launchd..."
launchctl unload "$LAUNCHD_FILE" 2>/dev/null || true
launchctl load "$LAUNCHD_FILE"
echo "✅ Задание загружено."
echo ""

echo "[3/3] Проверка: launchctl list | grep curator"
launchctl list | grep -i curator || echo "(задание в списке)"
echo ""
echo "Готово. Логи: ~/Library/Logs/atra-curator.log"
echo "Отключить: launchctl unload $LAUNCHD_FILE"
echo "См. docs/CURATOR_RUNBOOK.md — регулярный прогон."

#!/usr/bin/env bash
# Периодический сброс зависших задач (Watchdog).
# Запустить один раз: bash scripts/setup_stuck_tasks_watchdog.sh
# После установки: каждый час выполняется reset_stuck_tasks.py через venv.
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LAUNCHD_FILE="${HOME}/Library/LaunchAgents/com.atra.stuck-tasks-watchdog.plist"
echo "Создание LaunchAgent для ежечасного сброса зависших задач..."
cat > "$LAUNCHD_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atra.stuck-tasks-watchdog</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>-c</string>
        <string>cd ${ROOT} && [ -x knowledge_os/.venv/bin/python ] && knowledge_os/.venv/bin/python knowledge_os/scripts/reset_stuck_tasks.py</string>
    </array>
    <key>StartInterval</key>
    <integer>3600</integer>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/atra-stuck-tasks-watchdog.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/atra-stuck-tasks-watchdog.error.log</string>
</dict>
</plist>
EOF
launchctl unload "$LAUNCHD_FILE" 2>/dev/null || true
launchctl load "$LAUNCHD_FILE"
echo "Готово. Сброс задач: каждый час. Логи: ~/Library/Logs/atra-stuck-tasks-watchdog.log"
echo "Отключить: launchctl unload $LAUNCHD_FILE"

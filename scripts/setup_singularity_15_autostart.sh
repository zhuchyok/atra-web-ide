#!/usr/bin/env bash
# Включить автозапуск Singularity 15.0 (Victoria + Open WebUI) при входе в систему.
# Один раз: ./scripts/setup_singularity_15_autostart.sh
#
# Что делает:
# - Устанавливает launchd-юнит, который при входе запускает контейнеры Knowledge OS
#   (в т.ч. Victoria и Open WebUI). Используется тот же скрипт, что и для Singularity 14.
# - Либо использует уже настроенный полный автозапуск (setup_complete_autostart.sh).
# Проверка: launchctl list | grep com.atra.singularity

set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== Singularity 15.0: автозапуск при входе ==="
echo ""

# Используем существующий plist, если он указывает на скрипт в autostart/
PLIST_SRC="$ROOT/scripts/autostart/com.atra.singularity.autostart.plist"
LAUNCHD_DEST="${HOME}/Library/LaunchAgents/com.atra.singularity.autostart.plist"
START_SCRIPT="$ROOT/scripts/autostart/start_singularity_10.sh"

if [ ! -f "$START_SCRIPT" ]; then
  echo "Скрипт $START_SCRIPT не найден. Используйте полную настройку:"
  echo "  ./scripts/setup_complete_autostart.sh"
  exit 1
fi

mkdir -p "$ROOT/logs"
# Генерируем plist с путём текущего репозитория
cat > "$LAUNCHD_DEST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atra.singularity.autostart</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>$ROOT/scripts/autostart/start_singularity_10.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$ROOT/logs/autostart_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>$ROOT/logs/autostart_stderr.log</string>
    <key>WorkingDirectory</key>
    <string>$ROOT</string>
</dict>
</plist>
EOF

launchctl unload "$LAUNCHD_DEST" 2>/dev/null || true
launchctl load "$LAUNCHD_DEST"

if launchctl list 2>/dev/null | grep -q "com.atra.singularity.autostart"; then
  echo "Автозапуск включён: при входе в систему будут подняты Victoria и Open WebUI (порт 3005)."
  echo "Проверка: ./scripts/verify_singularity_15_openwebui.sh"
else
  echo "Не удалось загрузить launchd-юнит. Проверьте: cat $LAUNCHD_DEST"
  exit 1
fi

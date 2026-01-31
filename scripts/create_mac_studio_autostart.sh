#!/bin/bash
# Создание автозапуска для Mac Studio
# Запускать на Mac Studio: bash scripts/create_mac_studio_autostart.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "🔄 НАСТРОЙКА АВТОЗАПУСКА НА MAC STUDIO"
echo "=============================================="
echo ""

LAUNCHD_FILE="${HOME}/Library/LaunchAgents/com.atra.mac-studio-startup.plist"

cat > "$LAUNCHD_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atra.mac-studio-startup</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${ROOT}/scripts/start_all_on_mac_studio.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${ROOT}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/atra-mac-studio-startup.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/atra-mac-studio-startup.error.log</string>
</dict>
</plist>
EOF

echo "✅ LaunchAgent создан: $LAUNCHD_FILE"
echo ""

# Загрузка в launchd
launchctl unload "$LAUNCHD_FILE" 2>/dev/null || true
launchctl load "$LAUNCHD_FILE" 2>/dev/null || {
    echo "⚠️  Не удалось загрузить в launchd"
    echo "   Попробуйте вручную: launchctl load $LAUNCHD_FILE"
}

echo "✅ Автозапуск настроен"
echo ""
echo "📋 Автозапуск будет:"
echo "   - При загрузке системы"
echo "   - Каждые 5 минут (проверка)"
echo ""
echo "📊 Логи:"
echo "   ${HOME}/Library/Logs/atra-mac-studio-startup.log"
echo ""

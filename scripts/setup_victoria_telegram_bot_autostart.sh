#!/bin/bash
# Настройка автозапуска Victoria Telegram Bot через launchd
# Запускать один раз: bash scripts/setup_victoria_telegram_bot_autostart.sh
# Мировые практики: RunAtLoad + KeepAlive для долгоживущих сервисов

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Предпочитаем .venv (Pillow, pypdf уже установлены)
if [ -x "$ROOT/.venv/bin/python" ]; then
    PYTHON3="$ROOT/.venv/bin/python"
else
    PYTHON3="$(which python3 2>/dev/null || echo "/usr/bin/python3")"
fi
LAUNCHD_PLIST="${HOME}/Library/LaunchAgents/com.atra.victoria-telegram-bot.plist"

echo "=============================================="
echo "🤖 Автозапуск Victoria Telegram Bot"
echo "=============================================="
echo ""
echo "  ROOT: $ROOT"
echo "  Python: $PYTHON3"
echo "  Plist:  $LAUNCHD_PLIST"
echo ""

# 1. Создание plist
echo "[1/2] Создание LaunchAgent..."
mkdir -p "$(dirname "$LAUNCHD_PLIST")"

cat > "$LAUNCHD_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atra.victoria-telegram-bot</string>
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON3}</string>
        <string>-m</string>
        <string>src.agents.bridge.victoria_telegram_bot</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${ROOT}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
        <key>Crashed</key>
        <true/>
    </dict>
    <key>StandardOutPath</key>
    <string>${ROOT}/victoria_bot.log</string>
    <key>StandardErrorPath</key>
    <string>${ROOT}/victoria_bot.err.log</string>
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF

echo "✅ Plist создан: $LAUNCHD_PLIST"
echo ""

# 2. Загрузка в launchd
echo "[2/2] Загрузка в launchd..."
launchctl unload "$LAUNCHD_PLIST" 2>/dev/null || true
launchctl load "$LAUNCHD_PLIST" 2>/dev/null || {
    echo "⚠️ Не удалось загрузить. Попробуйте: launchctl load $LAUNCHD_PLIST"
    exit 1
}

if launchctl list 2>/dev/null | grep -q "com.atra.victoria-telegram-bot"; then
    echo "✅ Victoria Telegram Bot загружен в launchd (автозапуск при входе в систему)"
else
    echo "⚠️ Job не найден в launchctl list"
fi
echo ""
echo "📋 Управление:"
echo "   Запуск сейчас:  launchctl start com.atra.victoria-telegram-bot"
echo "   Остановка:      launchctl stop com.atra.victoria-telegram-bot"
echo "   Логи:           tail -f $ROOT/victoria_bot.log"
echo ""

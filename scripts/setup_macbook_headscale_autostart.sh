#!/bin/bash
# Настройка автозапуска подключения к Headscale на MacBook

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "🍎 НАСТРОЙКА АВТОЗАПУСКА HEADSCALE НА MACBOOK"
echo "=============================================="
echo ""

SERVER_IP="185.177.216.15"
HEADSCALE_PORT=8080
HEADSCALE_URL="http://${SERVER_IP}:${HEADSCALE_PORT}"

echo "📋 Параметры:"
echo "   Headscale URL: $HEADSCALE_URL"
echo ""

# Проверка установки Tailscale
if ! command -v tailscale >/dev/null 2>&1; then
    echo "📥 Установка Tailscale..."
    if command -v brew >/dev/null 2>&1; then
        brew install tailscale
    else
        echo "❌ Homebrew не найден. Установите Tailscale вручную:"
        echo "   https://tailscale.com/download"
        exit 1
    fi
fi

echo "✅ Tailscale установлен"
echo ""

# Создание скрипта для подключения
CONNECT_SCRIPT="${HOME}/.headscale_connect.sh"
cat > "$CONNECT_SCRIPT" << EOF
#!/bin/bash
# Автоматическое подключение к Headscale на Mac Studio через SSH туннель

SERVER_IP="${SERVER_IP}"
HEADSCALE_PORT=${HEADSCALE_PORT}
HEADSCALE_URL="${HEADSCALE_URL}"

# Проверка доступности Headscale
if curl -s --connect-timeout 5 "$HEADSCALE_URL" >/dev/null 2>&1; then
    echo "[$(date)] Headscale доступен, подключаюсь..."

    # Подключение к Headscale
    tailscale up --login-server="$HEADSCALE_URL" --accept-routes 2>&1 | tee -a ~/Library/Logs/headscale-connect.log

    if [ \${PIPESTATUS[0]} -eq 0 ]; then
        echo "[$(date)] ✅ Подключение к Headscale успешно"
    else
        echo "[$(date)] ⚠️  Ошибка подключения к Headscale"
    fi
else
    echo "[$(date)] ⚠️  Headscale недоступен на $HEADSCALE_URL"
    echo "   Проверьте, что SSH туннели запущены на Mac Studio"
fi
EOF

chmod +x "$CONNECT_SCRIPT"
echo "✅ Создан скрипт подключения: $CONNECT_SCRIPT"
echo ""

# Создание launchd service для автозапуска
LAUNCHD_HEADSCALE="${HOME}/Library/LaunchAgents/com.atra.headscale-connect.plist"

cat > "$LAUNCHD_HEADSCALE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atra.headscale-connect</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${CONNECT_SCRIPT}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/headscale-connect.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/headscale-connect.err.log</string>
</dict>
</plist>
EOF

launchctl unload "$LAUNCHD_HEADSCALE" 2>/dev/null || true
launchctl load "$LAUNCHD_HEADSCALE" 2>/dev/null || true

if launchctl list 2>/dev/null | grep -q "com.atra.headscale-connect"; then
    echo "✅ Автозапуск настроен через launchd"
    echo "   Логи: ${HOME}/Library/Logs/headscale-connect.log"
else
    echo "⚠️  Автозапуск не настроен (проверьте вручную)"
fi

echo ""
echo "🔧 Первое подключение..."
bash "$CONNECT_SCRIPT"

echo ""
echo "=============================================="
echo "✅ НАСТРОЙКА ЗАВЕРШЕНА"
echo "=============================================="
echo ""
echo "📝 Информация:"
echo "   Headscale URL: $HEADSCALE_URL"
echo "   Скрипт подключения: $CONNECT_SCRIPT"
echo "   Launchd service: $LAUNCHD_HEADSCALE"
echo ""
echo "🔄 Автозапуск:"
echo "   - При загрузке MacBook автоматически подключится к Headscale"
echo "   - Проверка каждые 5 минут"
echo ""

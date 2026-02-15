#!/bin/bash
# =============================================================================
# Настройка автозапуска MLX API Server через launchd (с wrapper — перезапуск при падении)
# Запускать на Mac Studio: bash scripts/setup_mlx_autostart.sh
# См. docs/MLX_PYTHON_CRASH_CAUSE.md — при краше Python перезапускает start_mlx_server.sh
# =============================================================================

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "🚀 Настройка автозапуска MLX API Server (wrapper)"
echo "=============================================="
echo ""

# 1. Создание launchd plist для MLX API Server (через wrapper — автоперезапуск при падении)
echo "[1/3] Создание launchd plist для MLX API Server..."
LAUNCHD_MLX="${HOME}/Library/LaunchAgents/com.atra.mlx-api-server.plist"

cat > "$LAUNCHD_MLX" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atra.mlx-api-server</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${ROOT}/scripts/start_mlx_server.sh</string>
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
    <string>${HOME}/Library/Logs/atra-mlx-api-server.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/atra-mlx-api-server.error.log</string>
    <key>ThrottleInterval</key>
    <integer>10</integer>
    <key>StartInterval</key>
    <integer>60</integer>
</dict>
</plist>
EOF

echo "✅ LaunchAgent создан: $LAUNCHD_MLX"
echo ""

# 2. Загрузка в launchd
echo "[2/3] Загрузка в launchd..."
launchctl unload "$LAUNCHD_MLX" 2>/dev/null || true
launchctl load "$LAUNCHD_MLX" 2>/dev/null || {
    echo "⚠️ Не удалось загрузить в launchd"
    echo "   Попробуйте вручную: launchctl load $LAUNCHD_MLX"
}

if launchctl list 2>/dev/null | grep -q "com.atra.mlx-api-server"; then
    echo "✅ MLX API Server загружен в launchd"
else
    echo "⚠️ MLX API Server не загружен (проверьте вручную)"
fi
echo ""

# 3. Проверка монитора
echo "[3/3] Проверка монитора MLX API Server..."
if launchctl list 2>/dev/null | grep -q "com.atra.mlx-monitor"; then
    echo "✅ Монитор MLX API Server уже настроен"
else
    echo "⚠️ Монитор не настроен. Запустите:"
    echo "   bash scripts/setup_system_auto_recovery.sh"
fi
echo ""

echo "=============================================="
echo "✅ НАСТРОЙКА ЗАВЕРШЕНА"
echo "=============================================="
echo ""
echo "📋 Команды:"
echo "   Статус:     launchctl list | grep mlx"
echo "   Запуск:     launchctl start com.atra.mlx-api-server"
echo "   Остановка:  launchctl stop com.atra.mlx-api-server"
echo "   Логи:       tail -f ~/Library/Logs/atra-mlx-api-server.log"
echo ""

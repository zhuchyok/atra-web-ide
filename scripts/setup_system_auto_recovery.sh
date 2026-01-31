#!/bin/bash
# Настройка системы самовосстановления через launchd
# Запускать один раз: bash scripts/setup_system_auto_recovery.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "🔄 НАСТРОЙКА СИСТЕМЫ САМОВОССТАНОВЛЕНИЯ"
echo "=============================================="
echo ""

# 1. Создание launchd plist для автозапуска при загрузке
echo "[1/3] Создание launchd plist..."
LAUNCHD_FILE="${HOME}/Library/LaunchAgents/com.atra.auto-recovery.plist"

cat > "$LAUNCHD_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atra.auto-recovery</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${ROOT}/scripts/system_auto_recovery.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${ROOT}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/atra-auto-recovery.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/atra-auto-recovery.error.log</string>
</dict>
</plist>
EOF

echo "✅ LaunchAgent создан: $LAUNCHD_FILE"
echo ""

# 2. Загрузка в launchd
echo "[2/3] Загрузка в launchd..."
launchctl unload "$LAUNCHD_FILE" 2>/dev/null || true
launchctl load "$LAUNCHD_FILE" 2>/dev/null || {
    echo "⚠️ Не удалось загрузить в launchd"
    echo "   Попробуйте вручную: launchctl load $LAUNCHD_FILE"
}

if launchctl list 2>/dev/null | grep -q "com.atra.auto-recovery"; then
    echo "✅ Система самовосстановления загружена в launchd"
else
    echo "⚠️ Система не загружена (проверьте вручную)"
fi
echo ""

# 3. Настройка мониторинга MLX API Server
echo "[3/4] Настройка мониторинга MLX API Server..."
LAUNCHD_MLX_MONITOR="${HOME}/Library/LaunchAgents/com.atra.mlx-monitor.plist"

cat > "$LAUNCHD_MLX_MONITOR" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atra.mlx-monitor</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${ROOT}/scripts/monitor_mlx_api_server.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${ROOT}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/atra-mlx-monitor.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/atra-mlx-monitor.error.log</string>
</dict>
</plist>
EOF

launchctl unload "$LAUNCHD_MLX_MONITOR" 2>/dev/null || true
launchctl load "$LAUNCHD_MLX_MONITOR" 2>/dev/null || {
    echo "⚠️ Не удалось загрузить мониторинг MLX в launchd"
}

if launchctl list 2>/dev/null | grep -q "com.atra.mlx-monitor"; then
    echo "   ✅ Мониторинг MLX API Server настроен через launchd"
else
    echo "   ⚠️ Мониторинг MLX не настроен (проверьте вручную)"
fi
echo ""

# 4. Первый запуск для проверки
echo "[4/4] Первый запуск для проверки..."
bash scripts/system_auto_recovery.sh
echo ""

echo "=============================================="
echo "✅ НАСТРОЙКА ЗАВЕРШЕНА"
echo "=============================================="
echo ""
echo "📋 Система самовосстановления будет:"
echo "   - Запускаться автоматически при загрузке системы"
echo "   - Проверять все сервисы каждые 5 минут"
echo "   - Автоматически исправлять проблемы"
echo ""
echo "📊 Логи:"
echo "   ${HOME}/Library/Logs/atra-auto-recovery.log"
echo "   ${HOME}/Library/Logs/atra-auto-recovery.error.log"
echo ""
echo "🔄 Проверка статуса:"
echo "   launchctl list | grep auto-recovery"
echo "   tail -f ~/Library/Logs/atra-auto-recovery.log"
echo ""

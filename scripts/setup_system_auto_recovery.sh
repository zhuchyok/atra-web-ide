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

# 0. Лаунчер для Recovery Listener (порт 9099) — вне Documents, чтобы launchd мог запустить
ATRA_SUPPORT="${HOME}/Library/Application Support/Atra"
mkdir -p "$ATRA_SUPPORT"
LAUNCHER_RECOVERY_LISTENER="${ATRA_SUPPORT}/launch_recovery_listener.sh"
cat > "$LAUNCHER_RECOVERY_LISTENER" << 'LAUNCHER_EOF'
#!/bin/bash
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
ROOT="${ATRA_PROJECT_ROOT:-}"
if [[ -z "$ROOT" || ! -f "$ROOT/scripts/host_recovery_listener.py" ]]; then
  echo "ATRA_PROJECT_ROOT not set or host_recovery_listener.py not found" >&2
  exit 1
fi
exec python3 "$ROOT/scripts/host_recovery_listener.py"
LAUNCHER_EOF
chmod +x "$LAUNCHER_RECOVERY_LISTENER"
echo "✅ Лаунчер Recovery Listener: $LAUNCHER_RECOVERY_LISTENER"
echo ""

# 1. Создание launchd plist для автозапуска при загрузке
echo "[1/5] Создание launchd plist (автовосстановление каждые 5 мин)..."
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
        <string>/Users/bikos/Library/Application Support/Atra/launch_recovery.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/tmp</string>
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
echo "[2/5] Загрузка в launchd..."
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
echo "[3/5] Настройка мониторинга MLX API Server..."
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
        <string>/Users/bikos/Library/Application Support/Atra/launch_mlx_monitor.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/tmp</string>
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

# 4. Recovery Listener (порт 9099) — Виктория/оркестратор шлёт сюда POST при падении MLX/Ollama; listener запускает system_auto_recovery.sh и поднимает MLX без участия пользователя
echo "[4/5] Recovery Listener (порт 9099 — автозапуск при загрузке)..."
LAUNCHD_RECOVERY_LISTENER="${HOME}/Library/LaunchAgents/com.atra.recovery-listener.plist"
cat > "$LAUNCHD_RECOVERY_LISTENER" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atra.recovery-listener</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${LAUNCHER_RECOVERY_LISTENER}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/tmp</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin</string>
        <key>ATRA_PROJECT_ROOT</key>
        <string>${ROOT}</string>
    </dict>
    <key>LimitLoadToSessionType</key>
    <string>Aqua</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/atra-recovery-listener.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/atra-recovery-listener.error.log</string>
</dict>
</plist>
EOF
GUI_DOMAIN="gui/$(id -u)"
launchctl bootout "$GUI_DOMAIN" "$LAUNCHD_RECOVERY_LISTENER" 2>/dev/null || true
if launchctl bootstrap "$GUI_DOMAIN" "$LAUNCHD_RECOVERY_LISTENER" 2>/dev/null; then
    echo "   ✅ Recovery Listener загружен в launchd ($GUI_DOMAIN) — Виктория сможет поднимать MLX по webhook"
else
    launchctl unload "$LAUNCHD_RECOVERY_LISTENER" 2>/dev/null || true
    launchctl load "$LAUNCHD_RECOVERY_LISTENER" 2>/dev/null || true
    if launchctl list 2>/dev/null | grep -q "com.atra.recovery-listener"; then
        echo "   ✅ Recovery Listener загружен (user domain)"
    else
        echo "   ⚠️ Recovery Listener не загружен. Вручную: python3 scripts/host_recovery_listener.py"
    fi
fi
echo ""

# 5. Первый запуск для проверки
echo "[5/5] Первый запуск для проверки..."
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
echo "📡 Recovery Listener (порт 9099): запускается автоматически при загрузке."
echo "   При падении MLX/Ollama оркестратор (Виктория) шлёт POST на host:9099/recover → MLX поднимается без ваших действий."
echo "   Статус: launchctl list | grep recovery-listener"
echo ""

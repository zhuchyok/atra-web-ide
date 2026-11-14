#!/bin/bash
# Полная настройка автозапуска корпорации ATRA на Mac Studio
# Запускать один раз: bash scripts/setup_complete_autostart.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SETUP_FAIL=0

echo "=============================================="
echo "🚀 Полная настройка автозапуска корпорации ATRA"
echo "=============================================="
echo ""

# 1. Проверка Docker Desktop автозапуска
echo "[1/5] Проверка Docker Desktop автозапуска..."
DOCKER_AUTOSTART=$(defaults read com.docker.docker StartAtLogin 2>/dev/null || echo "0")
if [ "$DOCKER_AUTOSTART" = "1" ]; then
    echo "   ✅ Docker Desktop автозапуск уже настроен"
else
    echo "   ⚠️  Настраиваю Docker Desktop автозапуск..."
    if defaults write com.docker.docker 'StartAtLogin' -bool true 2>/dev/null; then
        echo "   ✅ Docker Desktop автозапуск настроен"
    else
        echo "   ❌ Не удалось настроить Docker Desktop автозапуск"
        SETUP_FAIL=1
    fi
fi
echo ""

# 2. Проверка restart policy в docker-compose.yml
echo "[2/5] Проверка restart policy в docker-compose.yml..."
COMPOSE_FILE="knowledge_os/docker-compose.yml"
if [ -f "$COMPOSE_FILE" ]; then
    RESTART_ALWAYS=$(grep -c "restart: always" "$COMPOSE_FILE" || echo "0")
    RESTART_UNLESS_STOPPED=$(grep -c "restart: unless-stopped" "$COMPOSE_FILE" || echo "0")
    echo "   ✅ Контейнеры с 'restart: always': $RESTART_ALWAYS"
    echo "   ✅ Контейнеры с 'restart: unless-stopped': $RESTART_UNLESS_STOPPED"
    if [ "${RESTART_ALWAYS:-0}" = "0" ] && [ "${RESTART_UNLESS_STOPPED:-0}" = "0" ]; then
        echo "   ❌ Нет restart policy в compose"
        SETUP_FAIL=1
    else
        echo "   ✅ Контейнеры будут запускаться автоматически при старте Docker"
    fi
else
    echo "   ❌ docker-compose.yml не найден"
    SETUP_FAIL=1
fi
echo ""

# 3. Настройка Ollama автозапуска
echo "[3/5] Настройка Ollama автозапуска..."
if command -v brew >/dev/null 2>&1; then
    if brew services list 2>/dev/null | grep -q ollama; then
        OLLAMA_STATUS=$(brew services list | grep ollama | awk '{print $2}')
        if [ "$OLLAMA_STATUS" = "started" ]; then
            echo "   ✅ Ollama уже запущен через brew services"
        else
            echo "   ⚠️  Запускаю Ollama через brew services..."
            if ! brew services start ollama 2>/dev/null; then
                echo "   ❌ Не удалось запустить Ollama через brew"
                SETUP_FAIL=1
            fi
        fi
    else
        echo "   ⚠️  Ollama не найден в brew services (не блокер, если 11434 уже жив)"
    fi
else
    echo "   ⚠️  Homebrew не найден, проверьте Ollama автозапуск вручную"
fi
echo ""

# 4. Настройка Victoria MCP Server
echo "[4/5] Настройка Victoria MCP Server автозапуска..."
if [ -f "scripts/victoria/quick_victoria_autostart.sh" ]; then
    if bash scripts/victoria/quick_victoria_autostart.sh; then
        echo "   ✅ Victoria MCP Server настроен на автозапуск"
    else
        echo "   ❌ Victoria MCP autostart failed"
        SETUP_FAIL=1
    fi
else
    echo "   ⚠️  Скрипт quick_victoria_autostart.sh не найден (не блокер)"
fi
echo ""

# 5. Настройка SSH Reverse Tunnel для Headscale
echo "[5/7] Настройка SSH Reverse Tunnel автозапуска..."
if [ -f "scripts/setup_ssh_tunnel_for_headscale.sh" ]; then
    if bash scripts/setup_ssh_tunnel_for_headscale.sh 2>&1 | grep -E "(✅|⚠️|❌|📊|🌐)" || true; then
        :
    fi
    if launchctl list 2>/dev/null | grep -q "com.atra.ssh-tunnel-headscale"; then
        echo "   ✅ SSH Reverse Tunnel настроен на автозапуск"
    else
        echo "   ⚠️  SSH Reverse Tunnel не подтверждён в launchctl (не блокер)"
    fi
else
    echo "   ⚠️  Скрипт setup_ssh_tunnel_for_headscale.sh не найден"
fi
echo ""

# 6. Настройка Self-Check System автозапуска
echo "[6/7] Настройка Self-Check System автозапуска..."
LAUNCHD_SELFCHECK="${HOME}/Library/LaunchAgents/com.atra.self-check.plist"
mkdir -p "${HOME}/Library/LaunchAgents"
cat > "$LAUNCHD_SELFCHECK" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atra.self-check</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${ROOT}/scripts/start_autonomous_systems.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${ROOT}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/atra-self-check.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/atra-self-check.err.log</string>
    <key>StartInterval</key>
    <integer>300</integer>
</dict>
</plist>
EOF
launchctl unload "$LAUNCHD_SELFCHECK" 2>/dev/null || true
launchctl load "$LAUNCHD_SELFCHECK" 2>/dev/null || true
if launchctl list 2>/dev/null | grep -q "com.atra.self-check"; then
    echo "   ✅ Self-Check System автозапуск настроен через launchd"
else
    echo "   ❌ Self-Check System не настроен"
    SETUP_FAIL=1
fi
echo ""

# 7. Настройка Model Tracker автозапуска
echo "[7/8] Настройка Model Tracker автозапуска..."
LAUNCHD_MODELTRACKER="${HOME}/Library/LaunchAgents/com.atra.model-tracker.plist"
cat > "$LAUNCHD_MODELTRACKER" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atra.model-tracker</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${ROOT}/scripts/start_model_tracker.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${ROOT}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StartInterval</key>
    <integer>3600</integer>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/model-tracker.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/model-tracker.err.log</string>
</dict>
</plist>
EOF
launchctl unload "$LAUNCHD_MODELTRACKER" 2>/dev/null || true
launchctl load "$LAUNCHD_MODELTRACKER" 2>/dev/null || true
if launchctl list 2>/dev/null | grep -q "com.atra.model-tracker"; then
    echo "   ✅ Model Tracker автозапуск настроен через launchd"
else
    echo "   ❌ Model Tracker не настроен"
    SETUP_FAIL=1
fi
echo ""

# 8. Настройка автозапуска MLX API Server (запасной слой; live brain = Ollama 11434)
echo "[8/10] Настройка автозапуска MLX API Server..."
if [ -f "scripts/setup_mlx_autostart.sh" ]; then
    if bash scripts/setup_mlx_autostart.sh; then
        echo "   ✅ MLX API Server настроен на автозапуск при входе"
    else
        echo "   ⚠️  MLX autostart failed (не блокер: live brain = Ollama 11434)"
    fi
else
    echo "   ⚠️  setup_mlx_autostart.sh не найден"
fi
echo ""

# 9. Настройка системы самовосстановления
echo "[9/10] Настройка системы самовосстановления..."
if [ -f "scripts/setup_system_auto_recovery.sh" ]; then
    if bash scripts/setup_system_auto_recovery.sh; then
        echo "   ✅ System auto-recovery настроен"
    else
        echo "   ❌ setup_system_auto_recovery.sh failed"
        SETUP_FAIL=1
    fi
else
    echo "   ❌ setup_system_auto_recovery.sh не найден"
    SETUP_FAIL=1
fi
echo ""

# 10. Настройка автономных систем
echo "[10/10] Настройка автономных систем..."
if [ -f "scripts/ensure_autonomous_systems.sh" ]; then
    echo "   📝 Запускаю ensure_autonomous_systems..."
    if bash scripts/ensure_autonomous_systems.sh; then
        echo "   ✅ Автономные системы обеспечены"
    else
        echo "   ❌ ensure_autonomous_systems failed"
        SETUP_FAIL=1
    fi
elif [ -f "scripts/start_autonomous_systems.sh" ]; then
    echo "   📝 Fallback: start_autonomous_systems.sh..."
    if bash scripts/start_autonomous_systems.sh; then
        echo "   ✅ Автономные системы запущены"
    else
        echo "   ❌ start_autonomous_systems failed"
        SETUP_FAIL=1
    fi
else
    echo "   ❌ Нет ensure/start_autonomous_systems.sh"
    SETUP_FAIL=1
fi
echo ""

# Финальная проверка
echo "=============================================="
if [ "$SETUP_FAIL" -eq 0 ]; then
    echo "✅ НАСТРОЙКА ЗАВЕРШЕНА"
else
    echo "⚠️ НАСТРОЙКА ЗАВЕРШЕНА С ОШИБКАМИ"
fi
echo "=============================================="
echo ""
echo "📊 Статус автозапуска:"
echo ""
echo "Docker Desktop StartAtLogin: $DOCKER_AUTOSTART"
echo ""

# Проверка Ollama
if command -v brew >/dev/null 2>&1 && brew services list 2>/dev/null | grep -q ollama; then
    OLLAMA_STATUS=$(brew services list | grep ollama | awk '{print $2}')
    if [ "$OLLAMA_STATUS" = "started" ]; then
        echo "✅ Ollama: запущен через brew services"
    else
        echo "⚠️  Ollama: не запущен (запустите: brew services start ollama)"
    fi
else
    echo "⚠️  Ollama: проверьте автозапуск вручную"
fi

# Проверка MLX API Server (запас)
if launchctl list 2>/dev/null | grep -q "com.atra.mlx-api-server"; then
    echo "✅ MLX API Server: настроен на автозапуск при входе"
else
    echo "⚠️  MLX API Server: не настроен (live brain = Ollama 11434)"
fi

# Проверка Victoria MCP
if launchctl list 2>/dev/null | grep -q "com.atra.victoria-mcp"; then
    echo "✅ Victoria MCP Server: настроен на автозапуск"
else
    echo "⚠️  Victoria MCP Server: не настроен"
fi

# Проверка Self-Check System
if launchctl list 2>/dev/null | grep -q "com.atra.self-check"; then
    echo "✅ Self-Check System: настроен на автозапуск"
else
    echo "⚠️  Self-Check System: не настроен"
    SETUP_FAIL=1
fi

# Проверка SSH Reverse Tunnel
if launchctl list 2>/dev/null | grep -q "com.atra.ssh-tunnel-headscale"; then
    echo "✅ SSH Reverse Tunnel: настроен на автозапуск"
else
    echo "⚠️  SSH Reverse Tunnel: не настроен"
fi

# Проверка Model Tracker
if launchctl list 2>/dev/null | grep -q "com.atra.model-tracker"; then
    echo "✅ Model Tracker: настроен на автозапуск"
else
    echo "⚠️  Model Tracker: не настроен"
    SETUP_FAIL=1
fi

echo ""
echo "🔄 После перезагрузки: bash scripts/verify_mac_studio_self_recovery.sh"
echo "📝 Live brain: curl -s http://localhost:11434/api/tags"
echo "📝 Victoria:   curl -s http://localhost:8010/health"
echo ""
exit "$SETUP_FAIL"

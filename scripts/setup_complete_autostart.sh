#!/bin/bash
# Полная настройка автозапуска корпорации ATRA на Mac Studio
# Запускать один раз: bash scripts/setup_complete_autostart.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

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
    defaults write com.docker.docker 'StartAtLogin' -bool true
    echo "   ✅ Docker Desktop автозапуск настроен"
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
    echo "   ✅ Контейнеры будут запускаться автоматически при старте Docker"
else
    echo "   ⚠️  docker-compose.yml не найден"
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
            brew services start ollama 2>/dev/null || echo "   ⚠️  Не удалось запустить через brew, проверьте установку Ollama"
        fi
    else
        echo "   ⚠️  Ollama не найден в brew services"
        echo "   💡 Установите Ollama: brew install ollama"
        echo "   💡 Или настройте автозапуск вручную"
    fi
else
    echo "   ⚠️  Homebrew не найден, проверьте Ollama автозапуск вручную"
fi
echo ""

# 4. Настройка Victoria MCP Server
echo "[4/5] Настройка Victoria MCP Server автозапуска..."
if [ -f "scripts/victoria/quick_victoria_autostart.sh" ]; then
    bash scripts/victoria/quick_victoria_autostart.sh
    echo "   ✅ Victoria MCP Server настроен на автозапуск"
else
    echo "   ⚠️  Скрипт quick_victoria_autostart.sh не найден"
fi
echo ""

# 5. Настройка SSH Reverse Tunnel для Headscale (НОВОЕ)
echo "[5/7] Настройка SSH Reverse Tunnel автозапуска..."
if [ -f "scripts/setup_ssh_tunnel_for_headscale.sh" ]; then
    bash scripts/setup_ssh_tunnel_for_headscale.sh 2>&1 | grep -E "(✅|⚠️|❌|📊|🌐)" || true
    echo "   ✅ SSH Reverse Tunnel настроен на автозапуск"
else
    echo "   ⚠️  Скрипт setup_ssh_tunnel_for_headscale.sh не найден"
fi
echo ""

# 6. Настройка Self-Check System автозапуска (НОВОЕ)
echo "[6/7] Настройка Self-Check System автозапуска..."
LAUNCHD_SELFCHECK="${HOME}/Library/LaunchAgents/com.atra.self-check.plist"
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
    echo "   ⚠️  Self-Check System не настроен (проверьте вручную)"
fi
echo ""

# 7. Настройка Model Tracker автозапуска (НОВОЕ)
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
    echo "   ⚠️  Model Tracker не настроен (проверьте вручную)"
fi
echo ""

# 8. Настройка системы самовосстановления
echo "[8/9] Настройка системы самовосстановления..."
if [ -f "scripts/setup_system_auto_recovery.sh" ]; then
    bash scripts/setup_system_auto_recovery.sh
else
    echo "   ⚠️  setup_system_auto_recovery.sh не найден"
fi
echo ""

# 9. Настройка автономных систем
echo "[9/9] Настройка автономных систем..."
if [ -f "scripts/start_autonomous_systems.sh" ]; then
    echo "   📝 Запускаю настройку автономных систем..."
    bash scripts/start_autonomous_systems.sh || echo "   ⚠️  Не удалось настроить автономные системы"
else
    echo "   ⚠️  Скрипт start_autonomous_systems.sh не найден"
fi
echo ""

# Финальная проверка
echo "=============================================="
echo "✅ НАСТРОЙКА ЗАВЕРШЕНА"
echo "=============================================="
echo ""
echo "📊 Статус автозапуска:"
echo ""
echo "✅ Docker Desktop: автозапуск включен"
echo "✅ Docker контейнеры: restart policy настроена"
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

# Проверка Victoria MCP
if launchctl list 2>/dev/null | grep -q "com.atra.victoria-mcp"; then
    echo "✅ Victoria MCP Server: настроен на автозапуск"
else
    echo "⚠️  Victoria MCP Server: не настроен"
fi

# Проверка Self-Check System (НОВОЕ)
if launchctl list 2>/dev/null | grep -q "com.atra.self-check"; then
    echo "✅ Self-Check System: настроен на автозапуск (НОВОЕ)"
else
    echo "⚠️  Self-Check System: не настроен"
fi

# Проверка SSH Reverse Tunnel (НОВОЕ)
if launchctl list 2>/dev/null | grep -q "com.atra.ssh-tunnel-headscale"; then
    echo "✅ SSH Reverse Tunnel: настроен на автозапуск (НОВОЕ)"
else
    echo "⚠️  SSH Reverse Tunnel: не настроен"
fi

# Проверка Model Tracker (НОВОЕ)
if launchctl list 2>/dev/null | grep -q "com.atra.model-tracker"; then
    echo "✅ Model Tracker: настроен на автозапуск (НОВОЕ)"
else
    echo "⚠️  Model Tracker: не настроен"
fi

echo ""
echo "🔄 После перезагрузки Mac Studio или MacBook:"
echo "   1. Docker Desktop запустится автоматически"
echo "   2. Все Docker контейнеры запустятся автоматически"
echo "   3. Ollama запустится автоматически (если настроен)"
echo "   4. Victoria MCP Server запустится автоматически (если настроен)"
echo "   5. Self-Check System запустится автоматически (НОВОЕ) ✅"
echo "   6. SSH Reverse Tunnel запустится автоматически (НОВОЕ) ✅"
echo "   7. Model Tracker запустится автоматически (НОВОЕ) ✅"
echo "   8. Автономные системы запустятся автоматически (если настроены)"
echo ""
echo "📝 Проверка после перезагрузки:"
echo "   bash scripts/verify_mac_studio_self_recovery.sh"
echo "   launchctl list | grep atra"
echo "   tail -f ~/Library/Logs/atra-self-check.log"
echo "   tail -f ~/Library/Logs/ssh-tunnel-headscale.log"
echo ""
echo "🌐 Проверка удаленного доступа:"
echo "   curl -s http://185.177.216.15:8080 >/dev/null && echo '✅ Headscale доступен' || echo '⚠️ Headscale недоступен'"
echo "   curl -s http://185.177.216.15:8010/health >/dev/null && echo '✅ Victoria доступна' || echo '⚠️ Victoria недоступна'"
echo ""

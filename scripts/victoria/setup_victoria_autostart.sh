#!/bin/bash
# Настройка автозапуска Victoria и MCP сервера при старте Mac.
# Запускать один раз: bash scripts/setup_victoria_autostart.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "🚀 Настройка автозапуска Victoria"
echo "=============================================="
echo ""

# 1. Настройка Docker restart policy для Victoria
echo "[1/3] Настройка Docker restart policy..."
if [ -f "$ROOT/knowledge_os/docker-compose.yml" ]; then
  # Проверяем, есть ли уже restart: always
  if grep -q "victoria-agent:" "$ROOT/knowledge_os/docker-compose.yml" && ! grep -A 5 "victoria-agent:" "$ROOT/knowledge_os/docker-compose.yml" | grep -q "restart: always"; then
    echo "      ⚠️  Нужно добавить 'restart: always' в docker-compose.yml для victoria-agent"
    echo "      Сделай вручную или запусти: docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent"
  else
    echo "      ✅ Docker restart policy настроен"
  fi
else
  echo "      ⚠️  docker-compose.yml не найден"
fi

# 2. Создание launchd service для MCP сервера
echo ""
echo "[2/3] Настройка автозапуска MCP сервера..."
LAUNCHD_PLIST="${HOME}/Library/LaunchAgents/com.atra.victoria-mcp.plist"

cat > "$LAUNCHD_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atra.victoria-mcp</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>-m</string>
        <string>src.agents.bridge.victoria_mcp_server</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${ROOT}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PYTHONPATH</key>
        <string>${ROOT}</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/victoria-mcp.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/victoria-mcp.err.log</string>
    <key>StartInterval</key>
    <integer>60</integer>
</dict>
</plist>
EOF

# Загрузка launchd service
launchctl unload "$LAUNCHD_PLIST" 2>/dev/null || true
launchctl load "$LAUNCHD_PLIST" 2>/dev/null || true
sleep 2

if launchctl list | grep -q "com.atra.victoria-mcp"; then
  echo "      ✅ MCP сервер настроен на автозапуск через launchd"
else
  echo "      ⚠️  Ошибка загрузки launchd service"
fi

# 3. Создание скрипта для проверки и запуска Victoria при старте
echo ""
echo "[3/3] Создание скрипта проверки Victoria..."
STARTUP_SCRIPT="${HOME}/Library/LaunchAgents/com.atra.victoria-check.sh"
cat > "$STARTUP_SCRIPT" << 'STARTUPEOF'
#!/bin/bash
# Автоматическая проверка и запуск Victoria при старте Mac

ATRA_ROOT="${HOME}/Documents/GITHUB/atra/atra"
[ -d "${HOME}/Documents/dev/atra" ] && ATRA_ROOT="${HOME}/Documents/dev/atra"

cd "$ATRA_ROOT" 2>/dev/null || exit 0

# Проверка Victoria
if ! curl -sf --connect-timeout 2 http://localhost:8010/health >/dev/null 2>&1; then
  # Запуск через Docker
  if command -v docker-compose >/dev/null 2>&1 && [ -f "$ATRA_ROOT/knowledge_os/docker-compose.yml" ]; then
    docker-compose -f "$ATRA_ROOT/knowledge_os/docker-compose.yml" up -d victoria-agent >/dev/null 2>&1
  fi
fi

# Проверка MCP сервера (запускается через launchd, но проверим)
if ! curl -sf --connect-timeout 2 http://localhost:8012/sse >/dev/null 2>&1; then
  # MCP должен запуститься через launchd, но на всякий случай
  export PYTHONPATH="$ATRA_ROOT:$PYTHONPATH"
  nohup python3 -m src.agents.bridge.victoria_mcp_server > /tmp/victoria_mcp.log 2>&1 &
fi
STARTUPEOF

chmod +x "$STARTUP_SCRIPT"

# Создание launchd для проверки Victoria
CHECK_PLIST="${HOME}/Library/LaunchAgents/com.atra.victoria-check.plist"
cat > "$CHECK_PLIST" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atra.victoria-check</string>
    <key>ProgramArguments</key>
    <array>
        <string>${STARTUP_SCRIPT}</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/victoria-check.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/victoria-check.err.log</string>
</dict>
</plist>
EOF

SETUP_FAIL=0
launchctl unload "$CHECK_PLIST" 2>/dev/null || true
if ! launchctl load "$CHECK_PLIST" 2>/dev/null; then
  echo "      ❌ Не удалось загрузить victoria-check launchd"
  SETUP_FAIL=1
else
  echo "      ✅ Скрипт проверки Victoria настроен"
fi

# 4. Запуск сейчас
echo ""
echo "[4/4] Запуск сервисов сейчас..."
bash "$STARTUP_SCRIPT" || true
sleep 3

if curl -sf --connect-timeout 2 http://localhost:8010/health >/dev/null 2>&1; then
  echo "      ✅ Victoria работает"
else
  echo "      ❌ Victoria не запустилась (проверь Docker)"
  SETUP_FAIL=1
fi

# MCP 8012 optional when CHECK_LEGACY_MCP!=true
if [ "${CHECK_LEGACY_MCP:-false}" = "true" ]; then
  if curl -sf --connect-timeout 2 http://localhost:8012/sse >/dev/null 2>&1; then
    echo "      ✅ MCP сервер работает"
  else
    echo "      ❌ MCP сервер не запустился"
    SETUP_FAIL=1
  fi
else
  echo "      ℹ️  MCP 8012 skip (CHECK_LEGACY_MCP!=true); live brain=11434 / agent=8010"
fi

echo ""
echo "=============================================="
if [ "$SETUP_FAIL" -eq 0 ]; then
  echo "✅ ГОТОВО! Victoria будет запускаться автоматически."
else
  echo "⚠️ НАСТРОЙКА ЗАВЕРШЕНА С ОШИБКАМИ"
fi
echo ""
echo "📝 Что настроено:"
echo "   1. MCP сервер — автозапуск через launchd (legacy optional)"
echo "   2. Victoria — проверка и запуск при старте Mac"
echo "   3. Периодическая проверка (каждые 5 минут)"
echo ""
echo "🔄 Перезагрузи Mac или перезапусти Cursor."
echo "=============================================="
exit "$SETUP_FAIL"

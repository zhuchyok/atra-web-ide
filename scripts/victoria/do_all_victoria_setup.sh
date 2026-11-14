#!/bin/bash
# Полная автоматическая настройка Victoria для всех проектов Cursor.
# Запускать один раз: bash scripts/victoria/do_all_victoria_setup.sh

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT"
SETUP_FAIL=0

echo "=============================================="
echo "🚀 Полная автоматическая настройка Victoria"
echo "=============================================="
echo ""

# 1. Настройка MCP в Cursor settings
echo "[1/4] Настройка MCP в Cursor..."
if [ -f "scripts/victoria/setup_cursor_mcp_global.py" ]; then
  if ! python3 scripts/victoria/setup_cursor_mcp_global.py; then
    echo "      ❌ setup_cursor_mcp_global.py failed"
    SETUP_FAIL=1
  fi
else
  echo "      ⚠️  setup_cursor_mcp_global.py не найден (не блокер)"
fi

# 2. Запуск Victoria через Docker (если не запущена) — CRITICAL
echo ""
echo "[2/4] Проверка Victoria (8010)..."
if curl -sf --connect-timeout 3 http://localhost:8010/health >/dev/null 2>&1; then
  echo "      ✅ Victoria работает"
else
  echo "      🚀 Запуск Victoria..."
  if command -v docker-compose >/dev/null 2>&1 || command -v docker >/dev/null 2>&1; then
    docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent >/tmp/victoria_up.out 2>&1 || true
    sleep 5
    if curl -sf --connect-timeout 3 http://localhost:8010/health >/dev/null 2>&1; then
      echo "      ✅ Victoria запущена"
    else
      echo "      ❌ Victoria не отвечает"
      SETUP_FAIL=1
    fi
  else
    echo "      ❌ docker-compose не найден"
    SETUP_FAIL=1
  fi
fi

# 3. MCP 8012 — optional unless CHECK_LEGACY_MCP=true
echo ""
echo "[3/4] Настройка MCP сервера (legacy 8012)..."
if [ "${CHECK_LEGACY_MCP:-false}" = "true" ]; then
  if ! python3 -c "import fastmcp" 2>/dev/null; then
    pip3 install --user fastmcp >/dev/null 2>&1 || pip3 install fastmcp >/dev/null 2>&1 || SETUP_FAIL=1
  fi
  if curl -sf --connect-timeout 2 http://localhost:8012/sse >/dev/null 2>&1; then
    echo "      ✅ MCP сервер работает"
  else
    export PYTHONPATH="$ROOT:$PYTHONPATH"
    nohup python3 -m src.agents.bridge.victoria_mcp_server > /tmp/victoria_mcp.log 2>&1 &
    sleep 3
    if curl -sf --connect-timeout 2 http://localhost:8012/sse >/dev/null 2>&1; then
      echo "      ✅ MCP сервер запущен"
    else
      echo "      ❌ MCP 8012 не поднялся"
      SETUP_FAIL=1
    fi
  fi
else
  echo "      ℹ️  MCP 8012 skip (CHECK_LEGACY_MCP!=true); live = 8010 + brain 11434"
fi

# 4. Настройка launchd для автозапуска
echo ""
echo "[4/4] Настройка автозапуска..."
LAUNCHD_PLIST="${HOME}/Library/LaunchAgents/com.atra.victoria-mcp.plist"
mkdir -p "${HOME}/Library/LaunchAgents"
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
    <true/>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/victoria-mcp.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/victoria-mcp.err.log</string>
</dict>
</plist>
EOF

launchctl unload "$LAUNCHD_PLIST" 2>/dev/null || true
if launchctl load "$LAUNCHD_PLIST" 2>/dev/null && launchctl list 2>/dev/null | grep -q "com.atra.victoria-mcp"; then
  echo "      ✅ Автозапуск подтверждён в launchctl"
else
  echo "      ❌ Автозапуск launchd не подтверждён"
  SETUP_FAIL=1
fi

echo ""
echo "=============================================="
if [ "$SETUP_FAIL" -eq 0 ]; then
  echo "✅ ГОТОВО! Victoria настроена."
else
  echo "⚠️ НАСТРОЙКА ЗАВЕРШЕНА С ОШИБКАМИ"
fi
echo "Live: curl -s http://localhost:8010/health && curl -s http://localhost:11434/api/tags"
echo "=============================================="
exit "$SETUP_FAIL"

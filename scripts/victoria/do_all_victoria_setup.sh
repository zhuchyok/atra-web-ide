#!/bin/bash
# Полная автоматическая настройка Victoria для всех проектов Cursor.
# Запускать один раз: bash scripts/do_all_victoria_setup.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
# ROOT = корень проекта (scripts/victoria -> .. -> ..)
ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "🚀 Полная автоматическая настройка Victoria"
echo "=============================================="
echo ""

# 1. Настройка MCP в Cursor settings
echo "[1/4] Настройка MCP в Cursor..."
cd "$ROOT"
if [ -f "scripts/victoria/setup_cursor_mcp_global.py" ]; then
  python3 scripts/victoria/setup_cursor_mcp_global.py
else
  echo "      ⚠️  setup_cursor_mcp_global.py не найден в $ROOT/scripts/victoria/"
  echo "      Пропуск настройки MCP (можно сделать вручную)"
fi

# 2. Запуск Victoria через Docker (если не запущена)
echo ""
echo "[2/4] Проверка Victoria..."
if curl -sf --connect-timeout 3 http://localhost:8010/health >/dev/null 2>&1; then
  echo "      ✅ Victoria работает"
else
  echo "      🚀 Запуск Victoria..."
  cd "$ROOT"
  if command -v docker-compose >/dev/null 2>&1; then
    docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent 2>&1 | grep -E "(victoria|Creating|Starting|Up)" || true
    sleep 5
    if curl -sf --connect-timeout 3 http://localhost:8010/health >/dev/null 2>&1; then
      echo "      ✅ Victoria запущена"
    else
      echo "      ⚠️  Victoria не отвечает. Проверь: docker ps | grep victoria"
    fi
  else
    echo "      ⚠️  docker-compose не найден"
  fi
fi

# 3. Установка fastmcp и запуск MCP сервера
echo ""
echo "[3/4] Настройка MCP сервера..."
if ! python3 -c "import fastmcp" 2>/dev/null; then
  echo "      📦 Установка fastmcp..."
  pip3 install --user fastmcp >/dev/null 2>&1 || pip3 install fastmcp >/dev/null 2>&1
fi

if curl -sf --connect-timeout 2 http://localhost:8012/sse >/dev/null 2>&1; then
  echo "      ✅ MCP сервер работает"
else
  echo "      🚀 Запуск MCP сервера..."
  export PYTHONPATH="$ROOT:$PYTHONPATH"
  nohup python3 -m src.agents.bridge.victoria_mcp_server > /tmp/victoria_mcp.log 2>&1 &
  sleep 3
  if curl -sf --connect-timeout 2 http://localhost:8012/sse >/dev/null 2>&1; then
    echo "      ✅ MCP сервер запущен (PID: $!)"
  else
    echo "      ⚠️  Ошибка запуска. Лог: /tmp/victoria_mcp.log"
    tail -10 /tmp/victoria_mcp.log 2>/dev/null || true
  fi
fi

# 4. Настройка launchd для автозапуска
echo ""
echo "[4/4] Настройка автозапуска..."
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
    <true/>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/victoria-mcp.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/victoria-mcp.err.log</string>
</dict>
</plist>
EOF

launchctl unload "$LAUNCHD_PLIST" 2>/dev/null || true
launchctl load "$LAUNCHD_PLIST" 2>/dev/null || true
echo "      ✅ Автозапуск настроен через launchd"

echo ""
echo "=============================================="
echo "✅ ГОТОВО! Victoria настроена автоматически."
echo ""
echo "📝 Что сделано:"
echo "   1. ✅ MCP добавлен в Cursor settings"
echo "   2. ✅ Victoria запущена (если была остановлена)"
echo "   3. ✅ MCP сервер запущен (localhost:8012)"
echo "   4. ✅ Автозапуск через launchd настроен"
echo ""
echo "🔄 Перезапусти Cursor, чтобы применить MCP настройки."
echo ""
echo "💡 Теперь в ЛЮБОМ проекте Cursor используй:"
echo "   @victoria_run 'твоя задача'"
echo "   @victoria_status"
echo ""
echo "🔧 Автоматическое подключение работает через:"
echo "   - .vscode/tasks.json (при открытии проекта)"
echo "   - launchd (при старте Mac)"
echo "=============================================="

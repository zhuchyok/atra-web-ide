#!/bin/bash
# Автоматическая глобальная настройка Victoria для ВСЕХ проектов Cursor.
# Запускать один раз: bash scripts/auto_setup_victoria_global.sh

set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

CURSOR_SETTINGS="${HOME}/Library/Application Support/Cursor/User/settings.json"
CURSOR_SETTINGS_DIR="${HOME}/Library/Application Support/Cursor/User"
MCP_CONFIG_KEY="mcp.servers"

echo "=============================================="
echo "🌐 Глобальная настройка Victoria для Cursor"
echo "=============================================="
echo ""

# 1. Проверка и запуск Victoria
echo "[1/5] Проверка Victoria..."
if curl -sf --connect-timeout 3 http://localhost:8010/health >/dev/null 2>&1; then
  echo "      ✅ Victoria работает"
else
  echo "      🚀 Запуск Victoria через Docker..."
  cd "$ROOT"
  if [ -f "knowledge_os/docker-compose.yml" ]; then
    docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent 2>&1 | head -5
  else
    echo "      ⚠️  docker-compose.yml не найден. Проверь путь."
    exit 1
  fi
  sleep 5
  if curl -sf --connect-timeout 3 http://localhost:8010/health >/dev/null 2>&1; then
    echo "      ✅ Victoria запущена"
  else
    echo "      ⚠️  Victoria не запустилась. Проверь Docker."
    exit 1
  fi
fi

# 2. Установка fastmcp
echo ""
echo "[2/5] Проверка зависимостей..."
if python3 -c "import fastmcp" 2>/dev/null; then
  echo "      ✅ fastmcp установлен"
else
  echo "      📦 Установка fastmcp..."
  pip3 install --user fastmcp >/dev/null 2>&1 || pip3 install fastmcp >/dev/null 2>&1
  echo "      ✅ fastmcp установлен"
fi

# 3. Создание launchd service для MCP сервера
echo ""
echo "[3/5] Настройка автозапуска MCP сервера..."
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

# Загрузка launchd service
launchctl unload "$LAUNCHD_PLIST" 2>/dev/null || true
launchctl load "$LAUNCHD_PLIST" 2>/dev/null || true
sleep 3

if curl -sf --connect-timeout 3 http://localhost:8012/sse >/dev/null 2>&1; then
  echo "      ✅ MCP сервер запущен через launchd"
else
  echo "      ⚠️  Запуск MCP сервера вручную..."
  export PYTHONPATH="$ROOT:$PYTHONPATH"
  nohup python3 -m src.agents.bridge.victoria_mcp_server > /tmp/victoria_mcp.log 2>&1 &
  sleep 3
  if curl -sf --connect-timeout 3 http://localhost:8012/sse >/dev/null 2>&1; then
    echo "      ✅ MCP сервер запущен"
  else
    echo "      ❌ Ошибка запуска MCP. Лог: /tmp/victoria_mcp.log"
    exit 1
  fi
fi

# 4. Настройка MCP в Cursor settings.json
echo ""
echo "[4/5] Настройка MCP в Cursor..."
mkdir -p "$CURSOR_SETTINGS_DIR"

if [ -f "$CURSOR_SETTINGS" ]; then
  # Проверяем, есть ли уже VictoriaATRA
  if grep -q "VictoriaATRA" "$CURSOR_SETTINGS" 2>/dev/null; then
    echo "      ✅ VictoriaATRA уже настроен в Cursor"
  else
    # Добавляем MCP сервер
    python3 << 'PYEOF'
import json
import os
import sys

settings_path = os.path.expanduser("~/Library/Application Support/Cursor/User/settings.json")

# Читаем существующие настройки
try:
    with open(settings_path, 'r', encoding='utf-8') as f:
        settings = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    settings = {}

# Добавляем MCP сервер
if "mcp.servers" not in settings:
    settings["mcp.servers"] = {}

settings["mcp.servers"]["VictoriaATRA"] = {
    "type": "sse",
    "url": "http://localhost:8012/sse"
}

# Сохраняем
with open(settings_path, 'w', encoding='utf-8') as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)

print(f"✅ MCP сервер добавлен в {settings_path}")
PYEOF
    echo "      ✅ VictoriaATRA добавлен в Cursor settings"
  fi
else
  # Создаём новый settings.json
  python3 << 'PYEOF'
import json
import os

settings_path = os.path.expanduser("~/Library/Application Support/Cursor/User/settings.json")

settings = {
    "mcp.servers": {
        "VictoriaATRA": {
            "type": "sse",
            "url": "http://localhost:8012/sse"
        }
    }
}

with open(settings_path, 'w', encoding='utf-8') as f:
    json.dump(settings, f, indent=2, ensure_ascii=False)

print(f"✅ Создан {settings_path} с настройкой VictoriaATRA")
PYEOF
  echo "      ✅ Cursor settings создан с VictoriaATRA"
fi

# 5. Создание глобального скрипта для новых проектов
echo ""
echo "[5/5] Создание глобального скрипта..."
GLOBAL_SCRIPT="${HOME}/.cursor/victoria_init.sh"
cat > "$GLOBAL_SCRIPT" << 'GLOBALEOF'
#!/bin/bash
# Автоматическая инициализация Victoria при открытии проекта.
# Этот скрипт вызывается автоматически через .vscode/tasks.json

ROOT="$(cd "$(dirname "$0")/../.." && pwd 2>/dev/null || pwd)"
ATRA_ROOT="${HOME}/Documents/GITHUB/atra/atra"

# Проверка, что мы в проекте ATRA или есть скрипт
if [ -f "${ROOT}/scripts/init_victoria_for_new_project.sh" ]; then
  bash "${ROOT}/scripts/init_victoria_for_new_project.sh" >/dev/null 2>&1
elif [ -f "${ATRA_ROOT}/scripts/init_victoria_for_new_project.sh" ]; then
  bash "${ATRA_ROOT}/scripts/init_victoria_for_new_project.sh" >/dev/null 2>&1
fi
GLOBALEOF
chmod +x "$GLOBAL_SCRIPT"
echo "      ✅ Глобальный скрипт создан: $GLOBAL_SCRIPT"

echo ""
echo "=============================================="
echo "✅ ГОТОВО! Victoria настроена глобально."
echo ""
echo "📝 Что сделано:"
echo "   1. ✅ Victoria запущена (localhost:8010)"
echo "   2. ✅ MCP сервер запущен (localhost:8012)"
echo "   3. ✅ Автозапуск через launchd настроен"
echo "   4. ✅ Cursor settings обновлён (VictoriaATRA)"
echo "   5. ✅ Глобальный скрипт создан"
echo ""
echo "🔄 Перезапусти Cursor, чтобы применить настройки MCP."
echo ""
echo "💡 Использование в любом проекте:"
echo "   @victoria_run 'твоя задача'"
echo "   @victoria_status"
echo "=============================================="

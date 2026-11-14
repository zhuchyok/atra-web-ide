#!/bin/bash
# Быстрая настройка автозапуска Victoria.
# Запускать: bash scripts/victoria/quick_victoria_autostart.sh

set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
SETUP_FAIL=0

# 1. Launchd для MCP сервера (legacy optional)
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
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/victoria-mcp.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/victoria-mcp.err.log</string>
</dict>
</plist>
EOF

launchctl unload "$LAUNCHD_PLIST" 2>/dev/null || true
if ! launchctl load "$LAUNCHD_PLIST" 2>/dev/null; then
  echo "❌ Не удалось загрузить launchd MCP"
  SETUP_FAIL=1
fi

if launchctl list 2>/dev/null | grep -q "com.atra.victoria-mcp"; then
  echo "✅ MCP сервер настроен на автозапуск"
else
  echo "❌ MCP launchd не подтверждён"
  SETUP_FAIL=1
fi

# Live Victoria agent is docker restart: always — verify if reachable
if curl -sf --connect-timeout 2 http://localhost:8010/health >/dev/null 2>&1; then
  echo "✅ Victoria (8010) отвечает"
else
  echo "⚠️ Victoria (8010) сейчас не отвечает (compose restart: always)"
fi

echo ""
echo "Перезагрузи Mac или выполни:"
echo "  launchctl start com.atra.victoria-mcp"
exit "$SETUP_FAIL"

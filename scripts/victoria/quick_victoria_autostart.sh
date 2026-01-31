#!/bin/bash
# Быстрая настройка автозапуска Victoria.
# Запускать: bash scripts/quick_victoria_autostart.sh

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

# 1. Launchd для MCP сервера
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
</dict>
</plist>
EOF

launchctl unload "$LAUNCHD_PLIST" 2>/dev/null || true
launchctl load "$LAUNCHD_PLIST" 2>/dev/null || true

echo "✅ MCP сервер настроен на автозапуск"
echo "✅ Victoria уже настроена (restart: always в docker-compose.yml)"
echo ""
echo "Перезагрузи Mac или выполни:"
echo "  launchctl start com.atra.victoria-mcp"

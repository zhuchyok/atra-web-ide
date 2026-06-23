#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$PLIST_DIR/com.atra.boot-incident-guard.plist"
AGENT_SCRIPT_DIR="$HOME/Library/Application Support/ATRA"
SCRIPT_PATH="$AGENT_SCRIPT_DIR/boot_incident_guard.py"
SOURCE_SCRIPT="$ROOT_DIR/scripts/boot_incident_guard.py"
PYTHON_BIN="/usr/bin/python3"
LOG_DIR="$AGENT_SCRIPT_DIR/logs"

mkdir -p "$PLIST_DIR" "$LOG_DIR" "$AGENT_SCRIPT_DIR"
cp "$SOURCE_SCRIPT" "$SCRIPT_PATH"
chmod +x "$SCRIPT_PATH"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.atra.boot-incident-guard</string>

  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_BIN</string>
    <string>$SCRIPT_PATH</string>
  </array>

  <key>WorkingDirectory</key>
  <string>$AGENT_SCRIPT_DIR</string>

  <key>RunAtLoad</key>
  <true/>

  <key>StartInterval</key>
  <integer>900</integer>

  <key>EnvironmentVariables</key>
  <dict>
    <key>ATRA_ROOT</key>
    <string>$ROOT_DIR</string>
  </dict>

  <key>StandardOutPath</key>
  <string>$LOG_DIR/boot_incident_guard.stdout.log</string>

  <key>StandardErrorPath</key>
  <string>$LOG_DIR/boot_incident_guard.stderr.log</string>
</dict>
</plist>
EOF

launchctl bootout "gui/$(id -u)" "$PLIST_PATH" >/dev/null 2>&1 || true
sleep 1
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
launchctl enable "gui/$(id -u)/com.atra.boot-incident-guard"
launchctl kickstart -k "gui/$(id -u)/com.atra.boot-incident-guard"

echo "Installed: $PLIST_PATH"
echo "Label: com.atra.boot-incident-guard"

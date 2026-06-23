#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PLIST_DIR="$HOME/Library/LaunchAgents"
PLIST_PATH="$PLIST_DIR/com.atra.python-crash-detector.plist"
RUNTIME_DIR="$HOME/Library/Application Support/Atra"
RUNTIME_SCRIPT="$RUNTIME_DIR/python_crash_detector.py"
SOURCE_SCRIPT="$ROOT_DIR/scripts/python_crash_detector.py"
PYTHON_BIN="/usr/bin/python3"
LOG_DIR="$HOME/Library/Logs"

mkdir -p "$PLIST_DIR" "$RUNTIME_DIR" "$LOG_DIR"
cp "$SOURCE_SCRIPT" "$RUNTIME_SCRIPT"
chmod +x "$RUNTIME_SCRIPT"

cat > "$PLIST_PATH" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.atra.python-crash-detector</string>

  <key>ProgramArguments</key>
  <array>
    <string>$PYTHON_BIN</string>
    <string>$RUNTIME_SCRIPT</string>
    <string>--once</string>
  </array>

  <key>RunAtLoad</key>
  <true/>

  <key>StartInterval</key>
  <integer>60</integer>

  <key>WorkingDirectory</key>
  <string>$RUNTIME_DIR</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>ATRA_CRASH_COALITION_PREFIX</key>
    <string>com.atra.mlx-</string>
  </dict>

  <key>StandardOutPath</key>
  <string>$LOG_DIR/atra-python-crash-detector.stdout.log</string>

  <key>StandardErrorPath</key>
  <string>$LOG_DIR/atra-python-crash-detector.stderr.log</string>
</dict>
</plist>
EOF

# Bootstrap state without historical notification storm.
"$PYTHON_BIN" "$RUNTIME_SCRIPT" --once >/dev/null 2>&1 || true

launchctl bootout "gui/$(id -u)" "$PLIST_PATH" >/dev/null 2>&1 || true
sleep 1
launchctl bootstrap "gui/$(id -u)" "$PLIST_PATH"
launchctl enable "gui/$(id -u)/com.atra.python-crash-detector"
launchctl kickstart -k "gui/$(id -u)/com.atra.python-crash-detector"

echo "Installed: $PLIST_PATH"
echo "Script: $RUNTIME_SCRIPT"

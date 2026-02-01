#!/bin/bash
# Настройка автозапуска демона синхронизации employees.json
# Запускается при загрузке Mac Studio и слушает изменения в БД

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
PLIST_NAME="com.atra.employees-sync-daemon"
PLIST_PATH="$HOME/Library/LaunchAgents/${PLIST_NAME}.plist"
PYTHON_VENV="$REPO_ROOT/backend/.venv/bin/python"
DAEMON_SCRIPT="$REPO_ROOT/knowledge_os/app/employees_sync_daemon.py"
LOG_DIR="$HOME/Library/Logs/atra"

# Создаём директорию для логов
mkdir -p "$LOG_DIR"

# Проверяем наличие скриптов
if [ ! -f "$DAEMON_SCRIPT" ]; then
    echo "❌ Не найден $DAEMON_SCRIPT"
    exit 1
fi

if [ ! -f "$PYTHON_VENV" ]; then
    echo "⚠️ Не найден $PYTHON_VENV, используем системный python3"
    PYTHON_VENV="$(which python3)"
fi

# Останавливаем существующий сервис
launchctl unload "$PLIST_PATH" 2>/dev/null

# Создаём plist
cat > "$PLIST_PATH" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>${PLIST_NAME}</string>
    
    <key>ProgramArguments</key>
    <array>
        <string>${PYTHON_VENV}</string>
        <string>${DAEMON_SCRIPT}</string>
    </array>
    
    <key>WorkingDirectory</key>
    <string>${REPO_ROOT}</string>
    
    <key>EnvironmentVariables</key>
    <dict>
        <key>DATABASE_URL</key>
        <string>postgresql://admin:secret@localhost:5432/knowledge_os</string>
        <key>SYNC_DEBOUNCE_SECONDS</key>
        <string>5</string>
        <key>PERIODIC_SYNC_MINUTES</key>
        <string>60</string>
    </dict>
    
    <key>RunAtLoad</key>
    <true/>
    
    <key>KeepAlive</key>
    <true/>
    
    <key>StandardOutPath</key>
    <string>${LOG_DIR}/employees-sync-daemon.log</string>
    
    <key>StandardErrorPath</key>
    <string>${LOG_DIR}/employees-sync-daemon.error.log</string>
    
    <key>ThrottleInterval</key>
    <integer>10</integer>
</dict>
</plist>
EOF

echo "✅ Создан $PLIST_PATH"

# Загружаем сервис
launchctl load "$PLIST_PATH"
echo "✅ Сервис загружен и запущен"

# Проверяем статус
sleep 2
if launchctl list | grep -q "$PLIST_NAME"; then
    echo "✅ Демон employees-sync-daemon работает"
    echo ""
    echo "Команды управления:"
    echo "  launchctl stop $PLIST_NAME    # Остановить"
    echo "  launchctl start $PLIST_NAME   # Запустить"
    echo "  launchctl unload $PLIST_PATH  # Отключить автозапуск"
    echo ""
    echo "Логи:"
    echo "  tail -f $LOG_DIR/employees-sync-daemon.log"
else
    echo "⚠️ Демон не запустился. Проверьте логи:"
    echo "  cat $LOG_DIR/employees-sync-daemon.error.log"
fi

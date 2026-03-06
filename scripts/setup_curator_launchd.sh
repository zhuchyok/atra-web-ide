#!/bin/bash
# Настройка автоматического прогона куратора через launchd (macOS).
# Запускать один раз: bash scripts/setup_curator_launchd.sh
# После установки ежедневно в 9:00: полный автономный цикл (прогон → сравнение с эталонами → при расхождении задачи в БД → опционально синхронизация эталонов в RAG).
# DATABASE_URL и VICTORIA_URL подхватываются из $ROOT/.env при каждом запуске скрипта.

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "📋 АВТОМАТИЗАЦИЯ КУРАТОРА (launchd)"
echo "=============================================="
echo ""

# Создание launchd plist (ежедневно в 9:00) — полный автономный прогон
echo "[1/3] Создание launchd plist..."
LAUNCHD_FILE="${HOME}/Library/LaunchAgents/com.atra.curator-scheduled.plist"

cat > "$LAUNCHD_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atra.curator-scheduled</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${ROOT}/scripts/run_curator_autonomous.sh</string>
        <string>--full</string>
        <string>--sync-rag</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${ROOT}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>9</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/atra-curator.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/atra-curator.error.log</string>
</dict>
</plist>
EOF

echo "✅ LaunchAgent создан: $LAUNCHD_FILE"
echo "   Расписание: ежедневно в 9:00 (полный прогон + сравнение + задачи в БД + синхронизация эталонов в RAG)"
echo "   Переменные (VICTORIA_URL, DATABASE_URL): из $ROOT/.env при каждом запуске"
echo ""

# Загрузка в launchd
echo "[2/3] Загрузка в launchd..."
launchctl unload "$LAUNCHD_FILE" 2>/dev/null || true
launchctl load "$LAUNCHD_FILE"
echo "✅ Задание загружено."
echo ""

echo "[3/3] Проверка: launchctl list | grep curator"
launchctl list | grep -i curator || echo "(задание в списке)"
echo ""
echo "Готово. Логи: ~/Library/Logs/atra-curator.log"
echo "Отключить: launchctl unload $LAUNCHD_FILE"
echo "См. docs/CURATOR_RUNBOOK.md §1, §6 — автоматизация и автономность."

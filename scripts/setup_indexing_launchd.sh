#!/usr/bin/env bash
# Периодическая индексация доков в RAG (COGNITIVE_CODE, при необходимости ai_research).
# Запустить один раз: bash scripts/setup_indexing_launchd.sh
# После установки: еженедельно (воскресенье 3:00) выполняется index_cognitive_code.py.
# DATABASE_URL подхватывается из $ROOT/.env при запуске (скрипт index_cognitive_code.py читает env).
# Для ai_research (index_external_docs.py) добавьте в plist второй вызов или отдельное задание (долго, нужна сеть).
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
LAUNCHD_FILE="${HOME}/Library/LaunchAgents/com.atra.rag-indexing.plist"
echo "Создание LaunchAgent для еженедельной индексации COGNITIVE_CODE в RAG..."
cat > "$LAUNCHD_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atra.rag-indexing</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${ROOT}/scripts/run_rag_indexing.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${ROOT}</string>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Weekday</key>
        <integer>0</integer>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/atra-rag-indexing.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/atra-rag-indexing.error.log</string>
</dict>
</plist>
EOF
launchctl unload "$LAUNCHD_FILE" 2>/dev/null || true
launchctl load "$LAUNCHD_FILE"
echo "Готово. Индексация COGNITIVE_CODE: воскресенье 3:00. Логи: ~/Library/Logs/atra-rag-indexing.log"
echo "Отключить: launchctl unload $LAUNCHD_FILE"
echo "Cron (Linux), еженедельно: 0 3 * * 0 cd $ROOT && (source .env 2>/dev/null; cd knowledge_os && .venv/bin/python scripts/index_cognitive_code.py) >> docs/curator_reports/rag-indexing.log 2>&1"

#!/bin/bash
# Watcher для Moondream Station - автоматическое восстановление Vision API
# Singularity 21.10

CHECK_INTERVAL=30
PORT=2020
SCRIPT_DIR="/Users/bikos/Documents/atra-web-ide/scripts"
LOG_FILE="/Users/bikos/Documents/atra-web-ide/logs/vision_watcher.log"

mkdir -p "$(dirname "$LOG_FILE")"

echo "[$(date)] 👁️ Vision Watcher запущен. Мониторинг порта $PORT..." >> "$LOG_FILE"

while true; do
    # Проверяем, слушает ли кто-то порт 2020
    if ! lsof -i :$PORT > /dev/null; then
        echo "[$(date)] ⚠️ Vision API (порт $PORT) не отвечает. Перезапуск..." >> "$LOG_FILE"

        # Убиваем старые процессы, если они зависли
        pkill -f "moondream-station"
        sleep 2

        # Запускаем через наш expect-скрипт
        cd "/Users/bikos/Documents/atra-web-ide"
        ./scripts/start_moondream_station.exp >> "$LOG_FILE" 2>&1 &

        echo "[$(date)] ✅ Команда перезапуска отправлена." >> "$LOG_FILE"
    fi
    sleep $CHECK_INTERVAL
done

#!/bin/bash

# ATRA Auto-Sync Watcher - Автоматическое подключение новых проектов к Библии
# Автор: Виктория (Team Lead Atra Core)

WATCH_DIR="/Users/bikos/Documents/dev"
SYNC_SCRIPT="/Users/bikos/Documents/atra-web-ide/scripts/sync_global_configs.sh"

echo "👀 Запуск мониторинга папки $WATCH_DIR для авто-синхронизации..."

# Проверяем наличие fswatch (лучший инструмент для macOS)
if ! command -v fswatch &> /dev/null; then
    echo "инструмент fswatch не найден. Устанавливаю через brew..."
    brew install fswatch
fi

# Мониторим создание новых директорий
fswatch -0 -r -l 2 "$WATCH_DIR" | while read -d "" event; do
    # Если событие - создание новой папки (или изменение в существующей)
    if [ -d "$event" ]; then
        # Проверяем, не является ли это скрытой папкой (.git, .idea и т.д.)
        if [[ "$event" != *"/."* ]]; then
            echo "🆕 Обнаружена активность в проекте: $event"
            # Запускаем скрипт синхронизации
            bash "$SYNC_SCRIPT"
        fi
    fi
done

#!/bin/bash
# Скрипт для обслуживания логов ATRA Core
# Очищает логи Docker и локальные файлы логов

echo "--- Начинаю обслуживание логов $(date) ---"

# 1. Очистка логов Docker через вспомогательный контейнер (для macOS)
echo "Очищаю логи Docker-контейнеров..."
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock -v /var/lib/docker:/var/lib/docker alpine sh -c 'truncate -s 0 /var/lib/docker/containers/*/*-json.log' 2>/dev/null

# 2. Очистка локальных логов в проекте
echo "Очищаю локальные файлы логов..."
find ./logs -name "*.log" -exec truncate -s 0 {} +

# 3. Перезапуск контейнеров для применения настроек ротации (если были изменения в docker-compose)
# echo "Перезапускаю контейнеры для применения настроек ротации..."
# docker-compose up -d
# docker-compose -f knowledge_os/docker-compose.yml up -d

echo "--- Обслуживание завершено ---"

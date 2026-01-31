#!/bin/bash
# Применение всех изменений - выполнить в Cursor на Mac Studio

cd ~/Documents/atra-web-ide

echo '🔄 Применение изменений...'

# Используем docker-compose для перезапуска
if [ -f knowledge_os/docker-compose.yml ]; then
    echo '   Перезапуск Victoria и Veronica...'
    cd knowledge_os
    docker-compose restart victoria-agent veronica-agent 2>&1
    cd ..
fi

if [ -f docker-compose.yml ]; then
    echo '   Перезапуск Backend и Frontend...'
    docker-compose restart backend frontend 2>&1
fi

sleep 5

echo ''
echo '✅ Изменения применены!'
echo ''
echo '📋 Проверка:'
curl -s http://localhost:8010/health && echo ''
curl -s http://localhost:8011/health && echo ''
curl -s http://localhost:8080/health && echo ''

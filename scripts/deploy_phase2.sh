#!/bin/bash
# Развёртывание Фазы 2: RAG-light и рекомендации Agent
set -e
cd "$(dirname "$0")/.."

echo "Развёртывание Фазы 2: RAG-light и рекомендации Agent"

# 1. Остановка (опционально, чтобы не конфликтовать с другими сервисами)
# docker-compose down

# 2. Обновление кода (если из git)
# git pull origin main

# 3. Сборка бэкенда
docker-compose build backend

# 4. Запуск
docker-compose up -d

# 5. Ожидание инициализации
echo "Ожидание 30 с..."
sleep 30

# 6. Проверка здоровья
echo "Проверка здоровья..."
curl -sf "http://localhost:8080/health" > /dev/null || { echo "Бэкенд не отвечает на /health"; exit 1; }
curl -sf "http://localhost:8080/api/chat/mode/health" > /dev/null || true

echo "Фаза 2 развёрнута. Запустите scripts/check_phase2.sh для проверки."

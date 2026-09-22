#!/bin/bash
# Скрипт запуска отслеживания моделей

cd "$(dirname "$0")/.." || exit 1

echo "🚀 Запуск отслеживания моделей..."

# Проверяем переменные окружения
export DATABASE_URL="${DATABASE_URL:-postgresql://admin:${POSTGRES_PASSWORD:-secret}@localhost:5432/knowledge_os}"
export OLLAMA_BASE_URL="${OLLAMA_BASE_URL:-http://localhost:11434}"
export MODEL_TRACKER_INTERVAL="${MODEL_TRACKER_INTERVAL:-3600}"

# Запускаем отслеживание
cd knowledge_os || exit 1
python3 -m app.model_tracker

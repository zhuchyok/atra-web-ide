#!/bin/bash
# Автоматическое обнаружение новых моделей Ollama и обновление знаний корпорации
# Запускается периодически (например, через cron каждые 5 минут)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🔍 Проверка новых моделей Ollama..."
echo "   Время: $(date)"

# Проверяем Docker
if ! docker ps > /dev/null 2>&1; then
    echo "⚠️ Docker не запущен, проверяем локально..."
    # Локальная проверка
    if command -v ollama > /dev/null 2>&1; then
        echo "✅ Ollama доступен локально"
    else
        echo "❌ Ollama недоступен"
        exit 1
    fi
fi

# Обновляем знания корпорации
echo "🔄 Обновление знаний корпорации..."
cd "$PROJECT_ROOT"

# Проверяем, запущен ли контейнер knowledge_os_api
if docker ps --format "{{.Names}}" | grep -q "knowledge_os_api"; then
    echo "📦 Обновление через Docker контейнер..."
    docker exec -e DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os \
        knowledge_os_api \
        python /app/update_corporation_knowledge.py 2>&1 | tee -a /tmp/corporation_knowledge_update.log
else
    echo "💻 Обновление локально..."
    python3 knowledge_os/app/update_corporation_knowledge.py 2>&1 | tee -a /tmp/corporation_knowledge_update.log
fi

exit_code=${PIPESTATUS[0]}

if [ $exit_code -eq 0 ]; then
    echo "✅ Знания корпорации обновлены успешно"
    echo "   Логи: /tmp/corporation_knowledge_update.log"
else
    echo "⚠️ Ошибка обновления знаний (код: $exit_code)"
    exit $exit_code
fi

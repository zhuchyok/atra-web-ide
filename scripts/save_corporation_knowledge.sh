#!/bin/bash
# Скрипт для сохранения всех знаний корпорации в базу знаний
# Запускается через victoria-agent где правильные volumes

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "💾 Сохранение всех знаний корпорации в базу знаний..."
echo "   Время: $(date)"

# Проверяем Docker
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker не запущен!"
    exit 1
fi

# Проверяем контейнер victoria-agent
if ! docker ps --format "{{.Names}}" | grep -q "victoria-agent"; then
    echo "❌ Контейнер victoria-agent не запущен!"
    echo "   Запустите: docker-compose -f knowledge_os/docker-compose.yml up -d"
    exit 1
fi

# Запускаем через victoria-agent (где правильные volumes)
echo "🚀 Запуск через victoria-agent..."
docker exec -e DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os \
    victoria-agent \
    python3 -c "
import asyncio
import sys
sys.path.insert(0, '/app/knowledge_os')

from app.corporation_complete_knowledge import CorporationCompleteKnowledge

async def run():
    extractor = CorporationCompleteKnowledge()
    result = await extractor.extract_all()
    print(f'✅ Извлечено: {result[\"total_extracted\"]} знаний')
    print(f'✅ Сохранено в БД: {result[\"saved_to_db\"]}')

asyncio.run(run())
" 2>&1

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo "✅ Знания корпорации сохранены успешно"
else
    echo "⚠️ Ошибка сохранения знаний (код: $exit_code)"
    exit $exit_code
fi

#!/bin/bash
# Миграция узлов знаний из дампа SQL
# Использует knowledge_os_dump.sql если он доступен

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 Миграция узлов знаний из дампа SQL"
echo "   Время: $(date)"
echo ""

# Ищем дамп
DUMP_PATHS=(
    "$HOME/migration/server2/knowledge_os_dump.sql"
    "$HOME/migration/knowledge_os_dump.sql"
    "$PROJECT_ROOT/migration/knowledge_os_dump.sql"
    "$PROJECT_ROOT/knowledge_os_dump.sql"
    "./knowledge_os_dump.sql"
)

DUMP_FILE=""
for path in "${DUMP_PATHS[@]}"; do
    if [ -f "$path" ]; then
        DUMP_FILE="$path"
        echo "✅ Найден дамп: $DUMP_FILE"
        echo "   Размер: $(du -h "$DUMP_FILE" | cut -f1)"
        break
    fi
done

if [ -z "$DUMP_FILE" ]; then
    echo "❌ Дамп не найден!"
    echo ""
    echo "Ищите в:"
    for path in "${DUMP_PATHS[@]}"; do
        echo "  - $path"
    done
    echo ""
    echo "Или скачайте с сервера 46:"
    echo "  bash scripts/download_from_server46.sh"
    exit 1
fi

# Проверяем размер (пустой дамп = 0B, нормальный ~100MB+)
DUMP_SIZE=$(stat -f%z "$DUMP_FILE" 2>/dev/null || stat -c%s "$DUMP_FILE" 2>/dev/null || echo 0)
if [ "$DUMP_SIZE" -lt 1000 ]; then
    echo "❌ Дамп пустой (${DUMP_SIZE}B): $DUMP_FILE"
    echo "   Скачайте заново: bash scripts/download_from_server46.sh"
    exit 1
fi

# Проверяем Docker
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker не запущен!"
    exit 1
fi

# Проверяем контейнер
if ! docker ps --format "{{.Names}}" | grep -q "knowledge_postgres"; then
    echo "❌ Контейнер knowledge_postgres не запущен!"
    echo "   Запустите: docker-compose -f knowledge_os/docker-compose.yml up -d"
    exit 1
fi

echo ""
echo "📥 Импорт дампа в базу знаний..."
echo "   Это может занять несколько минут..."

# Импортируем дамп
docker exec -i knowledge_postgres psql -U admin -d knowledge_os < "$DUMP_FILE" 2>&1 | tail -20

if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo ""
    echo "✅ Дамп импортирован успешно!"
    
    # Проверяем количество узлов
    echo ""
    echo "📊 Статистика после импорта:"
    docker exec knowledge_postgres psql -U admin -d knowledge_os -c "
        SELECT 
            COUNT(*) as total_nodes,
            COUNT(DISTINCT domain_id) as domains,
            COUNT(DISTINCT metadata->>'source') as sources
        FROM knowledge_nodes;
    " 2>&1 | grep -A 3 "total_nodes"
else
    echo ""
    echo "⚠️ Ошибка импорта дампа"
    exit 1
fi

echo ""
echo "✅ Миграция завершена!"

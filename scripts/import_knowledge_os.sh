#!/bin/bash
# ============================================================================
# Импорт Knowledge OS БД из миграции
# ============================================================================

set -e

DUMP_FILE=~/migration/server2/knowledge_os_dump.sql
PROJECT_DIR="/Users/zhuchyok/Documents/atra-web-ide"

echo "🗄️  Импорт Knowledge OS"
echo "======================"
echo ""

if [ ! -f "$DUMP_FILE" ]; then
    echo "❌ Файл дампа не найден: $DUMP_FILE"
    exit 1
fi

echo "📁 Дамп: $DUMP_FILE ($(du -h "$DUMP_FILE" | cut -f1))"
echo ""

# Проверяем Docker
if docker ps >/dev/null 2>&1; then
    echo "🐳 Docker запущен"

    # Проверяем есть ли контейнер БД
    if docker ps --format '{{.Names}}' | grep -q "knowledge_os_db\|postgres"; then
        CONTAINER=$(docker ps --format '{{.Names}}' | grep -E "knowledge_os_db|postgres" | head -1)
        echo "✅ Найден контейнер: $CONTAINER"

        echo ""
        echo "⏳ Импортирую дамп..."
        docker exec -i "$CONTAINER" psql -U admin -d knowledge_os < "$DUMP_FILE"

        echo ""
        echo "✅ Импорт завершён!"

        # Проверка
        echo ""
        echo "📊 Проверка данных:"
        docker exec -i "$CONTAINER" psql -U admin -d knowledge_os -c "
            SELECT 'experts' as table_name, COUNT(*) as count FROM experts
            UNION ALL
            SELECT 'knowledge_nodes', COUNT(*) FROM knowledge_nodes
            UNION ALL
            SELECT 'domains', COUNT(*) FROM domains;
        "
    else
        echo "⚠️  Контейнер PostgreSQL не найден"
        echo ""
        echo "Запустите:"
        echo "  cd $PROJECT_DIR"
        echo "  docker-compose -f knowledge_os/docker-compose.yml up -d db"
        echo ""
        echo "Затем повторите этот скрипт."
    fi
else
    echo "⚠️  Docker не запущен"
    echo ""

    # Проверяем локальный PostgreSQL
    if pg_isready -h localhost -p 5432 >/dev/null 2>&1; then
        echo "✅ Локальный PostgreSQL запущен"

        # Проверяем БД
        if psql -h localhost -p 5432 -lqt 2>/dev/null | cut -d \| -f 1 | grep -qw knowledge_os; then
            echo "✅ БД knowledge_os существует"
        else
            echo "⏳ Создаю БД knowledge_os..."
            createdb knowledge_os 2>/dev/null || true
        fi

        echo ""
        echo "⏳ Импортирую дамп..."
        psql -h localhost -p 5432 -d knowledge_os < "$DUMP_FILE"

        echo ""
        echo "✅ Импорт завершён!"
    else
        echo "❌ PostgreSQL не доступен"
        echo ""
        echo "Варианты:"
        echo ""
        echo "1) Запустить Docker Desktop, затем:"
        echo "   cd $PROJECT_DIR"
        echo "   docker-compose -f knowledge_os/docker-compose.yml up -d db"
        echo ""
        echo "2) Установить PostgreSQL:"
        echo "   brew install postgresql@16"
        echo "   brew services start postgresql@16"
        echo ""
        echo "3) Импортировать на Mac Studio (если доступен):"
        echo "   scp $DUMP_FILE zhuchyok@192.168.1.43:/tmp/"
        echo "   ssh zhuchyok@192.168.1.43 'psql -d knowledge_os < /tmp/knowledge_os_dump.sql'"
    fi
fi

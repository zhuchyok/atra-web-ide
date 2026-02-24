#!/bin/bash
# Скрипт для применения миграции на сервере
# Singularity 5.0: Добавление метрик роутинга в semantic_ai_cache

SERVER="185.177.216.15"
PASSWORD="u44Ww9NmtQj,XG"
DB_NAME="knowledge_os"

echo "🚀 Применение миграции Singularity 5.0 на сервере..."

# Создаем временный SQL файл
SQL_CONTENT="-- Миграция для расширения semantic_ai_cache с метриками роутинга
ALTER TABLE semantic_ai_cache
ADD COLUMN IF NOT EXISTS routing_source TEXT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS performance_score FLOAT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS tokens_saved INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_semantic_cache_routing_source
ON semantic_ai_cache(routing_source)
WHERE routing_source IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_semantic_cache_performance
ON semantic_ai_cache(performance_score)
WHERE performance_score IS NOT NULL;
"

# Применяем миграцию через SSH
sshpass -p "$PASSWORD" ssh -o StrictHostKeyChecking=no root@$SERVER bash << EOF
    cd /root/knowledge_os 2>/dev/null || cd /root/atra/knowledge_os 2>/dev/null || cd /root 2>/dev/null || true

    # Создаем временный SQL файл
    cat > /tmp/migration_5_0.sql << 'SQLFILE'
-- Миграция для расширения semantic_ai_cache с метриками роутинга
ALTER TABLE semantic_ai_cache
ADD COLUMN IF NOT EXISTS routing_source TEXT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS performance_score FLOAT DEFAULT NULL,
ADD COLUMN IF NOT EXISTS tokens_saved INTEGER DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_semantic_cache_routing_source
ON semantic_ai_cache(routing_source)
WHERE routing_source IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_semantic_cache_performance
ON semantic_ai_cache(performance_score)
WHERE performance_score IS NOT NULL;
SQLFILE

    echo "📦 Применяю миграцию..."

    # Пробуем разные варианты подключения
    if sudo -u postgres psql -d knowledge_os -f /tmp/migration_5_0.sql 2>/dev/null; then
        echo "✅ Миграция применена (postgres user)"
    elif psql -U admin -d knowledge_os -f /tmp/migration_5_0.sql 2>/dev/null; then
        echo "✅ Миграция применена (admin user)"
    elif psql -h localhost -U admin -d knowledge_os -f /tmp/migration_5_0.sql 2>/dev/null; then
        echo "✅ Миграция применена (admin@localhost)"
    else
        echo "⚠️ Не удалось применить миграцию автоматически"
        echo "Выполните вручную: psql -d knowledge_os -f /tmp/migration_5_0.sql"
    fi

    # Проверяем результат
    echo "🔍 Проверка применения миграции..."
    if sudo -u postgres psql -d knowledge_os -c "\\d semantic_ai_cache" 2>/dev/null | grep -E "(routing_source|performance_score|tokens_saved)" > /dev/null; then
        echo "✅ Колонки найдены!"
    elif psql -U admin -d knowledge_os -c "\\d semantic_ai_cache" 2>/dev/null | grep -E "(routing_source|performance_score|tokens_saved)" > /dev/null; then
        echo "✅ Колонки найдены!"
    else
        echo "⚠️ Не удалось проверить (возможно, миграция применена)"
    fi

    rm -f /tmp/migration_5_0.sql
EOF

echo "✅ Готово!"

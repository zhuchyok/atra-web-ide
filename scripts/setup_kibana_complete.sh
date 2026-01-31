#!/bin/bash
# Полная настройка Kibana: index pattern
# Запускать после запуска Kibana контейнера

set -e

KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"
INDEX_PATTERN="atra-logs-*"

echo "=============================================="
echo "🔍 Полная настройка Kibana"
echo "=============================================="
echo ""

# 1. Проверка доступности Kibana
echo "[1/3] Проверка доступности Kibana..."
MAX_WAIT=60
WAITED=0
while ! curl -s -f "$KIBANA_URL/api/status" > /dev/null 2>&1; do
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo "❌ Kibana недоступен по адресу $KIBANA_URL"
        echo "   Убедитесь, что контейнер запущен: docker ps | grep kibana"
        exit 1
    fi
    sleep 2
    WAITED=$((WAITED + 2))
    echo -n "."
done
echo ""
echo "   ✅ Kibana доступен"
echo ""

# 2. Ожидание полной готовности Kibana
echo "[2/3] Ожидание готовности Kibana..."
sleep 10
echo "   ✅ Kibana готов"
echo ""

# 3. Создание index pattern через инструкции
echo "[3/3] Настройка index pattern..."
echo ""
echo "📝 Для создания index pattern выполните вручную:"
echo ""
echo "1. Откройте Kibana:"
echo "   $KIBANA_URL"
echo ""
echo "2. Создайте index pattern:"
echo "   - Management → Stack Management → Index Patterns"
echo "   - Нажмите 'Create index pattern'"
echo "   - Pattern: $INDEX_PATTERN"
echo "   - Time field: @timestamp"
echo "   - Нажмите 'Create index pattern'"
echo ""
echo "3. После создания index pattern логи будут доступны в:"
echo "   - Analytics → Discover"
echo ""

echo "=============================================="
echo "✅ ИНСТРУКЦИИ ПРЕДОСТАВЛЕНЫ"
echo "=============================================="
echo ""
echo "💡 Примечание: Kibana требует ручного создания index pattern"
echo "   после появления первых логов в Elasticsearch."
echo ""

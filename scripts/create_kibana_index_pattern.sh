#!/bin/bash
# Скрипт для создания index pattern в Kibana
# Использование: bash scripts/create_kibana_index_pattern.sh

set -e

KIBANA_URL="${KIBANA_URL:-http://localhost:5601}"
INDEX_PATTERN="atra-logs-*"
PATTERN_ID="atra-logs-pattern"

echo "=============================================="
echo "🔍 Создание index pattern в Kibana"
echo "=============================================="
echo ""

# 1. Проверка доступности Kibana
echo "[1/4] Проверка доступности Kibana..."
if ! curl -s -f "$KIBANA_URL/api/status" > /dev/null 2>&1; then
    echo "❌ Kibana недоступен по адресу $KIBANA_URL"
    echo "   Убедитесь, что контейнер запущен: docker ps | grep kibana"
    exit 1
fi
echo "   ✅ Kibana доступен"
echo ""

# 2. Проверка существующего pattern
echo "[2/4] Проверка существующего index pattern..."
EXISTING=$(curl -s -X GET "$KIBANA_URL/api/saved_objects/_find?type=index-pattern&search_fields=title&search=atra-logs" 2>&1 | python3 -c "import json, sys; data = json.load(sys.stdin); items = data.get('saved_objects', []); print(items[0]['id'] if items else '')" 2>/dev/null || echo "")

if [ -n "$EXISTING" ]; then
    echo "   ✅ Index pattern уже существует (ID: $EXISTING)"
    echo "   📊 Откройте Kibana: $KIBANA_URL/app/discover"
else
    echo "   ⚠️  Index pattern не найден, создаю..."

    # 3. Создание тестового лога если индексов нет
    echo "[3/4] Проверка индексов в Elasticsearch..."
    INDICES=$(curl -s 'http://localhost:9200/_cat/indices?v' 2>&1 | grep -c atra-logs || echo "0")

    if [ "$INDICES" = "0" ]; then
        echo "   ⚠️  Индексов atra-logs не найдено, создаю тестовый лог..."
        curl -s -X POST 'http://localhost:9200/atra-logs-2026.01.25/_doc' \
            -H 'Content-Type: application/json' \
            -d "{\"@timestamp\":\"$(date -u +"%Y-%m-%dT%H:%M:%SZ")\",\"level\":\"INFO\",\"logger\":\"setup\",\"message\":\"Test log entry for index pattern creation\",\"agent\":\"setup\",\"container\":\"setup\"}" > /dev/null 2>&1
        sleep 2
        echo "   ✅ Тестовый лог создан"
    else
        echo "   ✅ Индексы найдены ($INDICES)"
    fi
    echo ""

    # 4. Создание index pattern
    echo "[4/4] Создание index pattern..."
    RESPONSE=$(curl -s -X POST "$KIBANA_URL/api/saved_objects/index-pattern/$PATTERN_ID" \
        -H 'Content-Type: application/json' \
        -H 'kbn-xsrf: true' \
        -d "{
            \"attributes\": {
                \"title\": \"$INDEX_PATTERN\",
                \"timeFieldName\": \"@timestamp\"
            }
        }" 2>&1)

    if echo "$RESPONSE" | grep -q '"id"'; then
        PATTERN_ID_ACTUAL=$(echo "$RESPONSE" | python3 -c "import json, sys; print(json.load(sys.stdin).get('id', ''))" 2>/dev/null || echo "$PATTERN_ID")
        echo "   ✅ Index pattern успешно создан (ID: $PATTERN_ID_ACTUAL)"
        echo ""
        echo "   📊 Откройте Kibana:"
        echo "   $KIBANA_URL/app/discover"
    else
        echo "   ⚠️  Ошибка создания index pattern"
        echo "   Ответ: $RESPONSE"
        echo ""
        echo "   📝 Создайте вручную через UI:"
        echo "   1. Откройте $KIBANA_URL"
        echo "   2. Management → Stack Management → Index Patterns"
        echo "   3. Create index pattern"
        echo "   4. Pattern: $INDEX_PATTERN"
        echo "   5. Time field: @timestamp"
    fi
fi
echo ""

echo "=============================================="
echo "✅ НАСТРОЙКА ЗАВЕРШЕНА"
echo "=============================================="
echo ""

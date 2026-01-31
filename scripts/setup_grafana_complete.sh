#!/bin/bash
# Полная настройка Grafana: datasource + дашборд
# Запускать после запуска Grafana контейнера

set -e

GRAFANA_URL="${GRAFANA_URL:-http://localhost:3001}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASS="${GRAFANA_PASS:-atra2025}"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DASHBOARD_FILE="$ROOT/knowledge_os/dashboard/grafana_dashboard.json"

echo "=============================================="
echo "📊 Полная настройка Grafana"
echo "=============================================="
echo ""

# 1. Проверка доступности Grafana
echo "[1/4] Проверка доступности Grafana..."
if ! curl -s -f -u "$GRAFANA_USER:$GRAFANA_PASS" "$GRAFANA_URL/api/health" > /dev/null 2>&1; then
    echo "❌ Grafana недоступен по адресу $GRAFANA_URL"
    echo "   Убедитесь, что контейнер запущен: docker ps | grep grafana"
    exit 1
fi
echo "   ✅ Grafana доступен"
echo ""

# 2. Проверка существующего datasource
echo "[2/4] Проверка Prometheus datasource..."
EXISTING_DS=$(curl -s -u "$GRAFANA_USER:$GRAFANA_PASS" "$GRAFANA_URL/api/datasources/name/Prometheus" 2>&1 | grep -o '"id":[0-9]*' | head -1 | cut -d: -f2 || echo "")

if [ -n "$EXISTING_DS" ]; then
    echo "   ✅ Prometheus datasource уже существует (ID: $EXISTING_DS)"
else
    echo "   ⚠️  Prometheus datasource не найден, создаю..."
    
    # Создание datasource через API
    DS_RESPONSE=$(curl -s -X POST \
        -u "$GRAFANA_USER:$GRAFANA_PASS" \
        -H "Content-Type: application/json" \
        -d '{
            "name": "Prometheus",
            "type": "prometheus",
            "access": "proxy",
            "url": "http://atra-prometheus:9090",
            "isDefault": true,
            "jsonData": {
                "timeInterval": "30s",
                "httpMethod": "POST"
            }
        }' \
        "$GRAFANA_URL/api/datasources" 2>&1)
    
    if echo "$DS_RESPONSE" | grep -q '"id"'; then
        echo "   ✅ Prometheus datasource создан"
    else
        echo "   ⚠️  Ошибка создания datasource: $DS_RESPONSE"
        echo "   Попробуйте создать вручную через UI"
    fi
fi
echo ""

# 3. Импорт дашборда
echo "[3/4] Импорт дашборда..."
if [ ! -f "$DASHBOARD_FILE" ]; then
    echo "   ⚠️  Файл дашборда не найден: $DASHBOARD_FILE"
else
    echo "   📄 Файл найден: $DASHBOARD_FILE"
    
    # Обновляем дашборд для использования Prometheus datasource
    DASHBOARD_JSON=$(cat "$DASHBOARD_FILE" | python3 -c "
import json, sys
data = json.load(sys.stdin)
# Убеждаемся, что все панели используют Prometheus
for panel in data.get('dashboard', {}).get('panels', []):
    for target in panel.get('targets', []):
        if 'datasource' not in target:
            target['datasource'] = {'type': 'prometheus', 'uid': 'Prometheus'}
        elif isinstance(target['datasource'], str):
            target['datasource'] = {'type': 'prometheus', 'uid': 'Prometheus'}
print(json.dumps(data))
" 2>/dev/null || cat "$DASHBOARD_FILE")
    
    # Импорт через API
    IMPORT_RESPONSE=$(curl -s -X POST \
        -u "$GRAFANA_USER:$GRAFANA_PASS" \
        -H "Content-Type: application/json" \
        -d "{
            \"dashboard\": $DASHBOARD_JSON,
            \"overwrite\": true,
            \"folderId\": null
        }" \
        "$GRAFANA_URL/api/dashboards/db" 2>&1)
    
    if echo "$IMPORT_RESPONSE" | grep -q '"uid"'; then
        DASHBOARD_UID=$(echo "$IMPORT_RESPONSE" | python3 -c "import json, sys; print(json.load(sys.stdin).get('uid', ''))" 2>/dev/null || echo "")
        echo "   ✅ Дашборд успешно импортирован"
        echo "   📊 Откройте: $GRAFANA_URL/d/$DASHBOARD_UID"
    else
        echo "   ⚠️  Ошибка импорта дашборда"
        echo "   Ответ: $IMPORT_RESPONSE"
        echo "   Импортируйте вручную через UI: Dashboards → Import"
    fi
fi
echo ""

# 4. Финальная проверка
echo "[4/4] Финальная проверка..."
DS_COUNT=$(curl -s -u "$GRAFANA_USER:$GRAFANA_PASS" "$GRAFANA_URL/api/datasources" 2>&1 | python3 -c "import json, sys; data = json.load(sys.stdin); print(len(data))" 2>/dev/null || echo "0")
DASHBOARD_COUNT=$(curl -s -u "$GRAFANA_USER:$GRAFANA_PASS" "$GRAFANA_URL/api/search?type=dash-db" 2>&1 | python3 -c "import json, sys; data = json.load(sys.stdin); print(len(data)) if isinstance(data, list) else 0)" 2>/dev/null || echo "0")

echo "   📊 Datasources: $DS_COUNT"
echo "   📈 Dashboards: $DASHBOARD_COUNT"
echo ""

echo "=============================================="
echo "✅ НАСТРОЙКА ЗАВЕРШЕНА"
echo "=============================================="
echo ""
echo "🔗 Откройте Grafana:"
echo "   $GRAFANA_URL"
echo ""
echo "🔑 Логин: $GRAFANA_USER"
echo "🔑 Пароль: $GRAFANA_PASS"
echo ""

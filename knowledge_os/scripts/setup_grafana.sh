#!/bin/bash
# Настройка Grafana для Singularity 8.0

echo "📊 Настройка Grafana для Singularity 8.0..."
echo "=========================================="
echo ""

# Проверка наличия Grafana
if ! command -v grafana-server &> /dev/null; then
    echo "⚠️ Grafana не установлен"
    echo ""
    echo "📝 Инструкции по установке:"
    echo ""
    echo "macOS:"
    echo "  brew install grafana"
    echo "  brew services start grafana"
    echo ""
    echo "Linux (Ubuntu/Debian):"
    echo "  sudo apt-get install -y software-properties-common"
    echo "  sudo add-apt-repository 'deb https://packages.grafana.com/oss/deb stable main'"
    echo "  wget -q -O - https://packages.grafana.com/gpg.key | sudo apt-key add -"
    echo "  sudo apt-get update"
    echo "  sudo apt-get install grafana"
    echo "  sudo systemctl start grafana-server"
    echo ""
    echo "После установки запустите этот скрипт снова."
    exit 1
fi

echo "✅ Grafana установлен"
echo ""

# Путь к dashboard
DASHBOARD_FILE="knowledge_os/dashboard/grafana_dashboard.json"
PROJECT_ROOT=$(cd "$(dirname "$0")/../.." && pwd)
DASHBOARD_PATH="$PROJECT_ROOT/$DASHBOARD_FILE"

if [ ! -f "$DASHBOARD_PATH" ]; then
    echo "❌ Dashboard файл не найден: $DASHBOARD_PATH"
    exit 1
fi

echo "📝 Dashboard файл найден: $DASHBOARD_PATH"
echo ""

# URL Grafana (по умолчанию localhost:3000)
GRAFANA_URL="${GRAFANA_URL:-http://localhost:3000}"
GRAFANA_USER="${GRAFANA_USER:-admin}"
GRAFANA_PASS="${GRAFANA_PASS:-admin}"

echo "🔧 Настройка Grafana..."
echo "  URL: $GRAFANA_URL"
echo "  User: $GRAFANA_USER"
echo ""

# Проверка доступности Grafana
if ! curl -s -f -u "$GRAFANA_USER:$GRAFANA_PASS" "$GRAFANA_URL/api/health" > /dev/null 2>&1; then
    echo "⚠️ Grafana недоступен по адресу $GRAFANA_URL"
    echo ""
    echo "📝 Убедитесь, что Grafana запущен:"
    echo "  - macOS: brew services start grafana"
    echo "  - Linux: sudo systemctl start grafana-server"
    echo ""
    echo "Или измените GRAFANA_URL:"
    echo "  export GRAFANA_URL=http://your-grafana-url:3000"
    exit 1
fi

echo "✅ Grafana доступен"
echo ""

# Импорт dashboard
echo "📊 Импорт dashboard..."
echo ""

# Создаем папку для дашбордов если нужно
DASHBOARD_NAME="Singularity 8.0 Metrics"

# Используем Grafana API для импорта
cat << EOF | curl -s -X POST \
  -u "$GRAFANA_USER:$GRAFANA_PASS" \
  -H "Content-Type: application/json" \
  -d @- \
  "$GRAFANA_URL/api/dashboards/db" > /tmp/grafana_import.json

{
  "dashboard": $(cat "$DASHBOARD_PATH"),
  "overwrite": true,
  "folderId": null
}
EOF

if [ $? -eq 0 ]; then
    echo "✅ Dashboard успешно импортирован!"
    echo ""
    echo "📊 Откройте в браузере:"
    echo "  $GRAFANA_URL"
    echo ""
    echo "🔑 Логин: $GRAFANA_USER"
    echo "🔑 Пароль: $GRAFANA_PASS"
else
    echo "⚠️ Ошибка импорта dashboard"
    echo "   Импортируйте вручную: $DASHBOARD_PATH"
fi

echo ""
echo "📝 Настройка Prometheus:"
echo "  - Prometheus должен быть настроен для сбора метрик"
echo "  - Метрики доступны на: http://localhost:9090/metrics (или другой адрес)"
echo "  - Настройте Prometheus datasource в Grafana"
echo ""

echo "✅ Настройка завершена!"

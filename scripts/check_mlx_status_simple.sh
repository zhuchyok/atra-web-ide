#!/bin/bash
# Упрощенный просмотр метрик MLX API Server
# Использование: bash scripts/check_mlx_status_simple.sh

echo "🍎 MLX API Server - Статус"
echo ""

# Получаем метрики
if curl -sf --connect-timeout 2 http://localhost:8080/api/chat/mlx/metrics >/dev/null 2>&1; then
    METRICS=$(curl -s http://localhost:8080/api/chat/mlx/metrics)
else
    METRICS=$(curl -s http://localhost:11435/health)
fi

# Парсим и выводим ключевые метрики
STATUS=$(echo "$METRICS" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('status', 'unknown'))" 2>/dev/null)
ACTIVE=$(echo "$METRICS" | python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"{d.get('active_requests', 0)}/{d.get('max_concurrent', 5)}\")" 2>/dev/null)
MEMORY=$(echo "$METRICS" | python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"{d.get('memory', {}).get('used_percent', 0):.1f}%\")" 2>/dev/null)
MODELS=$(echo "$METRICS" | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('models_cached', 0))" 2>/dev/null)

echo "📊 Статус:        $STATUS"
echo "🔄 Запросы:       $ACTIVE (активных/максимум)"
echo "💾 Память:       $MEMORY использовано"
echo "📦 Модели:       $MODELS в кэше"
echo ""

# Предупреждения
WARNINGS=$(echo "$METRICS" | python3 -c "import sys, json; d=json.load(sys.stdin); warnings=d.get('warnings', []); print('\\n'.join(warnings))" 2>/dev/null)
if [ -n "$WARNINGS" ]; then
    echo "⚠️  Предупреждения:"
    echo "$WARNINGS" | sed 's/^/   /'
    echo ""
fi

# Загруженные модели
echo "📋 Загруженные модели:"
echo "$METRICS" | python3 -c "
import sys, json
d = json.load(sys.stdin)
for model in d.get('cached_models', [])[:5]:
    name = model.get('name', 'unknown')
    requests = model.get('active_requests', 0)
    use_count = model.get('use_count', 0)
    print(f\"   • {name} (использований: {use_count}, активных запросов: {requests})\")
" 2>/dev/null

echo ""

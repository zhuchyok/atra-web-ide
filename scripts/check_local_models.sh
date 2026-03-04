#!/bin/bash
# ============================================================================
# Виктория: проверка доступности локальных моделей (Ollama + MLX)
# Использование: ./scripts/check_local_models.sh
# ============================================================================

echo "🔍 Проверка локальных моделей (Ollama / MLX)"
echo "============================================"
echo ""

OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
MLX_URL="${MLX_API_URL:-http://localhost:11435}"

# Ollama
echo "📦 Ollama ($OLLAMA_URL)"
if curl -sf --connect-timeout 3 "$OLLAMA_URL/api/tags" > /tmp/ollama_tags.json 2>/dev/null; then
    echo "   Статус: ✅ доступен"
    python3 -c "
import json
with open('/tmp/ollama_tags.json') as f:
    d = json.load(f)
models = d.get('models', [])
print(f'   Моделей: {len(models)}')
for m in models[:10]:
    print(f\"   - {m.get('name', '')}\")
key = ['glm-4.7-flash:q8_0', 'phi3.5:3.8b', 'qwen2.5-coder:32b']
for k in key:
    ok = any(k in (m.get('name') or '') for m in models)
    print(f\"   {\"✓\" if ok else \"✗\"} {k}\")
" 2>/dev/null || echo "   (ошибка парсинга)"
else
    echo "   Статус: ❌ недоступен (проверьте порт 11434)"
fi
echo ""

# MLX
echo "🍎 MLX API ($MLX_URL)"
if curl -sf --connect-timeout 3 "$MLX_URL/health" > /tmp/mlx_health.json 2>/dev/null; then
    echo "   Статус: ✅ доступен"
    python3 -c "
import json
with open('/tmp/mlx_health.json') as f:
    d = json.load(f)
print(f\"   Сервис: {d.get('status', 'unknown')} | всего моделей: {d.get('total_models', 0)} | в кэше: {d.get('models_cached', 0)}\")
for m in d.get('cached_models', [])[:8]:
    print(f\"   - {m.get('name', '')}\")
" 2>/dev/null || echo "   (ошибка парсинга)"
else
    echo "   Статус: ❌ недоступен (проверьте порт 11435)"
fi
echo ""
echo "Готово."

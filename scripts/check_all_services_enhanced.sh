#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "🔍 Проверка всех сервисов Mac Studio M4 Max"
echo "=========================================="
echo ""

if ! command -v docker >/dev/null 2>&1; then
  echo "❌ Docker не установлен"
  exit 1
fi

if ! docker info >/dev/null 2>&1; then
  echo "❌ Docker daemon не запущен"
  exit 1
fi

echo "📊 Статус Docker контейнеров:"
docker-compose ps
echo ""

echo "🏥 Health Checks:"
ERRORS=0

check_service() {
  local name=$1
  local url=$2
  if curl -s -f "$url" >/dev/null 2>&1; then
    echo "   ✅ $name: Онлайн"
    return 0
  else
    echo "   ❌ $name: Офлайн"
    ERRORS=$((ERRORS + 1))
    return 1
  fi
}

# MLX API Server или Ollama (порт 11434)
echo -n "   MLX API Server / Ollama (порт 11434): "
if curl -s -f "http://localhost:11434/" >/dev/null 2>&1; then
  # Проверяем, что это за сервер
  if curl -s "http://localhost:11434/api/tags" 2>/dev/null | grep -q "mlx\|MLX" || curl -s "http://localhost:11434/" 2>/dev/null | grep -q "MLX"; then
    echo "✅ Онлайн (MLX API Server)"
  else
    echo "✅ Онлайн (Ollama)"
  fi
else
  echo "❌ Офлайн"
  echo "      💡 Запусти: bash scripts/setup_mlx_instead_ollama.sh"
  # Не увеличиваем ERRORS, так как это не критично для Docker сервисов
fi

# Knowledge OS сервисы
check_service "Knowledge OS MCP" "http://localhost:8000/health" || check_service "Knowledge OS MCP" "http://localhost:8000/"
check_service "Knowledge OS REST" "http://localhost:8002/health" || check_service "Knowledge OS REST" "http://localhost:8002/"
check_service "Knowledge OS Vector Core" "http://localhost:8001/health" || check_service "Knowledge OS Vector Core" "http://localhost:8001/"

# Мониторинг
check_service "Prometheus" "http://localhost:9090/-/healthy"
check_service "Grafana" "http://localhost:3000/api/health"

# Агенты
check_service "Victoria Agent" "http://localhost:8010/health" || check_service "Victoria Agent" "http://localhost:8010/"
check_service "Veronica Agent" "http://localhost:8011/health" || check_service "Veronica Agent" "http://localhost:8011/"

echo ""
echo "🗄️  База данных:"
if docker-compose exec -T knowledge_postgres pg_isready -U admin -d knowledge_os >/dev/null 2>&1; then
  echo "   ✅ PostgreSQL: Онлайн"
  TABLE_COUNT=$(docker-compose exec -T knowledge_postgres psql -U admin -d knowledge_os -tAc "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" 2>/dev/null || echo "0")
  echo "   📊 Таблиц в БД: $TABLE_COUNT"
else
  echo "   ❌ PostgreSQL: Офлайн"
  ERRORS=$((ERRORS + 1))
fi

echo ""
echo "🤖 Агенты (статус контейнеров):"
AGENTS=("victoria_agent" "veronica_agent" "knowledge_nightly")
for agent in "${AGENTS[@]}"; do
  if docker-compose ps "$agent" 2>/dev/null | grep -q "Up"; then
    echo "   ✅ $agent: Запущен"
  else
    echo "   ❌ $agent: Не запущен"
    ERRORS=$((ERRORS + 1))
  fi
done

echo ""
echo "💻 Использование ресурсов:"
docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | head -n 10

echo ""
echo "💾 Использование диска:"
df -h / | tail -n 1 | awk '{print "   Использовано: " $3 " / " $2 " (" $5 ")"}'

echo ""
echo "=========================================="
if [[ $ERRORS -eq 0 ]]; then
  echo "✅ Все Docker сервисы работают нормально"
  if ! curl -s -f "http://localhost:11434/" >/dev/null 2>&1; then
    echo ""
    echo "💡 Подсказка: MLX API Server / Ollama не запущен"
    echo "   Запусти: bash scripts/setup_mlx_instead_ollama.sh"
  fi
  exit 0
else
  echo "❌ Обнаружено проблем с Docker сервисами: $ERRORS"
  exit 1
fi

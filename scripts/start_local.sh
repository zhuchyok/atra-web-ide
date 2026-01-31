#!/bin/bash
# =============================================================================
# Локальный запуск Victoria + Veronica (PLAN.md Этап 1)
# Требуется: Docker, Ollama/MLX на localhost:11434
# =============================================================================

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "🚀 Локальный запуск Victoria + Veronica"
echo "=============================================="
echo ""

# 1. Docker
echo "[1/4] Docker..."
if ! command -v docker &>/dev/null; then
    echo "   ❌ Docker не установлен. Установите Docker Desktop."
    exit 1
fi
if ! docker info &>/dev/null; then
    echo "   ❌ Docker daemon не запущен. Запустите Docker Desktop."
    exit 1
fi
echo "   ✅ Docker готов"
echo ""

# 2. Сеть
echo "[2/4] Сеть atra-network..."
docker network create atra-network 2>/dev/null || true
echo "   ✅ OK"
echo ""

# 3. Knowledge OS: БД + Victoria + Veronica
echo "[3/4] Запуск Knowledge OS (db, Victoria, Veronica)..."
docker-compose -f knowledge_os/docker-compose.yml up -d db
echo "   ⏳ Ожидание готовности БД..."
for i in $(seq 1 30); do
  docker-compose -f knowledge_os/docker-compose.yml exec -T db pg_isready -U admin -d knowledge_os 2>/dev/null && break
  sleep 1
done
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent veronica-agent
echo "   ✅ Контейнеры запущены"
echo ""

# 4. Ollama
echo "[4/4] Ollama/MLX..."
if curl -s -f "http://localhost:11434/api/tags" &>/dev/null; then
    echo "   ✅ Ollama/MLX доступен на :11434"
else
    echo "   ⚠️  Ollama/MLX не доступен на http://localhost:11434"
    echo "   💡 Запустите: ollama serve  или  bash scripts/start_mlx_api_server.sh"
fi
echo ""

echo "=============================================="
echo "✅ Готово"
echo "=============================================="
echo "   Victoria:  http://localhost:8010/health"
echo "   Veronica:  http://localhost:8011/health"
echo "   БД:        localhost:5432 (knowledge_os)"
echo ""
echo "   Проверка:  bash scripts/check_services.sh"
echo ""

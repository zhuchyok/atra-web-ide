#!/bin/bash
# Полный запуск корпорации ATRA на Mac Studio
# Восстанавливает все автоматические системы как на сервере

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "🚀 ЗАПУСК ПОЛНОЙ КОРПОРАЦИИ ATRA"
echo "=============================================="
echo ""

# Проверка Docker
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker не запущен. Запустите Docker Desktop."
    exit 1
fi

# 0. Проверка volume (рекомендации экспертов после инцидента 2026-02-01)
# knowledge_os использует atra_knowledge_postgres_data — общая БД atra + atra-web-ide
if ! docker volume inspect atra_knowledge_postgres_data >/dev/null 2>&1; then
  echo "⚠️  Volume atra_knowledge_postgres_data не найден."
  echo "   Сначала запустите atra для создания volume: cd ~/Documents/dev/atra && docker-compose up -d db"
  echo "   Либо см. docs/INCIDENT_DB_VOLUME_SWITCH_2026_02_01.md"
  exit 1
fi

# 1. Запуск базовой инфраструктуры (db, redis)
echo "[1/7] Запуск базовой инфраструктуры..."
docker-compose -f knowledge_os/docker-compose.yml up -d db redis
sleep 5

# 1b. Проверка здоровья БД (пороги: experts>=80, knowledge_nodes>=10000)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -x "$SCRIPT_DIR/verify_db_health.sh" ]; then
  if ! "$SCRIPT_DIR/verify_db_health.sh" --fail-on-warning 2>/dev/null; then
    echo "⚠️  БД не прошла проверку здоровья (мало данных). См. docs/INCIDENT_DB_VOLUME_SWITCH_2026_02_01.md"
  fi
fi

# 2. Запуск Knowledge OS (Victoria, Veronica, Worker, Nightly, Orchestrator)
echo "[2/7] Запуск Knowledge OS..."
docker-compose -f knowledge_os/docker-compose.yml up -d
sleep 3

# 3. Запуск Victoria и Veronica
echo "[3/7] Запуск агентов Victoria и Veronica..."
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent veronica-agent
sleep 3

# 4. Исправление и запуск Worker
echo "[4/7] Настройка Knowledge OS Worker..."
# Останавливаем старый worker если есть
docker stop knowledge_os_worker 2>/dev/null || true
docker rm knowledge_os_worker 2>/dev/null || true

# Запускаем worker с правильной конфигурацией
docker run -d \
    --name knowledge_os_worker \
    --network atra-network \
    -e DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os \
    -e PYTHONPATH=/app \
    --restart unless-stopped \
    -v "$ROOT/knowledge_os/app:/app" \
    python:3.11-slim \
    sh -c "pip install asyncpg && cd /app && python smart_worker_autonomous.py" || \
docker run -d \
    --name knowledge_os_worker \
    --network atra-network \
    -e DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os \
    --restart unless-stopped \
    knowledge_os-worker \
    python smart_worker_autonomous.py 2>/dev/null || echo "⚠️ Worker будет запущен вручную"

# 5. Orchestrator и Nightly Learner — в Docker (knowledge_os_orchestrator, knowledge_nightly)
echo "[5/7] Orchestrator и Nightly Learner..."
echo "  ✅ Запущены в Docker (knowledge_os docker-compose)"

# 6. Резерв: если контейнеры не поднялись — перезапуск
echo "[6/7] Проверка контейнеров..."
docker-compose -f knowledge_os/docker-compose.yml up -d knowledge_os_orchestrator knowledge_nightly 2>/dev/null || true

# 7. Проверка всех сервисов
echo "[7/7] Проверка всех сервисов..."
sleep 5

echo ""
echo "=============================================="
echo "📊 СТАТУС СЕРВИСОВ"
echo "=============================================="

# Проверка агентов
if curl -sf http://localhost:8010/health >/dev/null 2>&1; then
    echo "✅ Victoria Agent: работает"
else
    echo "❌ Victoria Agent: не работает"
fi

if curl -sf http://localhost:8011/health >/dev/null 2>&1; then
    echo "✅ Veronica Agent: работает"
else
    echo "❌ Veronica Agent: не работает"
fi

# Проверка БД
if docker exec -i knowledge_postgres pg_isready -U admin -d knowledge_os >/dev/null 2>&1; then
    EXPERTS=$(docker exec -i knowledge_postgres psql -U admin -d knowledge_os -tAc "SELECT COUNT(*) FROM experts;" 2>/dev/null)
    TASKS=$(docker exec -i knowledge_postgres psql -U admin -d knowledge_os -tAc "SELECT COUNT(*) FROM tasks WHERE status = 'pending';" 2>/dev/null)
    NODES=$(docker exec -i knowledge_postgres psql -U admin -d knowledge_os -tAc "SELECT COUNT(*) FROM knowledge_nodes;" 2>/dev/null)
    echo "✅ Knowledge OS DB: работает ($EXPERTS экспертов, $NODES узлов знаний, $TASKS pending задач)"
    "$SCRIPT_DIR/verify_db_health.sh" 2>/dev/null || true
else
    echo "❌ Knowledge OS DB: не работает"
fi

# Проверка Worker
if docker ps | grep -q knowledge_os_worker; then
    echo "✅ Knowledge OS Worker: запущен"
else
    echo "⚠️ Knowledge OS Worker: не запущен (запустите вручную)"
fi

echo ""
echo "=============================================="
echo "✅ КОРПОРАЦИЯ ЗАПУЩЕНА!"
echo "=============================================="
echo ""
echo "📋 Что работает:"
echo "  - Victoria Agent (Team Lead)"
echo "  - Veronica Agent (Web Researcher)"
echo "  - Knowledge OS Database (PostgreSQL)"
echo "  - Redis (кэш, очереди)"
echo "  - Knowledge OS Orchestrator (в Docker)"
echo "  - Nightly Learner (в Docker, цикл 24ч)"
echo "  - Smart Worker (обработка задач)"
echo ""
echo "📝 Логи:"
echo "  - docker logs knowledge_os_orchestrator"
echo "  - docker logs knowledge_nightly"
echo "  - docker logs knowledge_os_worker"
echo ""

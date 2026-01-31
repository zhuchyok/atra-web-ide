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

# 1. Запуск базовой инфраструктуры
echo "[1/7] Запуск базовой инфраструктуры..."
docker-compose -f knowledge_os/docker-compose.yml up -d db
sleep 5

# 2. Запуск Knowledge OS API
echo "[2/7] Запуск Knowledge OS API..."
docker-compose -f knowledge_os/docker-compose.yml up -d || true
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
    -e DATABASE_URL=postgresql://admin:secret@atra-knowledge-os-db:5432/knowledge_os \
    -e PYTHONPATH=/app \
    --restart unless-stopped \
    -v "$ROOT/knowledge_os/app:/app" \
    python:3.11-slim \
    sh -c "pip install asyncpg && cd /app && python smart_worker_autonomous.py" || \
docker run -d \
    --name knowledge_os_worker \
    --network atra-network \
    -e DATABASE_URL=postgresql://admin:secret@atra-knowledge-os-db:5432/knowledge_os \
    --restart unless-stopped \
    knowledge_os-worker \
    python smart_worker_autonomous.py 2>/dev/null || echo "⚠️ Worker будет запущен вручную"

# 5. Запуск Enhanced Orchestrator (в фоне, каждые 5 минут)
echo "[5/7] Настройка Enhanced Orchestrator..."
cat > /tmp/start_orchestrator.sh << 'ORCH_EOF'
#!/bin/bash
while true; do
    docker exec knowledge_os_api python /app/enhanced_orchestrator.py 2>&1 | head -50
    sleep 300  # 5 минут
done
ORCH_EOF
chmod +x /tmp/start_orchestrator.sh
nohup /tmp/start_orchestrator.sh > /tmp/orchestrator.log 2>&1 &
echo "  ✅ Orchestrator запущен в фоне (логи: /tmp/orchestrator.log)"

# 6. Запуск Nightly Learner (ежедневно в 3:00 UTC)
echo "[6/7] Настройка Nightly Learner..."
cat > /tmp/start_nightly_learner.sh << 'NIGHTLY_EOF'
#!/bin/bash
while true; do
    # Проверяем, наступило ли время обучения (3:00 UTC = 6:00 MSK)
    HOUR=$(date +%H)
    if [ "$HOUR" = "06" ] || [ "$1" = "force" ]; then
        docker exec knowledge_os_api python /app/nightly_learner.py 2>&1
        sleep 3600  # Ждем час после обучения
    else
        sleep 600  # Проверяем каждые 10 минут
    fi
done
NIGHTLY_EOF
chmod +x /tmp/start_nightly_learner.sh
nohup /tmp/start_nightly_learner.sh > /tmp/nightly_learner.log 2>&1 &
echo "  ✅ Nightly Learner запущен в фоне (логи: /tmp/nightly_learner.log)"
echo "  💡 Для немедленного обучения: /tmp/start_nightly_learner.sh force"

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
if docker exec -i atra-knowledge-os-db pg_isready -U admin -d knowledge_os >/dev/null 2>&1; then
    EXPERTS=$(docker exec -i atra-knowledge-os-db psql -U admin -d knowledge_os -tAc "SELECT COUNT(*) FROM experts;" 2>/dev/null)
    TASKS=$(docker exec -i atra-knowledge-os-db psql -U admin -d knowledge_os -tAc "SELECT COUNT(*) FROM tasks WHERE status = 'pending';" 2>/dev/null)
    echo "✅ Knowledge OS DB: работает ($EXPERTS экспертов, $TASKS pending задач)"
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
echo "  - Knowledge OS Database"
echo "  - Enhanced Orchestrator (каждые 5 минут)"
echo "  - Nightly Learner (ежедневно в 6:00 MSK)"
echo "  - Smart Worker (обработка задач)"
echo ""
echo "📝 Логи:"
echo "  - Orchestrator: /tmp/orchestrator.log"
echo "  - Nightly Learner: /tmp/nightly_learner.log"
echo "  - Worker: docker logs knowledge_os_worker"
echo ""
echo "🔄 Для немедленного запуска обучения:"
echo "  /tmp/start_nightly_learner.sh force"
echo ""

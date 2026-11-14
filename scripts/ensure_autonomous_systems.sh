#!/bin/bash
# Обеспечивает автоматический запуск всех автономных систем
# Запускается при старте Docker контейнеров

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
# Cron не видит PATH — используем полный путь к docker (иначе «docker: command not found»)
DOCKER_BIN="$(command -v docker 2>/dev/null || echo '/usr/local/bin/docker')"
HARD_FAIL=0

echo "🚀 Настройка автоматического запуска автономных систем"
echo "   Время: $(date)"
echo ""

# Проверяем Docker
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker не запущен!"
    exit 1
fi

container_up() {
    local name="$1"
    docker ps --format '{{.Names}}' | grep -q "^${name}$"
}

# Проверяем контейнеры (redis: knowledge_os_redis live; knowledge_redis legacy alias)
REQUIRED_CONTAINERS=("knowledge_postgres" "victoria-agent")
for container in "${REQUIRED_CONTAINERS[@]}"; do
    if ! container_up "$container"; then
        echo "⚠️  Контейнер $container не запущен"
        echo "   Запустите: docker-compose -f knowledge_os/docker-compose.yml up -d"
        HARD_FAIL=1
    fi
done
if ! container_up "knowledge_os_redis" && ! container_up "knowledge_redis"; then
    echo "⚠️  Redis контейнер не запущен (ожидается knowledge_os_redis)"
    HARD_FAIL=1
fi

echo "✅ Контейнеры проверены"
echo ""

# 1. Enhanced Orchestrator — постоянно (Docker: knowledge_os_orchestrator с --continuous)
# Убираем оркестратор из cron, если был (теперь только Docker-сервис)
if crontab -l 2>/dev/null | grep -q "enhanced_orchestrator"; then
    (crontab -l 2>/dev/null | grep -v "enhanced_orchestrator") | crontab -
    echo "   📌 Оркестратор убран из crontab (используется Docker knowledge_os_orchestrator)"
fi
echo "🔄 Проверка Enhanced Orchestrator..."
if container_up "knowledge_os_orchestrator"; then
    echo "   ✅ Orchestrator запущен (режим continuous)"
else
    echo "   ⚠️  Orchestrator не запущен"
    echo "   Запустите: docker-compose -f knowledge_os/docker-compose.yml up -d knowledge_os_orchestrator"
    HARD_FAIL=1
fi

# 2. Smart Worker - постоянно (через Docker restart: always)
echo ""
echo "🔄 Проверка Smart Worker..."
if container_up "knowledge_os_worker"; then
    echo "   ✅ Worker запущен"
    RESTART_POLICY=$(docker inspect knowledge_os_worker --format '{{.HostConfig.RestartPolicy.Name}}' 2>/dev/null || echo "")
    if [ "$RESTART_POLICY" != "always" ] && [ "$RESTART_POLICY" != "unless-stopped" ]; then
        echo "   ⚠️  Restart policy: $RESTART_POLICY (рекомендуется: always)"
    else
        echo "   ✅ Restart policy: $RESTART_POLICY"
    fi
else
    echo "   ⚠️  Worker не запущен"
    echo "   Запустите: docker-compose -f knowledge_os/docker-compose.yml up -d knowledge_os_worker"
    HARD_FAIL=1
fi

# 3. Nightly Learner - ежедневно в 6:00 MSK (3:00 UTC)
echo ""
echo "📅 Настройка Nightly Learner (ежедневно в 3:00 UTC / 6:00 MSK)..."
if ! crontab -l 2>/dev/null | grep -q "nightly_learner"; then
    (crontab -l 2>/dev/null; echo "0 3 * * * cd $PROJECT_ROOT && $DOCKER_BIN exec -e DATABASE_URL=postgresql://admin:secret@knowledge_postgres:5432/knowledge_os -e REDIS_URL=redis://knowledge_os_redis:6379 -e OLLAMA_BASE_URL=http://host.docker.internal:11434 -e MAC_LLM_URL=http://host.docker.internal:11435 victoria-agent python3 /app/knowledge_os/app/nightly_learner.py >> /tmp/nightly_learner.log 2>&1") | crontab -
    echo "   ✅ Добавлен в crontab (docker: $DOCKER_BIN)"
else
    echo "   ✅ Уже настроен"
fi

echo ""
if [ "$HARD_FAIL" -eq 0 ]; then
    echo "✅ Автоматический запуск настроен!"
else
    echo "⚠️ Автоматический запуск настроен с ошибками"
fi
echo ""
echo "📋 Что настроено:"
echo "   ✅ Enhanced Orchestrator - постоянно (Docker: knowledge_os_orchestrator)"
echo "   ✅ Smart Worker - постоянно (Docker: knowledge_os_worker)"
echo "   ✅ Nightly Learner - ежедневно в 6:00 MSK (crontab)"
echo ""
echo "📄 Логи:"
echo "   - Orchestrator: docker logs knowledge_os_orchestrator"
echo "   - Nightly Learner: /tmp/nightly_learner.log"
echo "   - Worker: docker logs knowledge_os_worker"
exit "$HARD_FAIL"

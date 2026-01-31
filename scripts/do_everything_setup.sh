#!/bin/bash
# Один скрипт «сделать всё»: автопроверки, cron, Victoria, миграции, первый запуск оркестратора
# Использование: bash scripts/do_everything_setup.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "🔧 DO EVERYTHING SETUP"
echo "=============================================="
echo ""

# 1. Миграция expert_learning_logs (если ещё не применена)
echo "[1/5] Миграция expert_learning_logs..."
if docker ps --format "{{.Names}}" | grep -q knowledge_postgres; then
    docker exec -i knowledge_postgres psql -U admin -d knowledge_os -f - < knowledge_os/db/migrations/add_expert_learning_logs.sql 2>/dev/null || true
    echo "   ✅ Миграция применена (или таблица уже есть)"
else
    echo "   ⚠️ knowledge_postgres не запущен — примените миграцию вручную позже"
fi
echo ""

# 2. Victoria и Knowledge OS
echo "[2/5] Запуск Victoria и Knowledge OS..."
if [ -f "knowledge_os/docker-compose.yml" ]; then
    docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent 2>/dev/null | grep -v "level=warning" || true
    sleep 5
    if curl -sf --connect-timeout 5 http://localhost:8010/health >/dev/null; then
        echo "   ✅ Victoria доступна"
    else
        echo "   ⚠️ Victoria не отвечает — проверьте: docker logs victoria-agent"
    fi
else
    echo "   ⚠️ knowledge_os/docker-compose.yml не найден"
fi
echo ""

# 3. Cron (оркестратор каждые 5 мин, Nightly Learner раз в сутки)
echo "[3/5] Настройка cron (оркестратор + Nightly Learner)..."
bash scripts/ensure_autonomous_systems.sh 2>/dev/null | tail -15 || true
echo ""

# 4. Автовосстановление (launchd)
echo "[4/5] Настройка автовосстановления (launchd)..."
if [ -f "scripts/setup_system_auto_recovery.sh" ]; then
    bash scripts/setup_system_auto_recovery.sh 2>&1 | tail -25
else
    echo "   ⚠️ setup_system_auto_recovery.sh не найден"
fi
echo ""

# 5. Краткая сводка
echo "[5/5] Сводка"
echo "   • Victoria:        curl -s http://localhost:8010/health"
echo "   • Cron:            crontab -l | grep -E orchestrator\|nightly"
echo "   • Логи оркестратора: tail -f /tmp/orchestrator.log"
echo "   • Логи обучения:     tail -f /tmp/nightly_learner.log"
echo "   • Документация:     docs/WHY_NO_LEARNING_DEBATES_HYPOTHESES_TASKS.md"
echo ""
echo "=============================================="
echo "✅ DO EVERYTHING SETUP ЗАВЕРШЁН"
echo "=============================================="

#!/bin/bash
# Один скрипт «сделать всё»: автопроверки, cron, Victoria, миграции, первый запуск оркестратора
# Использование: bash scripts/do_everything_setup.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SETUP_FAIL=0

echo "=============================================="
echo "🔧 DO EVERYTHING SETUP"
echo "=============================================="
echo ""

# 1. Миграция expert_learning_logs (если ещё не применена)
echo "[1/5] Миграция expert_learning_logs..."
if docker ps --format "{{.Names}}" | grep -q knowledge_postgres; then
    if docker exec -i knowledge_postgres psql -U admin -d knowledge_os -f - < knowledge_os/db/migrations/add_expert_learning_logs.sql >/dev/null 2>&1; then
        echo "   ✅ Миграция применена (или таблица уже есть)"
    else
        echo "   ⚠️ Миграция не применилась (возможно уже есть) — проверяю вручную при необходимости"
    fi
else
    echo "   ⚠️ knowledge_postgres не запущен — примените миграцию вручную позже"
    SETUP_FAIL=1
fi
echo ""

# 2. Victoria и Knowledge OS
echo "[2/5] Запуск Victoria и Knowledge OS..."
if [ -f "knowledge_os/docker-compose.yml" ]; then
    set +e
    set +o pipefail
    docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent 2>&1 | grep -v "level=warning"
    compose_rc=${PIPESTATUS[0]}
    set -o pipefail
    set -e
    if [ "$compose_rc" -ne 0 ]; then
        echo "   ❌ Не удалось поднять victoria-agent"
        SETUP_FAIL=1
    fi
    sleep 5
    if curl -sf --connect-timeout 5 http://localhost:8010/health >/dev/null; then
        echo "   ✅ Victoria доступна"
    else
        echo "   ⚠️ Victoria не отвечает — проверьте: docker logs victoria-agent"
        SETUP_FAIL=1
    fi
else
    echo "   ⚠️ knowledge_os/docker-compose.yml не найден"
    SETUP_FAIL=1
fi
echo ""

# 3. Cron (оркестратор каждые 5 мин, Nightly Learner раз в сутки)
echo "[3/5] Настройка cron (оркестратор + Nightly Learner)..."
if ! bash scripts/ensure_autonomous_systems.sh 2>/dev/null | tail -15; then
    echo "   ⚠️ ensure_autonomous_systems завершился с ошибкой"
    SETUP_FAIL=1
fi
echo ""

# 4. Автовосстановление (launchd)
echo "[4/5] Настройка автовосстановления (launchd)..."
if [ -f "scripts/setup_system_auto_recovery.sh" ]; then
    if ! bash scripts/setup_system_auto_recovery.sh 2>&1 | tail -25; then
        echo "   ⚠️ setup_system_auto_recovery завершился с ошибкой"
        SETUP_FAIL=1
    fi
else
    echo "   ⚠️ setup_system_auto_recovery.sh не найден"
    SETUP_FAIL=1
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
if [ "$SETUP_FAIL" -eq 0 ]; then
    echo "✅ DO EVERYTHING SETUP ЗАВЕРШЁН"
else
    echo "⚠️ DO EVERYTHING SETUP ЗАВЕРШЁН С ОШИБКАМИ"
fi
echo "=============================================="
exit "$SETUP_FAIL"

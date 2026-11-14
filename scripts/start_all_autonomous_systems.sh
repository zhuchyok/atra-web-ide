#!/bin/bash
# Запуск всех автономных систем корпорации ATRA
set -euo pipefail

echo "🚀 ЗАПУСК ВСЕХ АВТОНОМНЫХ СИСТЕМ"
echo "================================================"
echo ""

# Переходим в корень проекта
cd "$(dirname "$0")/.." || exit 1
HARD_FAIL=0

# Проверка Docker
if ! docker ps > /dev/null 2>&1; then
    echo "❌ Docker не запущен!"
    exit 1
fi

# Проверка БД (live container name)
if ! docker exec knowledge_postgres psql -U admin -d knowledge_os -c "SELECT 1;" > /dev/null 2>&1; then
    echo "❌ База данных недоступна (knowledge_postgres)!"
    exit 1
fi

spawn_checked() {
    local name="$1"
    local pattern="$2"
    shift 2
    echo -n "Запуск $name... "
    if pgrep -f "$pattern" >/dev/null 2>&1; then
        echo "✅ Уже запущен"
        return 0
    fi
    nohup "$@" >/tmp/"${name// /_}.log" 2>&1 &
    local pid=$!
    sleep 2
    if kill -0 "$pid" 2>/dev/null || pgrep -f "$pattern" >/dev/null 2>&1; then
        echo "✅ Запущен (PID: $pid)"
        return 0
    fi
    echo "❌ Ошибка запуска"
    HARD_FAIL=1
    return 1
}

# Prefer Docker continuous services when present (Singularity live path).
if docker ps --format '{{.Names}}' | grep -q '^knowledge_os_orchestrator$'; then
    echo "1️⃣ Enhanced Orchestrator... ✅ Docker knowledge_os_orchestrator"
else
    echo "1️⃣ Enhanced Orchestrator..."
    (
      cd knowledge_os/app || exit 1
      spawn_checked "enhanced_orchestrator" "enhanced_orchestrator" python3 -c "
import asyncio, sys
sys.path.insert(0, '.')
from enhanced_orchestrator import run_enhanced_orchestration_cycle
async def main():
    while True:
        try:
            await run_enhanced_orchestration_cycle()
            await asyncio.sleep(300)
        except Exception as e:
            print(f'Error: {e}')
            await asyncio.sleep(60)
asyncio.run(main())
"
    ) || HARD_FAIL=1
fi

echo ""
echo "2️⃣ Curiosity Engine..."
spawn_checked "curiosity_engine" "curiosity_engine" python3 -c "
import asyncio, sys
sys.path.insert(0, 'knowledge_os/app')
from curiosity_engine import CuriosityEngine
async def main():
    engine = CuriosityEngine()
    while True:
        try:
            await engine.scan_for_gaps()
            await asyncio.sleep(21600)
        except Exception as e:
            print(f'Error: {e}')
            await asyncio.sleep(3600)
asyncio.run(main())
" || true
# curiosity is best-effort; do not hard-fail entire stack

echo ""
if docker ps --format '{{.Names}}' | grep -q '^knowledge_os_worker$'; then
    echo "3️⃣ Smart Worker... ✅ Docker knowledge_os_worker"
else
    echo "3️⃣ Smart Worker..."
    spawn_checked "smart_worker" "smart_worker_autonomous" python3 knowledge_os/app/smart_worker_autonomous.py || HARD_FAIL=1
fi

echo ""
echo "4️⃣ Nightly Learner..."
if docker ps --format '{{.Names}}' | grep -q '^knowledge_nightly$'; then
    echo "   ✅ Docker knowledge_nightly"
elif crontab -l 2>/dev/null | grep -q "nightly_learner"; then
    echo "   ✅ Уже в crontab"
else
    echo "   ⚠️ Nightly Learner не найден (Docker/crontab) — запустите ensure_autonomous_systems.sh"
    HARD_FAIL=1
fi

echo ""
if [ "$HARD_FAIL" -eq 0 ]; then
    echo "✅ ВСЕ СИСТЕМЫ ЗАПУЩЕНЫ"
else
    echo "⚠️ СИСТЕМЫ ЗАПУЩЕНЫ С ОШИБКАМИ"
fi
echo ""
echo "📝 Логи:"
echo "  - Enhanced Orchestrator: docker logs knowledge_os_orchestrator  OR /tmp/enhanced_orchestrator.log"
echo "  - Curiosity Engine: /tmp/curiosity_engine.log"
echo "  - Smart Worker: docker logs knowledge_os_worker OR /tmp/smart_worker.log"
echo "  - Nightly Learner: /tmp/nightly_learner.log"
echo ""
echo "🔍 Проверка: bash scripts/check_all_autonomous_systems.sh"
exit "$HARD_FAIL"

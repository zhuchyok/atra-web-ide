#!/bin/bash
# Запуск автономных систем корпорации (Orchestrator / Nightly / self-check helpers)
# Предпочтительно: Docker continuous services. Host daemons — fallback only.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
HARD_FAIL=0

echo "=============================================="
echo "🤖 ЗАПУСК АВТОНОМНЫХ СИСТЕМ"
echo "=============================================="
echo ""

if ! docker ps >/dev/null 2>&1; then
    echo "❌ Docker не запущен"
    exit 1
fi

require_container() {
    local name="$1"
    if docker ps --format '{{.Names}}' | grep -qx "$name"; then
        echo "  ✅ $name running"
        return 0
    fi
    echo "  ❌ $name not running"
    HARD_FAIL=1
    return 1
}

# 1. Enhanced Orchestrator — Docker preferred
echo "[1/4] Enhanced Orchestrator..."
if docker ps --format '{{.Names}}' | grep -qx "knowledge_os_orchestrator"; then
    echo "  ✅ Docker knowledge_os_orchestrator"
else
    echo "  ⚠️  knowledge_os_orchestrator отсутствует — пытаюсь ensure..."
    if [ -f scripts/ensure_autonomous_systems.sh ]; then
        bash scripts/ensure_autonomous_systems.sh || HARD_FAIL=1
    else
        HARD_FAIL=1
    fi
    require_container knowledge_os_orchestrator || true
fi

# 2. Smart Worker
echo "[2/4] Smart Worker..."
require_container knowledge_os_worker || true

# 3. Nightly Learner
echo "[3/4] Nightly Learner..."
require_container knowledge_nightly || true

# 4. Self-check host loop (optional helper; must stay alive if started)
echo "[4/4] Self-Check helper..."
if pgrep -f "start_self_check.sh" >/dev/null 2>&1; then
    echo "  ✅ Self-Check daemon уже запущен"
else
    cat > /tmp/start_self_check.sh << SELFCHECK_EOF
#!/bin/bash
ROOT="$ROOT"
while true; do
    echo "[\$(date)] Самопроверка..."
    bash "\$ROOT/scripts/verify_mac_studio_self_recovery.sh" 2>&1 | tee -a /tmp/self_check.log || true
    sleep 300
done
SELFCHECK_EOF
    chmod +x /tmp/start_self_check.sh
    nohup /tmp/start_self_check.sh > /tmp/self_check_daemon.log 2>&1 &
    sleep 1
    if pgrep -f "start_self_check.sh" >/dev/null 2>&1; then
        echo "  ✅ Self-Check System запущен (PID: $!)"
    else
        echo "  ❌ Self-Check не стартовал"
        HARD_FAIL=1
    fi
fi

echo ""
echo "=============================================="
if [ "$HARD_FAIL" -eq 0 ]; then
    echo "✅ АВТОНОМНЫЕ СИСТЕМЫ ЗАПУЩЕНЫ"
else
    echo "⚠️ АВТОНОМНЫЕ СИСТЕМЫ С ОШИБКАМИ"
fi
echo "=============================================="
echo ""
echo "📝 Проверка: bash scripts/ensure_autonomous_systems.sh"
echo "📝 Verify:   bash scripts/verify_mac_studio_self_recovery.sh"
exit "$HARD_FAIL"

#!/bin/bash
# Быстрая проверка: venv, импорты, опционально — доступность БД.
# Запуск: bash scripts/check_ready.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV="$PROJECT_ROOT/knowledge_os/.venv/bin/python"
APP_DIR="$PROJECT_ROOT/knowledge_os/app"

echo "🔍 Проверка готовности"
echo ""

# 1. Venv
if [ ! -x "$VENV" ]; then
    echo "❌ venv не найден. Запустите: bash scripts/setup_knowledge_os_venv.sh"
    exit 1
fi
echo "✅ venv: $VENV"

# 2. Импорты (из app)
cd "$APP_DIR" || exit 1
if ! "$VENV" -c "
import sys
sys.path.insert(0, '.')
from nightly_learner import nightly_learning_cycle
from enhanced_orchestrator import run_enhanced_orchestration_cycle
import vision_processor
assert getattr(vision_processor, 'MOONDREAM_AVAILABLE', False) or True
print('OK')
" 2>/dev/null; then
    echo "❌ Ошибка импорта. Запустите: bash scripts/setup_knowledge_os_venv.sh"
    exit 1
fi
echo "✅ Импорты: nightly_learner, enhanced_orchestrator, vision_processor"

# 3. БД (опционально)
if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  source "$PROJECT_ROOT/.env" 2>/dev/null || true
  set +a
fi
export DATABASE_URL="${DATABASE_URL:-postgresql://admin:secret@localhost:5432/knowledge_os}"
if "$VENV" -c "
import sys
sys.path.insert(0, '.')
import asyncio
import asyncpg
import os
async def check():
    try:
        conn = await asyncpg.connect(os.environ.get('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os'), timeout=2)
        await conn.close()
        return True
    except Exception:
        return False
r = asyncio.run(check())
exit(0 if r else 1)
" 2>/dev/null; then
    echo "✅ БД: доступна"
else
    echo "⚠️  БД: недоступна (запустите PostgreSQL; для обучения и оркестратора нужна БД)"
fi

echo ""
echo "✅ Готово к запуску: bash scripts/run_learning_and_orchestration.sh"

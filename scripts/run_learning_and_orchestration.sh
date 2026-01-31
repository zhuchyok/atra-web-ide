#!/bin/bash
# Запуск обучения и оркестрации на Mac Studio (локально, без Docker)
# Использует единую локальную БД (DATABASE_URL из .env или localhost)
# Требуется: Python с asyncpg (venv: cd knowledge_os && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt)

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
APP_DIR="$PROJECT_ROOT/knowledge_os/app"

# Python: venv в knowledge_os или в корне, иначе python3
if [ -x "$PROJECT_ROOT/knowledge_os/.venv/bin/python" ]; then
  PYTHON="$PROJECT_ROOT/knowledge_os/.venv/bin/python"
elif [ -x "$PROJECT_ROOT/.venv/bin/python" ]; then
  PYTHON="$PROJECT_ROOT/.venv/bin/python"
else
  PYTHON="python3"
  if ! "$PYTHON" -c "import asyncpg" 2>/dev/null; then
    echo "⚠️  asyncpg не найден. Запускаю setup (venv + зависимости)..."
    bash "$SCRIPT_DIR/setup_knowledge_os_venv.sh" || exit 1
    PYTHON="$PROJECT_ROOT/knowledge_os/.venv/bin/python"
  fi
fi

# Загружаем .env из корня проекта (если есть)
if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  source "$PROJECT_ROOT/.env" 2>/dev/null || true
  set +a
fi
# Единая локальная БД (если не задана в .env)
export DATABASE_URL="${DATABASE_URL:-postgresql://admin:secret@localhost:5432/knowledge_os}"

echo "🚀 Обучение и оркестрация (локальная БД)"
echo "   DATABASE_URL: ${DATABASE_URL%%@*}@***"
echo ""

# 1. Один цикл Nightly Learner (обучение, дебаты, гипотезы)
echo "1️⃣ Nightly Learner (один цикл)..."
cd "$APP_DIR" || exit 1
if "$PYTHON" -c "
import asyncio
import sys
sys.path.insert(0, '.')
from nightly_learner import nightly_learning_cycle
asyncio.run(nightly_learning_cycle())
" 2>&1; then
    echo "   ✅ Nightly Learner завершён"
else
    echo "   ⚠️ Nightly Learner завершился с ошибкой (проверьте БД и Ollama)"
fi

# 2. Один цикл Enhanced Orchestrator (задачи, гипотезы)
echo ""
echo "2️⃣ Enhanced Orchestrator (один цикл)..."
if "$PYTHON" -c "
import asyncio
import sys
sys.path.insert(0, '.')
from enhanced_orchestrator import run_enhanced_orchestration_cycle
asyncio.run(run_enhanced_orchestration_cycle())
" 2>&1; then
    echo "   ✅ Enhanced Orchestrator завершён"
else
    echo "   ⚠️ Enhanced Orchestrator завершился с ошибкой"
fi

echo ""
echo "✅ Готово. Данные в локальной БД; дашборд обновит вкладки «Академия ИИ», «Задачи», «База знаний»."
echo ""
echo "💡 Если Nightly Learner падает с ModuleNotFoundError (asyncpg/redis):"
echo "   cd knowledge_os && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
echo "   Затем снова: bash scripts/run_learning_and_orchestration.sh"

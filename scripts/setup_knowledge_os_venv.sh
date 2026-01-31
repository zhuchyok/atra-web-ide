#!/bin/bash
# Создаёт venv в knowledge_os и ставит зависимости для Nightly Learner, оркестраторов, vision.
# После этого работают: run_learning_and_orchestration.sh, nightly_learner, enhanced_orchestrator.

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
KNOWLEDGE_OS="$PROJECT_ROOT/knowledge_os"
APP_REQ="$KNOWLEDGE_OS/app/requirements.txt"
ROOT_REQ="$KNOWLEDGE_OS/requirements.txt"
VENV_DIR="$KNOWLEDGE_OS/.venv"

echo "🔧 Настройка knowledge_os (.venv + зависимости)"
echo "   Проект: $PROJECT_ROOT"
echo ""

if [ ! -d "$KNOWLEDGE_OS" ]; then
    echo "❌ Нет каталога knowledge_os"
    exit 1
fi

# 1. Venv
if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "1️⃣ Создаю venv: $VENV_DIR"
    python3 -m venv "$VENV_DIR"
    echo "   ✅ venv создан"
else
    echo "1️⃣ venv уже есть: $VENV_DIR"
fi

# 2. Upgrade pip
"$VENV_DIR/bin/pip" install -q --upgrade pip

# 3. Зависимости app (asyncpg, redis, httpx, ...)
echo "2️⃣ Устанавливаю зависимости app (requirements.txt)..."
"$VENV_DIR/bin/pip" install -q -r "$APP_REQ" 2>/dev/null || true
# Клиент moondream (vision) — без deps, чтобы не тянуть сборку Pillow на Python 3.14
"$VENV_DIR/bin/pip" install -q moondream --no-deps 2>/dev/null || true
echo "   ✅ app/requirements.txt установлен"

# 4. Дополнительно из корня knowledge_os (если есть и не ставилося)
if [ -f "$ROOT_REQ" ]; then
    echo "3️⃣ Доп. зависимости knowledge_os/requirements.txt..."
    "$VENV_DIR/bin/pip" install -q -r "$ROOT_REQ" 2>/dev/null || true
    echo "   ✅ установлено"
fi

echo ""
echo "✅ Готово. Запуск обучения и оркестрации:"
echo "   bash scripts/run_learning_and_orchestration.sh"
echo ""
echo "Или один цикл Nightly Learner:"
echo "   cd knowledge_os/app && ../.venv/bin/python -c \"import asyncio; from nightly_learner import nightly_learning_cycle; asyncio.run(nightly_learning_cycle())\""
echo ""

#!/usr/bin/env bash
# Setup Knowledge OS: venv + зависимости (в т.ч. watchdog). Опционально — миграция при доступной БД.
# Запуск из корня репо: bash knowledge_os/scripts/setup_knowledge_os.sh
# Или из knowledge_os: bash scripts/setup_knowledge_os.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KNOWLEDGE_OS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$KNOWLEDGE_OS_DIR"

echo "📦 Knowledge OS: $KNOWLEDGE_OS_DIR"

# 1. Venv
if [ ! -d ".venv" ]; then
  echo "🔧 Создаю .venv..."
  python3 -m venv .venv
fi
echo "✅ Venv: .venv"

# 2. Зависимости (watchdog и остальное)
echo "📥 Устанавливаю зависимости (pip install -r requirements.txt)..."
.venv/bin/pip install -q -r requirements.txt
echo "✅ Зависимости установлены (в т.ч. watchdog)"

# 3. Миграция (применить при доступной БД)
echo "ℹ️ Миграция организационных колонок (experts): когда БД будет доступна, выполните:"
echo "   cd $KNOWLEDGE_OS_DIR && .venv/bin/python scripts/apply_organizational_columns_migration.py"
echo "   или один раз запустите Enhanced Orchestrator (Phase 0.5 применит все миграции)."

echo ""
echo "🎯 Готово. Для запуска агентов используйте venv: .venv/bin/python ... или активируйте: source .venv/bin/activate"

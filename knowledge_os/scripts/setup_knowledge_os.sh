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

# 2. Критичные пакеты: сначала asyncpg (без тяжёлых native deps)
echo "📥 Устанавливаю asyncpg..."
.venv/bin/pip install -q "asyncpg>=0.29.0"
# 3. Остальные зависимости (Pillow может не собраться без libjpeg — brew install jpeg)
echo "📥 Устанавливаю остальные зависимости (requirements.txt)..."
.venv/bin/pip install -q -r requirements.txt || true
# 4. Если moondream не встал из-за Pillow — ставим без зависимостей (vision через API)
.venv/bin/python -c "import moondream" 2>/dev/null || .venv/bin/pip install -q "moondream>=0.1.0" --no-deps || true
if .venv/bin/python -c "import asyncpg" 2>/dev/null; then
  echo "✅ asyncpg установлен"
else
  echo "❌ asyncpg не установлен"
  exit 1
fi
# 5. Pillow (картинки): при ошибке сборки — сотрудники ставят по необходимости
if .venv/bin/python -c "from PIL import Image" 2>/dev/null; then
  echo "✅ Pillow установлен (работа с картинками)"
else
  echo "⚠️  Pillow не собрался (нужен libjpeg). Vision через API работает без него."
  echo "   Для локальной работы с картинками выполните: bash knowledge_os/scripts/install_pillow.sh"
fi
echo "✅ Зависимости установлены (asyncpg, moondream, watchdog и др.)."

# 3. Миграция (применить при доступной БД)
echo "ℹ️ Миграция организационных колонок (experts): когда БД будет доступна, выполните:"
echo "   cd $KNOWLEDGE_OS_DIR && .venv/bin/python scripts/apply_organizational_columns_migration.py"
echo "   или один раз запустите Enhanced Orchestrator (Phase 0.5 применит все миграции)."

echo ""
echo "🎯 Готово. Для запуска агентов используйте venv: .venv/bin/python ... или активируйте: source .venv/bin/activate"

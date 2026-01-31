#!/bin/bash
# Всё в одном: venv + зависимости + один цикл обучения и оркестрации.
# Использует локальную БД (DATABASE_URL из .env или localhost).

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "🚀 Запуск всего (venv + обучение + оркестрация)"
echo ""

# Загружаем .env из корня
if [ -f "$PROJECT_ROOT/.env" ]; then
  set -a
  source "$PROJECT_ROOT/.env" 2>/dev/null || true
  set +a
fi

# 1. Setup venv и зависимости (если нужно)
if [ ! -x "$PROJECT_ROOT/knowledge_os/.venv/bin/python" ] || ! "$PROJECT_ROOT/knowledge_os/.venv/bin/python" -c "import asyncpg" 2>/dev/null; then
    echo "📦 Настройка venv и зависимостей..."
    bash "$SCRIPT_DIR/setup_knowledge_os_venv.sh" || exit 1
    echo ""
fi

# 2. Обучение + оркестрация
bash "$SCRIPT_DIR/run_learning_and_orchestration.sh" || exit 1

echo ""
echo "✅ Готово. Данные в локальной БД; дашборд обновит вкладки «Академия ИИ», «Задачи», «База знаний»."

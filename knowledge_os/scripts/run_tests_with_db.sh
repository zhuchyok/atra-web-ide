#!/usr/bin/env bash
# Реальные тесты Knowledge OS: venv + PostgreSQL (DATABASE_URL).
# Запуск из корня knowledge_os:
#   ./scripts/run_tests_with_db.sh           — тесты Victoria/Department (по умолчанию)
#   ./scripts/run_tests_with_db.sh tests/    — все тесты
#   make test                                — то же, что без аргументов
# Для тестов с БД нужен запущенный PostgreSQL и DATABASE_URL (или по умолчанию localhost:5432).

set -e
cd "$(dirname "$0")/.."
ROOT="$PWD"

# Выбор Python из venv (сначала venv, потом .venv) — проверяем, что интерпретатор реально работает
for VENV in "$ROOT/venv" "$ROOT/.venv"; do
  for EXE in python3 python; do
    if [ -x "$VENV/bin/$EXE" ] && "$VENV/bin/$EXE" -c "pass" 2>/dev/null; then
      PYTHON="$VENV/bin/$EXE"
      PIP="$VENV/bin/pip"
      break 2
    fi
  done
done
if [ -z "$PYTHON" ]; then
  echo "❌ Рабочее виртуальное окружение не найдено (venv или .venv)."
  echo "   Создайте и установите зависимости:"
  echo "   cd $ROOT && python3 -m venv venv && ./venv/bin/pip install -r requirements.txt"
  exit 1
fi

# Убедиться, что в окружении есть все зависимости для реальных тестов (в т.ч. asyncpg, pytest)
if ! "$PYTHON" -c "import asyncpg, pytest" 2>/dev/null; then
  echo "⚠️ Устанавливаю зависимости из requirements.txt..."
  "$PYTHON" -m pip install -q -r "$ROOT/requirements.txt"
fi

# DATABASE_URL для приложения и тестов (реальная БД)
export DATABASE_URL="${DATABASE_URL:-postgresql://admin:secret@localhost:5432/knowledge_os}"
export TEST_DATABASE_URL="${TEST_DATABASE_URL:-postgresql://admin:secret@localhost:5432/knowledge_os_test}"

# Чтобы тесты видели пакет app (knowledge_os/app)
export PYTHONPATH="${ROOT}:${PYTHONPATH:-}"

echo "🧪 Реальные тесты Knowledge OS (venv + БД)"
echo "   PYTHON=$PYTHON"
echo "   DATABASE_URL=$DATABASE_URL"
echo "   TEST_DATABASE_URL=$TEST_DATABASE_URL"
echo ""

# Запуск реальных тестов (Victoria/Department, с БД когда доступна)
# Передайте свои аргументы: ./scripts/run_tests_with_db.sh tests/ — запустить все тесты
if [ $# -gt 0 ]; then
  "$PYTHON" -m pytest "$@" -v --tb=short 2>&1
else
  # По умолчанию — Victoria/Department + вся цепочка (просьба → Department Heads → Task Distribution → синтез)
  "$PYTHON" -m pytest tests/test_victoria_chat_and_request.py tests/test_chain_department_heads.py -v --tb=short 2>&1
fi

echo ""
echo "✅ Тесты завершены."

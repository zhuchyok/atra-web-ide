#!/bin/bash
# Один раз: включить авто-синхронизацию сотрудников при коммите.
# После этого при изменении configs/experts/employees.json и git commit
# автоматически запустится sync_employees.py и в коммит попадут обновлённые файлы.

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

HOOKS_DIR=".githooks"
PRE_COMMIT="$HOOKS_DIR/pre-commit"

if [ ! -f "$PRE_COMMIT" ]; then
  echo "Не найден $PRE_COMMIT"
  exit 1
fi
chmod +x "$PRE_COMMIT"
git config core.hooksPath "$HOOKS_DIR"
echo "Готово. Git использует хуки из $HOOKS_DIR."
echo "При коммите изменённого configs/experts/employees.json sync_employees.py запустится автоматически."

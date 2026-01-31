#!/bin/bash
# Создаёт venv для Locust (обход externally-managed-environment на macOS).
# После запуска: ./scripts/run_load_test.sh будет использовать этот venv.

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$SCRIPT_DIR/.venv"

if [ -d "$VENV_DIR" ] && [ -f "$VENV_DIR/bin/activate" ]; then
  echo "✅ Venv уже есть: $VENV_DIR"
  echo "   Проверка locust..."
  "$VENV_DIR/bin/python" -c "import locust" 2>/dev/null && { echo "   Locust установлен."; exit 0; }
fi

echo "Создание venv и установка locust..."
python3 -m venv "$VENV_DIR"
"$VENV_DIR/bin/pip" install --upgrade pip -q
"$VENV_DIR/bin/pip" install locust -q
echo "✅ Готово. Запускайте: RUN_TIME=1m USERS=30 SPAWN_RATE=5 ./scripts/run_load_test.sh"

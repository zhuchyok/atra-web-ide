#!/bin/bash
# =============================================================================
# Запуск backend, тесты API (--live), остановка backend
# Требует: Python venv (backend/.venv), httpx, БД Knowledge OS на localhost:5432
# =============================================================================

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

BACKEND_PORT="${BACKEND_PORT:-9876}"
VENV_PYTHON="${ROOT}/backend/.venv/bin/python"
UVICORN="${ROOT}/backend/.venv/bin/python -m uvicorn"

echo "=============================================="
echo "🧪 ATRA Web IDE — тесты API (live)"
echo "=============================================="
echo ""

if [ ! -x "$VENV_PYTHON" ]; then
    echo "❌ Не найден backend/.venv. Создайте: cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
    exit 1
fi

# Остановить предыдущий uvicorn на порту
pkill -f "uvicorn app.main:app.*${BACKEND_PORT}" 2>/dev/null || true
sleep 2

echo "[1/3] Запуск backend на :${BACKEND_PORT}..."
cd "$ROOT/backend"
PYTHONPATH=. $UVICORN app.main:app --host 127.0.0.1 --port "$BACKEND_PORT" &
UPID=$!
cd "$ROOT"

echo "[2/3] Ожидание готовности..."
for i in $(seq 1 30); do
    if curl -s -o /dev/null -w "%{http_code}" "http://127.0.0.1:${BACKEND_PORT}/" 2>/dev/null | grep -q 200; then
        echo "     Backend готов."
        break
    fi
    sleep 1
    if [ "$i" -eq 30 ]; then
        echo "❌ Backend не запустился за 30 сек."
        kill $UPID 2>/dev/null
        exit 1
    fi
done

sleep 1

echo "[3/3] Запуск тестов..."
PYTHONPATH=backend "$VENV_PYTHON" scripts/test_all.py --live "http://127.0.0.1:${BACKEND_PORT}"
EX=$?

kill $UPID 2>/dev/null
wait $UPID 2>/dev/null || true

echo ""
if [ $EX -eq 0 ]; then
    echo "✅ Все тесты пройдены."
else
    echo "❌ Часть тестов не пройдена (exit $EX)."
fi
exit $EX

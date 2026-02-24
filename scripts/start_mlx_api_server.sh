#!/usr/bin/env bash
set -euo pipefail

# Запуск MLX API Server на Mac Studio (вместо Ollama)
# Эмулирует Ollama API на порту 11435, используя MLX модели
# Порт можно изменить через переменную окружения MLX_API_PORT

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

LOG_DIR="$HOME/Library/Logs/atra"
mkdir -p "$LOG_DIR"

echo "🚀 Запуск MLX API Server (вместо Ollama)"
echo "========================================"
echo ""

# Python: MLX_PYTHON (из автопроверки/venv) или python3
if [ -n "${MLX_PYTHON:-}" ] && [ -x "$MLX_PYTHON" ]; then
  PYTHON_CMD="$MLX_PYTHON"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_CMD=python3
else
  echo "❌ Python не найден (задайте MLX_PYTHON или установите python3)"
  exit 1
fi

# Проверка uvicorn
if ! python3 -c "import uvicorn" 2>/dev/null; then
  echo "⚠️  uvicorn не установлен, устанавливаю..."
  pip3 install uvicorn fastapi
fi

# Проверка mlx_api_server
API_SERVER_PATH="$ROOT_DIR/knowledge_os/app/mlx_api_server.py"
if [[ ! -f "$API_SERVER_PATH" ]]; then
  echo "❌ MLX API Server не найден: $API_SERVER_PATH"
  exit 1
fi

echo "✅ MLX API Server найден"
echo ""

# MLX API Server работает на порту 11435 (можно изменить через MLX_API_PORT)
MLX_PORT=${MLX_API_PORT:-11435}

# Rate limit: реже 429 (по умолчанию 150 запросов / 90 с)
export MLX_RATE_LIMIT_MAX=${MLX_RATE_LIMIT_MAX:-150}
export MLX_RATE_LIMIT_WINDOW=${MLX_RATE_LIMIT_WINDOW:-90}
# Параллелизм: 1 — снижает Metal OOM и краш Python (mlx::core::gpu::check_error)
export MLX_MAX_CONCURRENT=${MLX_MAX_CONCURRENT:-1}
# Кэш: 1 модель — меньше пиковая память GPU, реже краши (см. docs/MLX_PYTHON_CRASH_CAUSE.md)
export MLX_MAX_CACHED_MODELS=${MLX_MAX_CACHED_MODELS:-1}
# Предзагрузка: по умолчанию fast (лёгкая). Для полноценной Виктории (мозг в MLX + руки в Ollama) задайте VICTORIA_MLX_BRAIN=true
export VICTORIA_MLX_BRAIN=${VICTORIA_MLX_BRAIN:-false}
export MLX_PRELOAD_MODELS=${MLX_PRELOAD_MODELS:-fast}

# Освобождение порта: убиваем все процессы на MLX_PORT (несколько PID при зависших воркерах)
free_port() {
  local pids
  pids=$(lsof -ti:$MLX_PORT 2>/dev/null)
  if [ -n "$pids" ]; then
    echo "⚠️  Порт $MLX_PORT занят (PID: $pids)"
    echo "$pids" | xargs kill -9 2>/dev/null || true
    sleep 2
    # Проверка: если порт всё ещё занят — ещё раз
    pids=$(lsof -ti:$MLX_PORT 2>/dev/null)
    if [ -n "$pids" ]; then
      echo "$pids" | xargs kill -9 2>/dev/null || true
      sleep 2
    fi
  fi
}

if lsof -ti:$MLX_PORT >/dev/null 2>&1; then
  if [ -t 0 ]; then
    read -p "Остановить процесс(ы) на порту $MLX_PORT и запустить MLX API Server? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
      echo "Отменено"
      exit 0
    fi
  fi
  free_port
fi

# Перед запуском убедиться, что порт свободен
if lsof -ti:$MLX_PORT >/dev/null 2>&1; then
  echo "❌ Порт $MLX_PORT всё ещё занят после освобождения. Проверьте: lsof -i:$MLX_PORT"
  exit 1
fi

echo "📡 Запуск MLX API Server на порту $MLX_PORT..."
echo "   Логи: $LOG_DIR/mlx_api_server.log"
echo ""

# Сохраняем PID для монитора
PID_FILE="$LOG_DIR/mlx_api_server.pid"

# Запуск в фоне
# Используем прямой путь к модулю, чтобы избежать конфликта с knowledge_os.py в корне
cd "$ROOT_DIR/knowledge_os"
nohup $PYTHON_CMD -m uvicorn app.mlx_api_server:app \
  --host 0.0.0.0 \
  --port $MLX_PORT \
  --timeout-keep-alive 30 \
  --log-level info \
  > "$LOG_DIR/mlx_api_server.log" 2>&1 &
cd "$ROOT_DIR"

MLX_PID=$!
echo "$MLX_PID" > "$PID_FILE"
sleep 3

# Проверка, запустился ли
if ps -p "$MLX_PID" > /dev/null 2>&1; then
  echo "✅ MLX API Server запущен (PID: $MLX_PID)"
  echo "   PID сохранен: $PID_FILE"
  echo ""

  # Проверка доступности (до 15 секунд)
  MAX_WAIT=15
  WAITED=0
  while [ $WAITED -lt $MAX_WAIT ]; do
    if curl -s -f --connect-timeout 2 "http://localhost:$MLX_PORT/" >/dev/null 2>&1; then
      echo "✅ MLX API Server доступен на http://localhost:$MLX_PORT"
      echo ""
      echo "📋 Проверка моделей:"
      curl -s "http://localhost:$MLX_PORT/api/tags" | python3 -m json.tool 2>/dev/null | head -20 || echo "   (API отвечает, но модели могут быть не загружены)"
      break
    fi
    sleep 1
    WAITED=$((WAITED + 1))
    # Проверяем, не упал ли процесс
    if ! ps -p "$MLX_PID" > /dev/null 2>&1; then
      echo "❌ MLX API Server упал сразу после запуска"
      echo "   Проверь логи: $LOG_DIR/mlx_api_server.log"
      tail -20 "$LOG_DIR/mlx_api_server.log" 2>/dev/null || true
      rm -f "$PID_FILE"
      exit 1
    fi
  done

  if [ $WAITED -ge $MAX_WAIT ]; then
    echo "⚠️  MLX API Server запущен, но еще не отвечает (подожди еще 5-10 секунд)"
    echo "   Логи: tail -f $LOG_DIR/mlx_api_server.log"
  fi

  echo ""
  echo "💡 Для остановки:"
  echo "   kill $MLX_PID"
  echo "   или: pkill -f 'uvicorn.*mlx_api_server'"
  echo ""
  echo "📊 Логи:"
  echo "   tail -f $LOG_DIR/mlx_api_server.log"
else
  echo "❌ Не удалось запустить MLX API Server"
  echo "   Проверь логи: $LOG_DIR/mlx_api_server.log"
  tail -30 "$LOG_DIR/mlx_api_server.log" 2>/dev/null || true
  rm -f "$PID_FILE"
  exit 1
fi

#!/usr/bin/env bash
# Автоматический запуск MLX API Server - одна команда для копирования

# Находим репозиторий автоматически
ROOT=""
for dir in ~/Documents/dev/atra ~/atra ~/Documents/GITHUB/atra/atra; do
  if [ -f "$dir/docker-compose.yml" ]; then
    ROOT="$dir"
    cd "$dir"
    break
  fi
done

if [ -z "$ROOT" ]; then
  echo "❌ Репозиторий не найден"
  exit 1
fi

echo "📁 Репозиторий: $ROOT"
API="$ROOT/knowledge_os/app/mlx_api_server.py"

if [ ! -f "$API" ]; then
  echo "❌ Файл не найден: $API"
  exit 1
fi

echo "✅ Файл найден"

# Зависимости
if ! python3 -c "import uvicorn" 2>/dev/null; then
  echo "📦 Устанавливаю uvicorn..."
  pip3 install --user uvicorn fastapi >/dev/null 2>&1 || pip3 install uvicorn fastapi >/dev/null 2>&1
fi

# Порт MLX API Server (можно изменить через MLX_API_PORT)
MLX_PORT=${MLX_API_PORT:-11435}

# Останавливаем старый
lsof -ti:${MLX_PORT} | xargs kill >/dev/null 2>&1 || true
sleep 2

# Запускаем
mkdir -p ~/Library/Logs/atra
cd "$ROOT"
export PYTHONPATH="$ROOT:$PYTHONPATH"
export MLX_API_PORT=${MLX_PORT}

echo "🚀 Запуск MLX API Server на порту ${MLX_PORT}..."
nohup python3 -m uvicorn knowledge_os.app.mlx_api_server:app \
  --host 0.0.0.0 \
  --port ${MLX_PORT} \
  > ~/Library/Logs/atra/mlx_api_server.log 2>&1 &

PID=$!
sleep 4

if ps -p "$PID" >/dev/null 2>&1; then
  if curl -s http://localhost:${MLX_PORT}/ >/dev/null 2>&1; then
    echo "✅ MLX API Server работает! (PID: $PID)"
    echo "🌐 http://localhost:${MLX_PORT}"
  else
    echo "⚠️  Запускается... (PID: $PID)"
    echo "📊 Логи: tail -f ~/Library/Logs/atra/mlx_api_server.log"
  fi
else
  echo "❌ Ошибка запуска:"
  tail -15 ~/Library/Logs/atra/mlx_api_server.log 2>/dev/null | grep -i error || tail -10 ~/Library/Logs/atra/mlx_api_server.log
  exit 1
fi

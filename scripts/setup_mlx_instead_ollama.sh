#!/usr/bin/env bash
set -euo pipefail

# Полная настройка MLX API Server вместо Ollama на Mac Studio

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

echo "🚀 Настройка MLX API Server вместо Ollama"
echo "=========================================="
echo ""

# 1. Проверка зависимостей
echo "[1/4] Проверка зависимостей..."
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ Python3 не установлен"
  exit 1
fi

if ! python3 -c "import uvicorn, fastapi" 2>/dev/null; then
  echo "⚠️  Устанавливаю uvicorn и fastapi..."
  pip3 install uvicorn fastapi
fi

if ! python3 -c "import mlx.core" 2>/dev/null; then
  echo "⚠️  MLX не установлен. Устанавливаю..."
  pip3 install mlx mlx-lm
fi

echo "✅ Зависимости готовы"
echo ""

# 2. Остановка Ollama (если запущена)
echo "[2/4] Проверка Ollama..."
if pgrep -f "ollama serve" >/dev/null 2>&1; then
  echo "⚠️  Ollama запущена. Останавливаю..."
  pkill -f "ollama serve" || true
  sleep 2
  echo "✅ Ollama остановлена"
else
  echo "✅ Ollama не запущена"
fi
echo ""

# 3. Запуск MLX API Server
echo "[3/4] Запуск MLX API Server..."
if [[ -f "scripts/start_mlx_api_server.sh" ]]; then
  bash scripts/start_mlx_api_server.sh
else
  echo "⚠️  Скрипт запуска не найден, запускаю напрямую..."
  LOG_DIR="$HOME/Library/Logs/atra"
  mkdir -p "$LOG_DIR"

  nohup python3 -m uvicorn knowledge_os.app.mlx_api_server:app \
    --host 0.0.0.0 \
    --port 11434 \
    --app-dir "$ROOT_DIR/knowledge_os/app" \
    > "$LOG_DIR/mlx_api_server.log" 2>&1 &

  sleep 3
  if curl -s -f "http://localhost:11434/" >/dev/null 2>&1; then
    echo "✅ MLX API Server запущен"
  else
    echo "⚠️  MLX API Server запускается (подожди 5-10 секунд)"
  fi
fi
echo ""

# 4. Настройка автозапуска
echo "[4/4] Настройка автозапуска..."
if [[ -f "scripts/setup_mlx_api_autostart.sh" ]]; then
  bash scripts/setup_mlx_api_autostart.sh
else
  echo "⚠️  Скрипт автозапуска не найден"
fi
echo ""

echo "=========================================="
echo "✅ Настройка завершена!"
echo ""
echo "📋 Проверка:"
echo "   curl http://localhost:11434/"
echo "   curl http://localhost:11434/api/tags"
echo ""
echo "📊 Логи:"
echo "   tail -f ~/Library/Logs/atra/mlx_api_server.log"
echo ""
echo "💡 MLX API Server работает вместо Ollama на порту 11434"

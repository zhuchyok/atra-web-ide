#!/bin/bash
# Полный запуск корпорации ATRA на Mac Studio (Singularity 31.2)
# Оптимизированная версия: использует разделенные docker-compose файлы

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "🚀 ЗАПУСК ПОЛНОЙ КОРПОРАЦИИ ATRA (v31.2)"
echo "=============================================="

# 1. Базовые проверки
if ! docker info >/dev/null 2>&1; then
    echo "❌ Docker не запущен."
    exit 1
fi

# 2. Запуск всего стека
echo "[1/3] Запуск Docker Compose (Core + Agents + UI + Monitoring)..."
docker-compose -f knowledge_os/docker-compose.yml up -d

# 3. Запуск Rust Gateway (если собран)
echo "[2/3] Запуск Rust Gateway..."
if [ -f "$ROOT/target/release/gateway" ]; then
    ps aux | grep gateway | grep -v grep | awk '{print $2}' | xargs kill -9 2>/dev/null || true
    RUST_LOG=info WORKSPACE_ROOT="$ROOT" "$ROOT/target/release/gateway" > "$ROOT/gateway.log" 2>&1 &
    echo "   ✅ Rust Gateway запущен (порт 8081)"
else
    echo "   ⚠️  Rust Gateway не найден. Пропуск."
fi

# 4. Финальная проверка
echo "[3/3] Верификация сервисов..."
sleep 10

docker-compose -f knowledge_os/docker-compose.yml ps

echo ""
echo "=============================================="
echo "✅ КОРПОРАЦИЯ ГОТОВА К РАБОТЕ"
echo "=============================================="

#!/bin/bash
# Автоматический запуск контейнеров на Mac Studio
# Пытается подключиться и запустить контейнеры

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MAC_STUDIO_IP="192.168.1.64"
MAC_STUDIO_USER="bikos"
MAC_STUDIO_PATH="~/Documents/atra-web-ide"

echo "=============================================="
echo "🚀 АВТОМАТИЧЕСКИЙ ЗАПУСК КОНТЕЙНЕРОВ"
echo "=============================================="
echo ""

# Попытка подключения
echo "🔍 Попытка подключения к Mac Studio..."
if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} "echo 'OK'" 2>/dev/null; then
    echo "   ✅ Подключение установлено"
    echo ""
    echo "🚀 Запуск контейнеров..."

    set +e
    ssh ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} << 'ENDSSH'
cd ~/Documents/atra-web-ide
export PATH="/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"

echo "[1/3] Проверка Docker..."
if ! docker info &> /dev/null; then
    echo "   ❌ Docker не запущен!"
    exit 1
fi
echo "   ✅ Docker готов"

echo ""
echo "[2/3] Запуск контейнеров..."
if [ -f "knowledge_os/docker-compose.yml" ]; then
    set +e
    set +o pipefail
    docker-compose -f knowledge_os/docker-compose.yml up -d 2>&1 | grep -v "level=warning"
    compose_rc=${PIPESTATUS[0]}
    set -o pipefail
    set -e
    if [ "$compose_rc" -ne 0 ]; then
        echo "   ❌ docker-compose up failed (rc=$compose_rc)"
        exit 1
    fi
    echo "   ⏳ Ожидание запуска (20 секунд)..."
    sleep 20
else
    echo "   ❌ docker-compose.yml не найден!"
    exit 1
fi

echo ""
echo "[3/3] Проверка статуса..."
docker-compose -f knowledge_os/docker-compose.yml ps 2>&1 | grep -v "level=warning" || true

echo ""
echo "✅ Проверка сервисов:"
FAIL=0
if curl -sf http://localhost:8010/health >/dev/null 2>&1; then
    echo " - Victoria OK"
else
    echo " - Victoria не отвечает"
    FAIL=1
fi
if curl -sf http://localhost:8011/health >/dev/null 2>&1; then
    echo " - Veronica OK"
else
    echo " - Veronica не отвечает"
    FAIL=1
fi
exit $FAIL
ENDSSH
    remote_rc=$?
    set -e
    if [ "$remote_rc" -eq 0 ]; then
        echo ""
        echo "=============================================="
        echo "✅ КОНТЕЙНЕРЫ ЗАПУЩЕНЫ"
        echo "=============================================="
        exit 0
    else
        echo ""
        echo "❌ Ошибка при запуске (remote rc=$remote_rc)"
        exit 1
    fi
else
    echo "   ❌ Mac Studio недоступен по SSH"
    echo ""
    echo "=============================================="
    echo "⚠️  АВТОМАТИЧЕСКИЙ ЗАПУСК НЕВОЗМОЖЕН"
    echo "=============================================="
    echo ""
    echo "📝 ВЫПОЛНИТЕ НА MAC STUDIO:"
    echo ""
    echo "   cd ~/Documents/atra-web-ide"
    echo "   bash scripts/check_and_start_containers.sh"
    echo ""
    echo "   ИЛИ:"
    echo ""
    echo "   export PATH=\"/usr/local/bin:/Applications/Docker.app/Contents/Resources/bin:\$PATH\""
    echo "   docker-compose -f knowledge_os/docker-compose.yml up -d"
    echo ""
    exit 1
fi

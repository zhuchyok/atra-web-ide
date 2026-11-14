#!/bin/bash
# Применение изменений на Mac Studio
# Проверка и синхронизация всех изменений из этого чата

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
HARD_FAIL=0

MAC_STUDIO_IP="192.168.1.64"
MAC_STUDIO_USER="bikos"
MAC_STUDIO_PATH="~/Documents/atra-web-ide"

echo "=============================================="
echo "🔄 ПРИМЕНЕНИЕ ИЗМЕНЕНИЙ НА MAC STUDIO"
echo "=============================================="
echo ""

# Проверка SSH доступа
echo "[1/5] Проверка SSH доступа к Mac Studio..."
if ! ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} "echo 'OK'" 2>/dev/null; then
    echo "   ❌ SSH недоступен к Mac Studio — remote apply невозможен"
    echo "   📝 Инструкция: APPLY_CHANGES_ON_MAC_STUDIO.md"
    echo "   💡 Локальный fallback без SSH не считается успешным remote apply"
    exit 1
fi
echo "   ✅ SSH доступен"
echo ""

# Синхронизация файлов
echo "[2/5] Синхронизация измененных файлов..."

# 1. victoria_mcp_server.py
echo "   📤 src/agents/bridge/victoria_mcp_server.py"
scp -o StrictHostKeyChecking=no \
    src/agents/bridge/victoria_mcp_server.py \
    ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/src/agents/bridge/ 2>/dev/null || echo "      ⚠️  Ошибка копирования"

# 2. victoria_enhanced.py
echo "   📤 knowledge_os/app/victoria_enhanced.py"
scp -o StrictHostKeyChecking=no \
    knowledge_os/app/victoria_enhanced.py \
    ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/knowledge_os/app/ 2>/dev/null || echo "      ⚠️  Ошибка копирования"

# 3. backend/app/routers/chat.py (с изменениями для Victoria Enhanced)
echo "   📤 backend/app/routers/chat.py"
scp -o StrictHostKeyChecking=no \
    backend/app/routers/chat.py \
    ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/backend/app/routers/ 2>/dev/null || echo "      ⚠️  Ошибка копирования"

echo "   ✅ Файлы синхронизированы"
echo ""

# Проверка статуса сервисов на Mac Studio (live ports)
echo "[3/5] Проверка статуса сервисов на Mac Studio..."
HARD_FAIL=0
REMOTE_STATUS=$(ssh ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} << 'EOF'
    FAIL=0
    echo "   Проверка Victoria (8010)..."
    if curl -s -f http://localhost:8010/health >/dev/null 2>&1; then
        echo "      ✅ Victoria работает"
    else
        echo "      ❌ Victoria не работает"
        FAIL=1
    fi
    echo "   Проверка Ollama brain (11434)..."
    if curl -s -f http://localhost:11434/api/tags >/dev/null 2>&1; then
        echo "      ✅ Ollama brain работает"
    else
        echo "      ❌ Ollama brain не работает"
        FAIL=1
    fi
    echo "   Проверка Docker victoria-agent..."
    if docker ps --format '{{.Names}}' | grep -q '^victoria-agent$'; then
        echo "      ✅ Victoria контейнер запущен"
    else
        echo "      ❌ Victoria контейнер не запущен"
        FAIL=1
    fi
    exit $FAIL
EOF
) || HARD_FAIL=1
echo "$REMOTE_STATUS"
echo ""

# Применение изменений в chat.py (если нужно)
echo "[4/5] Применение изменений в chat.py для Victoria Enhanced..."
ssh ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} << 'EOF'
    cd ~/Documents/atra-web-ide

    # Проверяем, применено ли изменение
    if grep -q "Victoria Enhanced: всегда используем Victoria Enhanced" backend/app/routers/chat.py 2>/dev/null; then
        echo "      ✅ Изменение уже применено"
    else
        echo "      🔧 Применяем изменение..."
        # Создаем backup
        cp backend/app/routers/chat.py backend/app/routers/chat.py.bak

        # Применяем изменение (заменяем строку 155-156)
        sed -i.bak2 's/# Умный роутинг: простые сообщения -> Ollama, сложные -> Victoria/# Victoria Enhanced: всегда используем Victoria Enhanced, если use_victoria=True/' backend/app/routers/chat.py
        sed -i.bak3 's/use_ollama_direct = is_simple_message(message.content) or not message.use_victoria/use_ollama_direct = not message.use_victoria/' backend/app/routers/chat.py

        echo "      ✅ Изменение применено"
    fi
EOF
echo ""

# Перезапуск сервисов (если нужно)
echo "[5/5] Перезапуск сервисов (если нужно)..."
ssh ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} << 'EOF'
    cd ~/Documents/atra-web-ide

    # Перезапуск Victoria контейнера
    if docker ps | grep -q victoria-agent; then
        echo "      🔄 Перезапуск Victoria контейнера..."
        docker restart victoria-agent
        sleep 3
        echo "      ✅ Victoria перезапущена"
    fi

    # Перезапуск MCP сервера (если запущен)
    if pgrep -f "victoria_mcp_server" > /dev/null; then
        echo "      🔄 Перезапуск MCP сервера..."
        pkill -f "victoria_mcp_server"
        sleep 2
        cd ~/Documents/atra-web-ide
        export PYTHONPATH=~/Documents/atra-web-ide:$PYTHONPATH
        nohup python3 -m src.agents.bridge.victoria_mcp_server > /tmp/victoria_mcp.log 2>&1 &
        sleep 2
        echo "      ✅ MCP сервер перезапущен"
    fi
EOF
echo ""

echo "=============================================="
if [ "${HARD_FAIL:-0}" -eq 0 ]; then
    echo "✅ ИЗМЕНЕНИЯ ПРИМЕНЕНЫ НА MAC STUDIO"
else
    echo "⚠️ ПРИМЕНЕНИЕ ЗАВЕРШЕНО С ОШИБКАМИ"
fi
echo "=============================================="
echo ""
echo "📋 Проверка:"
echo "   curl http://192.168.1.64:8010/health"
echo "   curl http://192.168.1.64:11434/api/tags"
echo ""
exit "${HARD_FAIL:-0}"

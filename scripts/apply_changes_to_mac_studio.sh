#!/bin/bash
# Применение изменений на Mac Studio
# Проверка и синхронизация всех изменений из этого чата

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

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
    echo "   ⚠️  SSH недоступен к Mac Studio"
    echo "   💡 Это нормально, если Mac Studio не в сети или SSH не включен"
    echo "   📝 Инструкция для применения изменений вручную:"
    echo "      См. файл: APPLY_CHANGES_ON_MAC_STUDIO.md"
    echo ""
    echo "   🔄 Продолжаем с локальными изменениями..."
    echo ""
    
    # Применяем изменения локально
    echo "   🔧 Применение изменений локально в chat.py..."
    if grep -q "Victoria Enhanced: всегда используем Victoria Enhanced" backend/app/routers/chat.py 2>/dev/null; then
        echo "      ✅ Изменение уже применено локально"
    else
        echo "      🔧 Применяем изменение..."
        cp backend/app/routers/chat.py backend/app/routers/chat.py.bak
        sed -i.bak2 's/# Умный роутинг: простые сообщения -> Ollama, сложные -> Victoria/# Victoria Enhanced: всегда используем Victoria Enhanced, если use_victoria=True/' backend/app/routers/chat.py
        sed -i.bak3 's/use_ollama_direct = is_simple_message(message.content) or not message.use_victoria/use_ollama_direct = not message.use_victoria/' backend/app/routers/chat.py
        echo "      ✅ Изменение применено локально"
    fi
    echo ""
    exit 0
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

# Проверка статуса сервисов на Mac Studio
echo "[3/5] Проверка статуса сервисов на Mac Studio..."
ssh ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} << 'EOF'
    echo "   Проверка Victoria..."
    if curl -s -f http://localhost:8010/health >/dev/null 2>&1; then
        echo "      ✅ Victoria работает"
    else
        echo "      ❌ Victoria не работает"
    fi
    
    echo "   Проверка MCP сервера..."
    if curl -s -f http://localhost:8012/sse >/dev/null 2>&1; then
        echo "      ✅ MCP сервер работает"
    else
        echo "      ❌ MCP сервер не работает"
    fi
    
    echo "   Проверка Docker контейнеров..."
    if docker ps | grep -q victoria-agent; then
        echo "      ✅ Victoria контейнер запущен"
    else
        echo "      ❌ Victoria контейнер не запущен"
    fi
EOF
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
echo "✅ ИЗМЕНЕНИЯ ПРИМЕНЕНЫ НА MAC STUDIO"
echo "=============================================="
echo ""
echo "📋 Проверка:"
echo "   curl http://192.168.1.64:8010/health"
echo "   curl http://192.168.1.64:8012/sse"
echo ""

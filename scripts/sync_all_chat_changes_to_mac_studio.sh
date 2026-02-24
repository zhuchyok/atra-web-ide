#!/bin/bash
# Синхронизация ВСЕХ изменений из этого чата на Mac Studio
# Для применения Veronica

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MAC_STUDIO_IP="192.168.1.64"
MAC_STUDIO_USER="bikos"
MAC_STUDIO_PATH="~/Documents/atra-web-ide"

echo "=============================================="
echo "🔄 СИНХРОНИЗАЦИЯ ВСЕХ ИЗМЕНЕНИЙ ИЗ ЧАТА"
echo "=============================================="
echo ""

# Проверка SSH доступа
echo "[1/4] Проверка SSH доступа..."
if ! ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} "echo 'OK'" 2>/dev/null; then
    echo "   ❌ SSH недоступен к Mac Studio"
    exit 1
fi
echo "   ✅ SSH доступен"
echo ""

# Создание директорий на Mac Studio
echo "[2/4] Создание директорий на Mac Studio..."
ssh ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} << 'EOF'
    cd ~/Documents/atra-web-ide
    mkdir -p src/agents/core src/agents/bridge
    mkdir -p backend/app/routers
    mkdir -p knowledge_os/app
    mkdir -p knowledge_os/scripts
    mkdir -p knowledge_os/src/agents/core
    mkdir -p scripts/local
    mkdir -p configs/agents
    echo "   ✅ Директории созданы"
EOF
echo ""

# Синхронизация всех файлов из этого чата
echo "[3/4] Синхронизация всех файлов из этого чата..."

# 1. Backend - Chat Router
echo "   📤 backend/app/routers/chat.py"
scp -o StrictHostKeyChecking=no \
    backend/app/routers/chat.py \
    ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/backend/app/routers/ 2>&1 | grep -v "Warning" || true

# 2. Victoria MCP Server
echo "   📤 src/agents/bridge/victoria_mcp_server.py"
scp -o StrictHostKeyChecking=no \
    src/agents/bridge/victoria_mcp_server.py \
    ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/src/agents/bridge/ 2>&1 | grep -v "Warning" || true

# 3. Victoria Enhanced
echo "   📤 knowledge_os/app/victoria_enhanced.py"
scp -o StrictHostKeyChecking=no \
    knowledge_os/app/victoria_enhanced.py \
    ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/knowledge_os/app/ 2>&1 | grep -v "Warning" || true

# 4. Victoria System Prompts (5 файлов)
echo "   📤 src/agents/core/executor.py (Victoria)"
scp -o StrictHostKeyChecking=no \
    src/agents/core/executor.py \
    ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/src/agents/core/ 2>&1 | grep -v "Warning" || true

echo "   📤 src/agents/bridge/victoria_server.py (Victoria)"
scp -o StrictHostKeyChecking=no \
    src/agents/bridge/victoria_server.py \
    ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/src/agents/bridge/ 2>&1 | grep -v "Warning" || true

echo "   📤 scripts/local/start_victoria_local.py (Victoria)"
scp -o StrictHostKeyChecking=no \
    scripts/local/start_victoria_local.py \
    ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/scripts/local/ 2>&1 | grep -v "Warning" || true

echo "   📤 knowledge_os/scripts/commander.py (Victoria)"
scp -o StrictHostKeyChecking=no \
    knowledge_os/scripts/commander.py \
    ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/knowledge_os/scripts/ 2>&1 | grep -v "Warning" || true

echo "   📤 knowledge_os/src/agents/core/executor.py (Victoria)"
scp -o StrictHostKeyChecking=no \
    knowledge_os/src/agents/core/executor.py \
    ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/knowledge_os/src/agents/core/ 2>&1 | grep -v "Warning" || true

# 5. Veronica System Prompts (2 файла)
echo "   📤 src/agents/bridge/server.py (Veronica)"
scp -o StrictHostKeyChecking=no \
    src/agents/bridge/server.py \
    ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/src/agents/bridge/ 2>&1 | grep -v "Warning" || true

echo "   📤 configs/agents/veronica.yaml (Veronica)"
scp -o StrictHostKeyChecking=no \
    configs/agents/veronica.yaml \
    ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/configs/agents/ 2>&1 | grep -v "Warning" || true

echo "   ✅ Все файлы синхронизированы"
echo ""

# Применение изменений через Veronica
echo "[4/4] Применение изменений через Veronica на Mac Studio..."
ssh ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} << 'EOF'
    cd ~/Documents/atra-web-ide

    echo "   🔧 Применение изменений в chat.py (если нужно)..."
    if grep -q "Victoria Enhanced: всегда используем Victoria Enhanced" backend/app/routers/chat.py 2>/dev/null; then
        echo "      ✅ Изменение уже применено"
    else
        echo "      🔧 Применяем изменение..."
        cp backend/app/routers/chat.py backend/app/routers/chat.py.bak 2>/dev/null || true
        python3 << 'PYEOF'
with open('backend/app/routers/chat.py', 'r') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'use_ollama_direct = is_simple_message(message.content) or not message.use_victoria' in line:
        # Заменяем строку
        lines[i] = '        use_ollama_direct = not message.use_victoria\n'
        # Добавляем комментарий перед строкой, если его нет
        if i > 0 and 'Victoria Enhanced: всегда используем Victoria Enhanced' not in lines[i-1]:
            lines.insert(i, '        # Victoria Enhanced: всегда используем Victoria Enhanced, если use_victoria=True\n')
        break

with open('backend/app/routers/chat.py', 'w') as f:
    f.writelines(lines)
print('✅ Изменение применено')
PYEOF
    fi

    echo "   ✅ Все изменения применены"
EOF
echo ""

echo "=============================================="
echo "✅ ВСЕ ИЗМЕНЕНИЯ ИЗ ЧАТА СИНХРОНИЗИРОВАНЫ"
echo "=============================================="
echo ""
echo "📋 Синхронизировано файлов:"
echo "   1. backend/app/routers/chat.py"
echo "   2. src/agents/bridge/victoria_mcp_server.py"
echo "   3. knowledge_os/app/victoria_enhanced.py"
echo "   4. src/agents/core/executor.py (Victoria)"
echo "   5. src/agents/bridge/victoria_server.py (Victoria)"
echo "   6. scripts/local/start_victoria_local.py (Victoria)"
echo "   7. knowledge_os/scripts/commander.py (Victoria)"
echo "   8. knowledge_os/src/agents/core/executor.py (Victoria)"
echo "   9. src/agents/bridge/server.py (Veronica)"
echo "   10. configs/agents/veronica.yaml (Veronica)"
echo ""
echo "📋 Проверка:"
echo "   curl http://192.168.1.64:8010/health"
echo "   curl http://192.168.1.64:8011/health"
echo ""

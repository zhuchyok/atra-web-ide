#!/bin/bash
# Полная проверка и применение ВСЕХ изменений из этого чата на Mac Studio

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MAC_STUDIO_IP="192.168.1.64"
MAC_STUDIO_USER="bikos"
MAC_STUDIO_PATH="~/Documents/atra-web-ide"

echo "=============================================="
echo "🔍 ПОЛНАЯ ПРОВЕРКА И ПРИМЕНЕНИЕ ВСЕХ ИЗМЕНЕНИЙ"
echo "=============================================="
echo ""

# Проверка SSH доступа
if ! ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} "echo 'OK'" 2>/dev/null; then
    echo "   ❌ SSH недоступен к Mac Studio"
    exit 1
fi

# Функция проверки и применения изменений
check_and_apply() {
    local file_path="$1"
    local check_pattern="$2"
    local description="$3"

    echo "   Проверка: $description"
    ssh ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} << EOF
        cd ~/Documents/atra-web-ide
        if [ -f "$file_path" ]; then
            if grep -q "$check_pattern" "$file_path" 2>/dev/null; then
                echo "      ✅ Применено"
            else
                echo "      ❌ НЕ ПРИМЕНЕНО - требуется синхронизация"
                exit 1
            fi
        else
            echo "      ❌ ФАЙЛ НЕ НАЙДЕН - требуется синхронизация"
            exit 1
        fi
EOF
}

# Список всех изменений для проверки
declare -a changes=(
    "backend/app/routers/chat.py|use_ollama_direct = not message.use_victoria|Chat Router: Victoria Enhanced"
    "src/agents/bridge/victoria_mcp_server.py|localhost:8010|Victoria MCP Server: автоопределение URL"
    "knowledge_os/app/victoria_enhanced.py|self.observability = None|Victoria Enhanced: observability"
    "src/agents/core/executor.py|VICTORIA ENHANCED|Victoria system prompt: executor"
    "src/agents/bridge/victoria_server.py|VICTORIA ENHANCED|Victoria system prompt: server"
    "scripts/local/start_victoria_local.py|VICTORIA ENHANCED|Victoria system prompt: local"
    "knowledge_os/scripts/commander.py|VICTORIA ENHANCED|Victoria system prompt: commander"
    "knowledge_os/src/agents/core/executor.py|VICTORIA ENHANCED|Victoria system prompt: knowledge_os executor"
    "src/agents/bridge/server.py|VERONICA ENHANCED|Veronica system prompt: server"
    "configs/agents/veronica.yaml|VERONICA ENHANCED|Veronica system prompt: yaml"
)

echo "[1/3] Проверка всех изменений..."
missing_files=()
for change in "${changes[@]}"; do
    IFS='|' read -r file_path check_pattern description <<< "$change"
    if ! check_and_apply "$file_path" "$check_pattern" "$description" 2>/dev/null; then
        missing_files+=("$file_path")
    fi
done
echo ""

# Если есть недостающие файлы - синхронизируем
if [ ${#missing_files[@]} -gt 0 ]; then
    echo "[2/3] Синхронизация недостающих файлов..."
    bash scripts/sync_all_chat_changes_to_mac_studio.sh
    echo ""
else
    echo "[2/3] ✅ Все файлы на месте, синхронизация не требуется"
    echo ""
fi

# Финальная проверка
echo "[3/3] Финальная проверка всех изменений..."
all_ok=true
for change in "${changes[@]}"; do
    IFS='|' read -r file_path check_pattern description <<< "$change"
    if ! check_and_apply "$file_path" "$check_pattern" "$description" 2>/dev/null; then
        all_ok=false
    fi
done
echo ""

if [ "$all_ok" = true ]; then
    echo "=============================================="
    echo "✅ ВСЕ ИЗМЕНЕНИЯ ПРИМЕНЕНЫ"
    echo "=============================================="
else
    echo "=============================================="
    echo "⚠️  НЕКОТОРЫЕ ИЗМЕНЕНИЯ НЕ ПРИМЕНЕНЫ"
    echo "=============================================="
    echo "Попробуйте запустить: bash scripts/sync_all_chat_changes_to_mac_studio.sh"
fi
echo ""

#!/bin/bash
# Обновление конфигурации для использования Tailscale IP вместо локального IP

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "🔐 ОБНОВЛЕНИЕ КОНФИГУРАЦИИ ДЛЯ TAILSCALE"
echo "=============================================="
echo ""

# Получаем Tailscale IP
TAILSCALE_IP=$(tailscale ip -4 2>/dev/null | head -1)
if [ -z "$TAILSCALE_IP" ]; then
    echo "⚠️  Tailscale не запущен или IP не получен"
    echo "   Запустите: tailscale up"
    exit 1
fi

echo "✅ Tailscale IP: $TAILSCALE_IP"
echo ""

# Локальный IP Mac Studio (для замены)
LOCAL_IP="192.168.1.43"

echo "📝 Обновляю конфигурацию..."

# Обновление в local_router.py
if [ -f "knowledge_os/app/local_router.py" ]; then
    sed -i.bak "s|http://${LOCAL_IP}:8010|http://${TAILSCALE_IP}:8010|g" knowledge_os/app/local_router.py
    sed -i.bak "s|http://${LOCAL_IP}:8011|http://${TAILSCALE_IP}:8011|g" knowledge_os/app/local_router.py
    sed -i.bak "s|http://${LOCAL_IP}:11434|http://${TAILSCALE_IP}:11434|g" knowledge_os/app/local_router.py
    echo "✅ Обновлен local_router.py"
fi

# Обновление в victoria_mcp_server.py
if [ -f "src/agents/bridge/victoria_mcp_server.py" ]; then
    sed -i.bak "s|http://${LOCAL_IP}:8010|http://${TAILSCALE_IP}:8010|g" src/agents/bridge/victoria_mcp_server.py
    echo "✅ Обновлен victoria_mcp_server.py"
fi

# Обновление в других файлах если есть
for file in $(grep -r "192.168.1.43" --include="*.py" --include="*.sh" --include="*.md" . 2>/dev/null | grep -v ".git" | grep -v ".bak" | cut -d: -f1 | sort -u); do
    if [[ "$file" != *".bak" ]]; then
        sed -i.bak "s|192.168.1.43|${TAILSCALE_IP}|g" "$file" 2>/dev/null || true
    fi
done

echo ""
echo "✅ Конфигурация обновлена для Tailscale IP: $TAILSCALE_IP"
echo ""
echo "📝 Теперь можно подключаться удаленно:"
echo "   Victoria: http://${TAILSCALE_IP}:8010"
echo "   Veronica: http://${TAILSCALE_IP}:8011"
echo "   Ollama: http://${TAILSCALE_IP}:11434"
echo ""
echo "💡 Для возврата к локальному IP:"
echo "   sed -i.bak 's|${TAILSCALE_IP}|192.168.1.43|g' knowledge_os/app/local_router.py"
echo ""

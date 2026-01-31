#!/bin/bash
# Удаленный запуск всех сервисов на Mac Studio
# Запускать на MacBook: bash scripts/remote_start_mac_studio.sh

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MAC_STUDIO_IP="192.168.1.64"
MAC_STUDIO_USER="bikos"
MAC_STUDIO_PATH="~/Documents/atra-web-ide"

echo "=============================================="
echo "🚀 УДАЛЕННЫЙ ЗАПУСК СЕРВИСОВ НА MAC STUDIO"
echo "=============================================="
echo ""

# Попытка подключения через разные методы
echo "🔍 Поиск способа подключения к Mac Studio..."

# Метод 1: SSH
if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} "echo 'OK'" 2>/dev/null; then
    echo "✅ SSH подключение работает"
    echo ""
    echo "🚀 Запуск скрипта на Mac Studio..."
    ssh ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} "cd ${MAC_STUDIO_PATH} && bash scripts/start_all_on_mac_studio.sh" 2>&1
    exit 0
fi

# Метод 2: Проверка доступности через HTTP
echo "⚠️  SSH недоступен, проверяю HTTP сервисы..."
if curl -s --connect-timeout 3 http://${MAC_STUDIO_IP}:8010/health >/dev/null 2>&1; then
    echo "✅ Victoria уже работает на Mac Studio"
    curl -s http://${MAC_STUDIO_IP}:8010/health
    echo ""
fi

if curl -s --connect-timeout 3 http://${MAC_STUDIO_IP}:8011/health >/dev/null 2>&1; then
    echo "✅ Veronica уже работает на Mac Studio"
    curl -s http://${MAC_STUDIO_IP}:8011/health
    echo ""
fi

# Метод 3: Через удаленный сервер (SSH туннель)
echo ""
echo "💡 Mac Studio недоступен напрямую"
echo ""
echo "📝 ИНСТРУКЦИЯ:"
echo "   На Mac Studio (где запущен Cursor) выполните:"
echo ""
echo "   cd ~/Documents/atra-web-ide"
echo "   bash scripts/start_all_on_mac_studio.sh"
echo ""
echo "   Или откройте терминал в Cursor и выполните команду выше"
echo ""

#!/bin/bash
# Быстрое подключение к Mac Studio
# Использование: bash scripts/mac-studio/quick_connect.sh

MAC_STUDIO_IP="192.168.1.64"
MAC_STUDIO_USER="bikos"

echo "🔌 Подключение к Mac Studio..."
echo "   IP: ${MAC_STUDIO_IP}"
echo "   Пользователь: ${MAC_STUDIO_USER}"
echo ""

# Проверка доступности
if ! ping -c 1 -W 2000 ${MAC_STUDIO_IP} > /dev/null 2>&1; then
    echo "❌ Mac Studio недоступен (${MAC_STUDIO_IP})"
    echo "   Проверьте, что Mac Studio включен и в той же сети"
    exit 1
fi

echo "✅ Mac Studio доступен"
echo ""

# Подключение
ssh ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}

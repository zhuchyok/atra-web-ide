#!/bin/bash
# Быстрое подключение к Mac Studio по SSH
# Использование: bash scripts/mac-studio/connect_ssh.sh

MAC_STUDIO_IP="192.168.1.64"
MAC_STUDIO_USER="bikos"

echo "🔌 Подключение к Mac Studio..."
echo "   IP: ${MAC_STUDIO_IP}"
echo "   Пользователь: ${MAC_STUDIO_USER}"
echo ""
echo "Введите пароль при запросе..."
echo ""

ssh ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}

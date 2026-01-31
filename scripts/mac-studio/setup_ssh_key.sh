#!/bin/bash
# Скрипт для настройки SSH ключа на Mac Studio
# Использование: bash scripts/mac-studio/setup_ssh_key.sh

set -e

MAC_STUDIO_IP="192.168.1.64"
MAC_STUDIO_USER="bikos"

echo "🔐 НАСТРОЙКА SSH КЛЮЧА ДЛЯ MAC STUDIO"
echo "====================================="
echo ""

# Проверка наличия SSH ключа
if [ ! -f ~/.ssh/id_ed25519.pub ]; then
    echo "❌ SSH ключ не найден. Создаю новый..."
    ssh-keygen -t ed25519 -C "macbook-to-macstudio" -f ~/.ssh/id_ed25519 -N ""
    echo "✅ SSH ключ создан"
fi

echo "📋 Публичный ключ:"
cat ~/.ssh/id_ed25519.pub
echo ""

echo "📤 Копирование ключа на Mac Studio..."
echo "   Вам нужно будет ввести пароль от Mac Studio"
echo ""

# Копируем ключ на Mac Studio
ssh-copy-id -o StrictHostKeyChecking=no ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}

if [ $? -eq 0 ]; then
    echo ""
    echo "✅ SSH ключ успешно скопирован!"
    echo ""
    echo "🧪 Проверка подключения..."
    ssh -o ConnectTimeout=5 ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} "echo '✅ Подключение успешно!' && hostname && whoami"
    
    if [ $? -eq 0 ]; then
        echo ""
        echo "✅✅✅ ВСЁ ГОТОВО! Теперь можно подключаться без пароля:"
        echo "   ssh ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}"
    fi
else
    echo ""
    echo "❌ Ошибка при копировании ключа"
    echo ""
    echo "Альтернативный способ:"
    echo "1. Скопируйте публичный ключ вручную:"
    echo "   cat ~/.ssh/id_ed25519.pub | pbcopy"
    echo ""
    echo "2. На Mac Studio выполните:"
    echo "   mkdir -p ~/.ssh"
    echo "   echo '<ваш_публичный_ключ>' >> ~/.ssh/authorized_keys"
    echo "   chmod 700 ~/.ssh"
    echo "   chmod 600 ~/.ssh/authorized_keys"
fi

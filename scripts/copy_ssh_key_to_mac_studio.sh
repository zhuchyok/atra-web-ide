#!/bin/bash
# Быстрое копирование SSH ключа с MacBook на Mac Studio

set -e

MAC_STUDIO_IP="${1:-192.168.1.64}"
MAC_STUDIO_USER="${2:-bikos}"
KEY_PATH="$HOME/.ssh/id_ed25519"
KEY_PUB_PATH="$HOME/.ssh/id_ed25519.pub"

echo "=============================================="
echo "📡 КОПИРОВАНИЕ SSH КЛЮЧА НА MAC STUDIO"
echo "=============================================="
echo ""
echo "Mac Studio: $MAC_STUDIO_USER@$MAC_STUDIO_IP"
echo ""

# Проверка наличия ключа
if [ ! -f "$KEY_PATH" ]; then
    echo "❌ Ключ не найден: $KEY_PATH"
    exit 1
fi

echo "✅ Ключ найден на MacBook"
echo ""

# Создаем директорию .ssh на Mac Studio если её нет
echo "📁 Создание директории .ssh на Mac Studio..."
ssh $MAC_STUDIO_USER@$MAC_STUDIO_IP "mkdir -p ~/.ssh && chmod 700 ~/.ssh" 2>/dev/null || {
    echo "⚠️  Не удалось подключиться. Убедитесь, что:"
    echo "   1. Mac Studio доступен по IP $MAC_STUDIO_IP"
    echo "   2. Пользователь $MAC_STUDIO_USER существует"
    echo "   3. SSH доступен (пароль или другой ключ)"
    echo ""
    echo "Альтернатива: скопируйте вручную:"
    echo "  scp $KEY_PATH $KEY_PUB_PATH $MAC_STUDIO_USER@$MAC_STUDIO_IP:~/.ssh/"
    exit 1
}

# Копируем ключи
echo "📋 Копирование ключей..."
scp $KEY_PATH $KEY_PUB_PATH $MAC_STUDIO_USER@$MAC_STUDIO_IP:~/.ssh/ || {
    echo "❌ Ошибка копирования. Попробуйте вручную:"
    echo "  scp $KEY_PATH $KEY_PUB_PATH $MAC_STUDIO_USER@$MAC_STUDIO_IP:~/.ssh/"
    exit 1
}

# Устанавливаем права на Mac Studio
echo "🔐 Установка прав доступа..."
ssh $MAC_STUDIO_USER@$MAC_STUDIO_IP "chmod 600 ~/.ssh/id_ed25519 && chmod 644 ~/.ssh/id_ed25519.pub"

echo ""
echo "✅ Ключ скопирован и настроен!"
echo ""
echo "🔍 Проверка подключения к серверу..."
ssh -i $KEY_PATH $MAC_STUDIO_USER@$MAC_STUDIO_IP "ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no root@185.177.216.15 'echo OK'" 2>/dev/null && {
    echo "✅ Подключение к серверу работает!"
} || {
    echo "⚠️  Подключение к серверу не работает. Проверьте:"
    echo "   1. Публичный ключ добавлен на сервер:"
    echo "      cat ~/.ssh/id_ed25519.pub | ssh root@185.177.216.15 'cat >> ~/.ssh/authorized_keys'"
}

echo ""
echo "=============================================="
echo "✅ ГОТОВО"
echo "=============================================="
echo ""
echo "Теперь на Mac Studio можно запустить туннели:"
echo "  bash scripts/start_mac_studio_tunnels.sh"
echo ""

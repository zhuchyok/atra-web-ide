#!/bin/bash
# Настройка SSH ключа на Mac Studio для туннелей
# Вариант А: Копирование ключа с MacBook
# Вариант Б: Создание нового ключа на Mac Studio

set -e

echo "=============================================="
echo "🔐 НАСТРОЙКА SSH КЛЮЧА ДЛЯ MAC STUDIO"
echo "=============================================="
echo ""

# Проверка наличия ключа на MacBook
MACBOOK_KEY="$HOME/.ssh/id_ed25519"
MACBOOK_KEY_PUB="$HOME/.ssh/id_ed25519.pub"

if [ -f "$MACBOOK_KEY" ]; then
    echo "✅ Найден ключ на MacBook: $MACBOOK_KEY"
    echo ""
    echo "📋 Публичный ключ:"
    cat "$MACBOOK_KEY_PUB"
    echo ""
    echo ""
    echo "Выберите вариант:"
    echo "  1. Скопировать ключ с MacBook на Mac Studio (SCP)"
    echo "  2. Создать новый ключ на Mac Studio"
    echo "  3. Показать инструкцию для ручного копирования"
    echo ""
    read -p "Ваш выбор (1-3): " choice
    
    case $choice in
        1)
            echo ""
            echo "📡 Копирование ключа на Mac Studio..."
            read -p "IP адрес Mac Studio [192.168.1.64]: " MAC_STUDIO_IP
            MAC_STUDIO_IP=${MAC_STUDIO_IP:-192.168.1.64}
            read -p "Пользователь на Mac Studio [bikos]: " MAC_STUDIO_USER
            MAC_STUDIO_USER=${MAC_STUDIO_USER:-bikos}
            
            echo ""
            echo "⚠️  ВАЖНО: Для копирования нужен пароль или другой способ доступа"
            echo "   Выполните на MacBook:"
            echo ""
            echo "   scp $MACBOOK_KEY $MACBOOK_KEY_PUB $MAC_STUDIO_USER@$MAC_STUDIO_IP:~/.ssh/"
            echo ""
            echo "   Затем на Mac Studio выполните:"
            echo "   chmod 600 ~/.ssh/id_ed25519"
            echo "   chmod 644 ~/.ssh/id_ed25519.pub"
            ;;
        2)
            echo ""
            echo "🔑 Создание нового ключа на Mac Studio..."
            echo ""
            echo "Выполните на Mac Studio:"
            echo ""
            echo "  ssh-keygen -t ed25519 -C 'mac-studio-tunnel' -f ~/.ssh/id_ed25519"
            echo "  chmod 600 ~/.ssh/id_ed25519"
            echo "  chmod 644 ~/.ssh/id_ed25519.pub"
            echo ""
            echo "Затем добавьте публичный ключ на сервер:"
            echo "  cat ~/.ssh/id_ed25519.pub | ssh root@185.177.216.15 'cat >> ~/.ssh/authorized_keys'"
            echo ""
            echo "И на MacBook (если нужен доступ с MacBook к Mac Studio):"
            echo "  cat ~/.ssh/id_ed25519.pub | ssh bikos@192.168.1.64 'cat >> ~/.ssh/authorized_keys'"
            ;;
        3)
            echo ""
            echo "📝 ИНСТРУКЦИЯ ДЛЯ РУЧНОГО КОПИРОВАНИЯ:"
            echo ""
            echo "1. На MacBook скопируйте ключ:"
            echo "   scp $MACBOOK_KEY $MACBOOK_KEY_PUB bikos@192.168.1.64:~/.ssh/"
            echo ""
            echo "2. На Mac Studio установите права:"
            echo "   chmod 600 ~/.ssh/id_ed25519"
            echo "   chmod 644 ~/.ssh/id_ed25519.pub"
            echo ""
            echo "3. Проверьте подключение:"
            echo "   ssh -i ~/.ssh/id_ed25519 root@185.177.216.15 'echo OK'"
            echo ""
            echo "4. Запустите туннели:"
            echo "   bash scripts/start_mac_studio_tunnels.sh"
            ;;
        *)
            echo "❌ Неверный выбор"
            exit 1
            ;;
    esac
else
    echo "⚠️  Ключ на MacBook не найден: $MACBOOK_KEY"
    echo ""
    echo "Создайте новый ключ на Mac Studio:"
    echo "  ssh-keygen -t ed25519 -C 'mac-studio-tunnel' -f ~/.ssh/id_ed25519"
fi

echo ""
echo "=============================================="
echo "✅ ИНСТРУКЦИЯ ГОТОВА"
echo "=============================================="

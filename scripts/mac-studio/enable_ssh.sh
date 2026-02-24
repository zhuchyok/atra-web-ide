#!/bin/bash
# Скрипт для включения SSH на Mac Studio
# Использование: bash scripts/mac-studio/enable_ssh.sh

set -e

echo "🔐 ВКЛЮЧЕНИЕ SSH НА MAC STUDIO"
echo "=============================="
echo ""

# Проверка, что скрипт запущен на macOS
if [[ "$OSTYPE" != "darwin"* ]]; then
    echo "❌ Этот скрипт предназначен только для macOS"
    exit 1
fi

# Проверка прав root
if [[ $EUID -ne 0 ]]; then
    echo "⚠️  Требуются права администратора (sudo)"
    echo "Запустите: sudo bash $0"
    exit 1
fi

echo "1️⃣ Проверка текущего статуса SSH..."
CURRENT_STATUS=$(systemsetup -getremotelogin | awk '{print $3}')
echo "   Текущий статус: $CURRENT_STATUS"

if [[ "$CURRENT_STATUS" == "On" ]]; then
    echo "✅ SSH уже включен!"
    echo ""
    echo "Проверка порта 22..."
    if lsof -i :22 > /dev/null 2>&1; then
        echo "✅ SSH слушает порт 22"
        lsof -i :22
    else
        echo "⚠️  SSH включен, но порт 22 не слушается"
        echo "Перезапускаю SSH сервис..."
        launchctl stop com.openssh.sshd 2>/dev/null || true
        launchctl start com.openssh.sshd
        sleep 2
        if lsof -i :22 > /dev/null 2>&1; then
            echo "✅ SSH теперь слушает порт 22"
        else
            echo "❌ Проблема с SSH сервисом"
        fi
    fi
else
    echo "2️⃣ Включение SSH..."
    systemsetup -setremotelogin on

    if [[ $? -eq 0 ]]; then
        echo "✅ SSH успешно включен!"

        echo ""
        echo "3️⃣ Проверка файрвола..."
        FIREWALL_STATE=$(/usr/libexec/ApplicationFirewall/socketfilterfw --getglobalstate 2>/dev/null | grep -i "enabled" || echo "disabled")

        if [[ "$FIREWALL_STATE" == *"enabled"* ]]; then
            echo "   Файрвол включен, разрешаю SSH..."
            /usr/libexec/ApplicationFirewall/socketfilterfw --add /usr/sbin/sshd 2>/dev/null || true
            /usr/libexec/ApplicationFirewall/socketfilterfw --unblockapp /usr/sbin/sshd 2>/dev/null || true
            echo "✅ SSH разрешён в файрволе"
        else
            echo "   Файрвол отключен, пропускаю"
        fi

        echo ""
        echo "4️⃣ Проверка порта 22..."
        sleep 2
        if lsof -i :22 > /dev/null 2>&1; then
            echo "✅ SSH слушает порт 22"
            echo ""
            echo "Активные соединения:"
            lsof -i :22
        else
            echo "⚠️  Порт 22 не слушается, перезапускаю SSH..."
            launchctl stop com.openssh.sshd 2>/dev/null || true
            launchctl start com.openssh.sshd
            sleep 3
            if lsof -i :22 > /dev/null 2>&1; then
                echo "✅ SSH теперь слушает порт 22"
            else
                echo "❌ Проблема с SSH сервисом, проверьте логи"
            fi
        fi
    else
        echo "❌ Ошибка при включении SSH"
        exit 1
    fi
fi

echo ""
echo "=============================="
echo "✅ ГОТОВО!"
echo ""
echo "📋 ИНФОРМАЦИЯ ДЛЯ ПОДКЛЮЧЕНИЯ:"
echo ""

# Получаем IP адреса
echo "IP адреса Mac Studio:"
ifconfig | grep "inet " | grep -v 127.0.0.1 | awk '{print "   " $2}' || echo "   Не удалось определить IP"

echo ""
echo "Имя пользователя: $(whoami)"
echo ""
echo "Команда для подключения:"
echo "   ssh $(whoami)@<IP-ADDRESS>"
echo ""
echo "Пример:"
ifconfig | grep "inet " | grep -v 127.0.0.1 | head -1 | awk '{print "   ssh $(whoami)@" $2}' || echo "   ssh $(whoami)@<IP-ADDRESS>"
echo ""
echo "📚 Документация: docs/mac-studio/SSH_ENABLE_MAC_STUDIO.md"
echo ""

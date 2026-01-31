#!/bin/bash
# SSH Reverse Tunnel для Frontend (порт 3002) через сервер 185.177.216.15

echo "=== Настройка SSH Reverse Tunnel для Frontend ==="
echo ""

# Проверяем существующие туннели
EXISTING_TUNNEL=$(ps aux | grep "ssh.*3002.*185.177.216.15" | grep -v grep)
if [ -n "$EXISTING_TUNNEL" ]; then
    echo "⚠️ Туннель для порта 3002 уже существует"
    echo "$EXISTING_TUNNEL"
    read -p "Остановить существующий туннель? (y/n) " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pkill -f "ssh.*3002.*185.177.216.15"
        sleep 2
    else
        echo "Используем существующий туннель"
        exit 0
    fi
fi

# Создаем SSH Reverse Tunnel
echo "🚀 Создаю SSH Reverse Tunnel для Frontend..."
echo "   Локальный порт: 3002"
echo "   Удаленный порт: 3002"
echo "   Сервер: 185.177.216.15"
echo ""

# Используем GatewayPorts для доступа из интернета
# Используем 0.0.0.0 для GatewayPorts (доступ из интернета)
ssh -fN \
    -o StrictHostKeyChecking=no \
    -o ServerAliveInterval=60 \
    -o ServerAliveCountMax=3 \
    -o ExitOnForwardFailure=yes \
    -R 0.0.0.0:3002:localhost:3002 \
    root@185.177.216.15

if [ $? -eq 0 ]; then
    echo "✅ SSH Reverse Tunnel создан!"
    echo ""
    echo "🌐 Frontend доступен через:"
    echo "   http://185.177.216.15:3002"
    echo ""
    echo "📝 Проверка:"
    echo "   curl http://185.177.216.15:3002"
else
    echo "❌ Ошибка создания SSH Reverse Tunnel"
    exit 1
fi

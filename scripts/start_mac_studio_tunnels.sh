#!/bin/bash
# Запуск SSH Reverse Tunnels с Mac Studio на сервер 185.177.216.15
# Для Victoria (8010), Veronica (8011), MCP (8012)

set -e

# Загрузка переменных окружения из .env
if [ -f ~/.env ]; then
    source ~/.env
fi

# Использование переменных окружения или значения по умолчанию
SERVER_IP="${SSH_REMOTE_HOST#*@}"
SERVER_USER="${SSH_REMOTE_HOST%@*}"
SERVER_IP="${SERVER_IP:-185.177.216.15}"
SERVER_USER="${SERVER_USER:-root}"
SSH_KEY="${SSH_KEY_PATH:-~/.ssh/id_ed25519}"

echo "🔗 Запуск SSH туннелей с Mac Studio на сервер..."

# Функция для создания туннеля
create_tunnel() {
    local name=$1
    local server_port=$2
    local local_port=$3

    echo "   📡 $name: порт $server_port → localhost:$local_port"

    # Убиваем старый туннель если есть
    pkill -f "ssh.*-R.*$server_port:localhost:$local_port" 2>/dev/null || true

    sleep 1

    # Создаем новый туннель с GatewayPorts (чтобы слушал на всех интерфейсах)
    ssh -f -N -i "$SSH_KEY" \
        -o StrictHostKeyChecking=no \
        -o ServerAliveInterval=60 \
        -o ServerAliveCountMax=3 \
        -o ExitOnForwardFailure=yes \
        -R 0.0.0.0:$server_port:localhost:$local_port \
        $SERVER_USER@$SERVER_IP 2>/dev/null

    if [ $? -eq 0 ]; then
        echo "      ✅ Туннель создан"
    else
        echo "      ⚠️  Не удалось создать туннель"
    fi
}

# Создаем туннели
create_tunnel "Victoria" 8010 8010
create_tunnel "Veronica" 8011 8011
create_tunnel "MCP" 8012 8012

echo ""
echo "✅ SSH туннели запущены!"
echo ""
echo "📊 Доступ через сервер:"
echo "   Victoria: http://$SERVER_IP:8010"
echo "   Veronica: http://$SERVER_IP:8011"
echo "   MCP: http://$SERVER_IP:8012"
echo ""

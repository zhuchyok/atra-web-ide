#!/bin/bash
# Настройка SSH Reverse Tunnel для Headscale через сервер 185.177.216.15
# Пока сервер доступен - используем его для удаленного доступа

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "🔗 НАСТРОЙКА SSH REVERSE TUNNEL ДЛЯ HEADSCALE"
echo "=============================================="
echo ""

SERVER_IP="185.177.216.15"
SERVER_USER="root"
LOCAL_PORT=8080  # Порт Headscale на Mac Studio

# Порты на сервере для проброса
SERVER_PORT_VIC=8010  # Victoria
SERVER_PORT_VER=8011  # Veronica
SERVER_PORT_MCP=8012  # MCP
SERVER_PORT_HEADSCALE=8080  # Headscale

echo "📋 Параметры:"
echo "   Сервер: $SERVER_USER@$SERVER_IP"
echo "   Headscale порт (Mac Studio): $LOCAL_PORT"
echo "   Headscale порт (сервер): $SERVER_PORT_HEADSCALE"
echo ""

# Проверка SSH доступа
echo "🔍 Проверка SSH доступа к серверу..."
if ! ssh -o ConnectTimeout=5 -o BatchMode=yes $SERVER_USER@$SERVER_IP "echo 'OK'" 2>/dev/null; then
    echo "⚠️  SSH доступ требует пароль или ключ"
    echo "   Убедитесь, что настроен SSH ключ или используйте sshpass"
    echo ""
    read -p "Введите пароль для сервера (или нажмите Enter для использования sshpass): " SERVER_PASS
    if [ -z "$SERVER_PASS" ]; then
        if command -v sshpass >/dev/null 2>&1; then
            echo "✅ Используем sshpass"
            SSH_CMD="sshpass -p '${SSH_REMOTE_PASS:-u44Ww9NmtQj,XG}' ssh"
        else
            echo "❌ sshpass не найден. Установите: brew install hudochenkov/sshpass/sshpass"
            exit 1
        fi
    else
        if command -v sshpass >/dev/null 2>&1; then
            SSH_CMD="sshpass -p '$SERVER_PASS' ssh"
        else
            echo "❌ sshpass не найден. Установите: brew install hudochenkov/sshpass/sshpass"
            exit 1
        fi
    fi
else
    echo "✅ SSH доступ настроен (ключ)"
    SSH_CMD="ssh"
fi

echo ""
echo "🔧 Настройка SSH туннелей..."

# Функция для создания туннеля
create_tunnel() {
    local name=$1
    local server_port=$2
    local local_port=$3

    echo "   📡 $name: порт $server_port → localhost:$local_port"

    # Убиваем старый туннель если есть
    $SSH_CMD -o StrictHostKeyChecking=no -o ServerAliveInterval=60 -o ServerAliveCountMax=3 \
        $SERVER_USER@$SERVER_IP "pkill -f 'ssh.*-R.*$server_port:localhost:$local_port' || true" 2>/dev/null || true

    sleep 1

    # Создаем новый туннель с GatewayPorts (чтобы слушал на всех интерфейсах)
    if [ "$SSH_CMD" = "ssh" ]; then
        ssh -f -N -o StrictHostKeyChecking=no \
            -o ServerAliveInterval=60 \
            -o ServerAliveCountMax=3 \
            -R *:$server_port:localhost:$local_port \
            $SERVER_USER@$SERVER_IP 2>/dev/null
    else
        eval "$SSH_CMD -f -N -o StrictHostKeyChecking=no \
            -o ServerAliveInterval=60 \
            -o ServerAliveCountMax=3 \
            -R *:$server_port:localhost:$local_port \
            $SERVER_USER@$SERVER_IP" 2>/dev/null
    fi

    if [ $? -eq 0 ]; then
        echo "      ✅ Туннель создан"
    else
        echo "      ⚠️  Не удалось создать туннель (возможно уже существует)"
    fi
}

# Создаем туннели
create_tunnel "Headscale" $SERVER_PORT_HEADSCALE $LOCAL_PORT
create_tunnel "Victoria" $SERVER_PORT_VIC 8010
create_tunnel "Veronica" $SERVER_PORT_VER 8011
create_tunnel "MCP" $SERVER_PORT_MCP 8012

echo ""
echo "✅ SSH туннели настроены!"
echo ""
echo "📊 Информация для подключения:"
echo "   Headscale: http://$SERVER_IP:$SERVER_PORT_HEADSCALE"
echo "   Victoria: http://$SERVER_IP:$SERVER_PORT_VIC"
echo "   Veronica: http://$SERVER_IP:$SERVER_PORT_VER"
echo "   MCP: http://$SERVER_IP:$SERVER_PORT_MCP"
echo ""
echo "🌐 На MacBook подключитесь к Headscale:"
echo "   tailscale up --login-server=http://$SERVER_IP:$SERVER_PORT_HEADSCALE"
echo ""
echo "⚠️  ВАЖНО:"
echo "   - Туннели работают пока активны SSH соединения"
echo "   - При перезагрузке Mac Studio туннели нужно пересоздать"
echo "   - Для автозапуска используйте launchd (см. ниже)"
echo ""

# Создание launchd service для автозапуска (автоматически)
echo ""
echo "🔧 Настройка автозапуска через launchd..."
LAUNCHD_TUNNEL="${HOME}/Library/LaunchAgents/com.atra.ssh-tunnel-headscale.plist"

cat > "$LAUNCHD_TUNNEL" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atra.ssh-tunnel-headscale</string>
    <key>ProgramArguments</key>
    <array>
        <string>/bin/bash</string>
        <string>${ROOT}/scripts/setup_ssh_tunnel_for_headscale.sh</string>
    </array>
    <key>WorkingDirectory</key>
    <string>${ROOT}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StartInterval</key>
    <integer>300</integer>
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/ssh-tunnel-headscale.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/ssh-tunnel-headscale.err.log</string>
</dict>
</plist>
EOF

launchctl unload "$LAUNCHD_TUNNEL" 2>/dev/null || true
launchctl load "$LAUNCHD_TUNNEL" 2>/dev/null || true

if launchctl list 2>/dev/null | grep -q "com.atra.ssh-tunnel-headscale"; then
    echo "✅ Автозапуск настроен через launchd"
    echo "   Логи: ${HOME}/Library/Logs/ssh-tunnel-headscale.log"
else
    echo "⚠️  Автозапуск не настроен (проверьте вручную)"
fi

echo ""
echo "=============================================="
echo "✅ НАСТРОЙКА ЗАВЕРШЕНА"
echo "=============================================="

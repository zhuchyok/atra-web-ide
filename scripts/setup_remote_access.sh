#!/bin/bash
# Настройка удаленного доступа к Mac Studio с MacBook
# Поддерживает несколько вариантов: Tailscale, Cloudflare Tunnel, SSH Reverse Tunnel

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "🌐 НАСТРОЙКА УДАЛЕННОГО ДОСТУПА К MAC STUDIO"
echo "=============================================="
echo ""
echo "Выберите метод удаленного доступа:"
echo "  1. Tailscale (VPN) - РЕКОМЕНДУЕТСЯ ✅"
echo "  2. Cloudflare Tunnel (бесплатно, через облако)"
echo "  3. SSH Reverse Tunnel (через промежуточный сервер)"
echo "  4. Ngrok (быстро, но временно)"
echo ""
read -p "Ваш выбор (1-4): " choice

case $choice in
    1)
        echo ""
        echo "=============================================="
        echo "🔐 НАСТРОЙКА TAILSCALE VPN"
        echo "=============================================="
        echo ""
        echo "Tailscale - лучший вариант для безопасного удаленного доступа"
        echo ""
        
        # Проверка установки Tailscale
        if ! command -v tailscale >/dev/null 2>&1; then
            echo "📥 Установка Tailscale..."
            if [[ "$OSTYPE" == "darwin"* ]]; then
                brew install tailscale
            else
                echo "⚠️  Установите Tailscale вручную: https://tailscale.com/download"
                exit 1
            fi
        fi
        
        echo "✅ Tailscale установлен"
        echo ""
        echo "📝 Инструкция:"
        echo "  1. На Mac Studio:"
        echo "     tailscale up"
        echo "     # Запишите IP адрес Mac Studio в Tailscale сети"
        echo ""
        echo "  2. На MacBook:"
        echo "     tailscale up"
        echo "     # Подключитесь к той же сети"
        echo ""
        echo "  3. Используйте Tailscale IP вместо 192.168.1.43"
        echo ""
        echo "  4. Обновите конфигурацию:"
        echo "     bash scripts/update_tailscale_config.sh"
        echo ""
        ;;
        
    2)
        echo ""
        echo "=============================================="
        echo "☁️ НАСТРОЙКА CLOUDFLARE TUNNEL"
        echo "=============================================="
        echo ""
        echo "Cloudflare Tunnel - бесплатный туннель через облако"
        echo ""
        
        # Проверка установки cloudflared
        if ! command -v cloudflared >/dev/null 2>&1; then
            echo "📥 Установка cloudflared..."
            if [[ "$OSTYPE" == "darwin"* ]]; then
                brew install cloudflare/cloudflare/cloudflared
            else
                echo "⚠️  Установите cloudflared: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation/"
                exit 1
            fi
        fi
        
        echo "✅ cloudflared установлен"
        echo ""
        echo "📝 Инструкция:"
        echo "  1. Зарегистрируйтесь на Cloudflare (бесплатно)"
        echo "  2. На Mac Studio выполните:"
        echo "     cloudflared tunnel login"
        echo "     cloudflared tunnel create atra-mac-studio"
        echo ""
        echo "  3. Создайте конфигурацию tunnel.yml (создан в $ROOT/tunnel.yml)"
        echo ""
        echo "  4. Запустите туннель:"
        echo "     cloudflared tunnel run atra-mac-studio"
        echo ""
        echo "  5. На MacBook используйте домены вместо IP"
        echo ""
        
        # Создание конфигурации tunnel.yml
        cat > "$ROOT/tunnel.yml" << 'TUNNEL_EOF'
tunnel: atra-mac-studio
credentials-file: /Users/zhuchyok/.cloudflared/<tunnel-id>.json

ingress:
  - hostname: victoria-atra.yourdomain.com
    service: http://localhost:8010
  - hostname: veronica-atra.yourdomain.com
    service: http://localhost:8011
  - hostname: mcp-atra.yourdomain.com
    service: http://localhost:8012
  - service: http_status:404
TUNNEL_EOF
        echo "     ✅ Создан файл tunnel.yml"
        echo ""
        echo "  6. Для автозапуска создан launchd service"
        echo ""
        
        # Создание launchd для автозапуска туннеля
        LAUNCHD_TUNNEL="${HOME}/Library/LaunchAgents/com.atra.cloudflare-tunnel.plist"
        cat > "$LAUNCHD_TUNNEL" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.atra.cloudflare-tunnel</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/cloudflared</string>
        <string>tunnel</string>
        <string>run</string>
        <string>atra-mac-studio</string>
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
    <key>StandardOutPath</key>
    <string>${HOME}/Library/Logs/cloudflare-tunnel.log</string>
    <key>StandardErrorPath</key>
    <string>${HOME}/Library/Logs/cloudflare-tunnel.err.log</string>
</dict>
</plist>
EOF
        echo "✅ Создан launchd service для автозапуска туннеля"
        echo "   Загрузите: launchctl load $LAUNCHD_TUNNEL"
        ;;
        
    3)
        echo ""
        echo "=============================================="
        echo "🔗 НАСТРОЙКА SSH REVERSE TUNNEL"
        echo "=============================================="
        echo ""
        echo "SSH Reverse Tunnel - через промежуточный сервер"
        echo ""
        read -p "IP адрес промежуточного сервера [185.177.216.15]: " SERVER_IP
        SERVER_IP=${SERVER_IP:-185.177.216.15}
        read -p "Пользователь на сервере [root]: " SERVER_USER
        SERVER_USER=${SERVER_USER:-root}
        read -p "Порт на сервере для Victoria [8010]: " SERVER_PORT_VIC
        SERVER_PORT_VIC=${SERVER_PORT_VIC:-8010}
        read -p "Порт на сервере для Veronica [8011]: " SERVER_PORT_VER
        SERVER_PORT_VER=${SERVER_PORT_VER:-8011}
        read -p "Порт на сервере для MCP [8012]: " SERVER_PORT_MCP
        SERVER_PORT_MCP=${SERVER_PORT_MCP:-8012}
        
        echo ""
        echo "📝 Создание SSH туннелей..."
        
        # Создание скрипта для SSH туннелей
        cat > "$ROOT/scripts/start_ssh_tunnels.sh" << EOF
#!/bin/bash
# SSH Reverse Tunnels для удаленного доступа к Mac Studio

SERVER_IP="$SERVER_IP"
SERVER_USER="$SERVER_USER"
SERVER_PORT_VIC="$SERVER_PORT_VIC"
SERVER_PORT_VER="$SERVER_PORT_VER"
SERVER_PORT_MCP="$SERVER_PORT_MCP"

echo "🔗 Запуск SSH туннелей..."

# Victoria (8010)
ssh -f -N -R $SERVER_PORT_VIC:localhost:8010 $SERVER_USER@$SERVER_IP

# Veronica (8011)
ssh -f -N -R $SERVER_PORT_VER:localhost:8011 $SERVER_USER@$SERVER_IP

# MCP (8012)
ssh -f -N -R $SERVER_PORT_MCP:localhost:8012 $SERVER_USER@$SERVER_IP

echo "✅ Туннели запущены"
echo "   Victoria: http://$SERVER_IP:$SERVER_PORT_VIC"
echo "   Veronica: http://$SERVER_IP:$SERVER_PORT_VER"
echo "   MCP: http://$SERVER_IP:$SERVER_PORT_MCP"
EOF
        chmod +x "$ROOT/scripts/start_ssh_tunnels.sh"
        echo "✅ Создан скрипт: scripts/start_ssh_tunnels.sh"
        echo ""
        echo "📝 Для автозапуска создайте launchd service или добавьте в cron"
        ;;
        
    4)
        echo ""
        echo "=============================================="
        echo "⚡ НАСТРОЙКА NGROK"
        echo "=============================================="
        echo ""
        echo "Ngrok - быстрый туннель для тестирования"
        echo ""
        
        # Проверка установки ngrok
        if ! command -v ngrok >/dev/null 2>&1; then
            echo "📥 Установка ngrok..."
            if [[ "$OSTYPE" == "darwin"* ]]; then
                brew install ngrok/ngrok/ngrok
            else
                echo "⚠️  Установите ngrok: https://ngrok.com/download"
                exit 1
            fi
        fi
        
        echo "✅ ngrok установлен"
        echo ""
        echo "📝 Инструкция:"
        echo "  1. Зарегистрируйтесь на ngrok.com (бесплатно)"
        echo "  2. Получите authtoken: ngrok config add-authtoken <token>"
        echo ""
        echo "  3. Запустите туннели:"
        echo "     ngrok http 8010 --domain=your-domain.ngrok-free.app  # Victoria"
        echo "     ngrok http 8011 --domain=your-domain.ngrok-free.app  # Veronica"
        echo "     ngrok http 8012 --domain=your-domain.ngrok-free.app  # MCP"
        echo ""
        echo "  ⚠️  ВАЖНО: Ngrok бесплатный план имеет ограничения"
        echo "     Для продакшена используйте Tailscale или Cloudflare Tunnel"
        ;;
        
    *)
        echo "❌ Неверный выбор"
        exit 1
        ;;
esac

echo ""
echo "=============================================="
echo "✅ НАСТРОЙКА ЗАВЕРШЕНА"
echo "=============================================="
echo ""
echo "📝 Следующие шаги:"
echo "  1. Следуйте инструкциям выше"
echo "  2. Обновите конфигурацию для использования удаленных адресов"
echo "  3. Протестируйте подключение"
echo ""
echo "💡 РЕКОМЕНДАЦИЯ: Используйте Tailscale для безопасного и простого удаленного доступа"
echo ""

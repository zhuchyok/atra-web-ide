#!/bin/bash
# Установка автозапуска SSH туннеля 185:3002 с постоянной проверкой
# Запуск: bash scripts/setup_tunnel_185_autostart.sh

set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

LAUNCH_AGENTS="${HOME}/Library/LaunchAgents"
TUNNEL_PLIST="com.atra.frontend-tunnel-185.plist"
WATCHDOG_PLIST="com.atra.frontend-tunnel-185-watchdog.plist"
WATCHDOG_SCRIPT="${ROOT}/scripts/tunnel_185_watchdog.sh"

echo "=== Автозапуск туннеля 185:3002 с постоянной проверкой ==="
echo ""

# 1. Туннель: копируем plist
mkdir -p "$LAUNCH_AGENTS"
cp "$ROOT/scripts/tunnel_185_frontend_launchd.plist" "$LAUNCH_AGENTS/$TUNNEL_PLIST"
echo "✅ Туннель: $LAUNCH_AGENTS/$TUNNEL_PLIST"

# 2. Watchdog: подставляем путь к скрипту и копируем plist
sed "s|SCRIPT_PATH_PLACEHOLDER|$WATCHDOG_SCRIPT|g" \
    "$ROOT/scripts/tunnel_185_watchdog_launchd.plist" \
    > "$LAUNCH_AGENTS/$WATCHDOG_PLIST"
chmod +x "$WATCHDOG_SCRIPT"
echo "✅ Watchdog: $LAUNCH_AGENTS/$WATCHDOG_PLIST (каждые 120 сек)"

# 3. Останавливаем старые процессы туннеля (чтобы управлял launchd)
pkill -f "ssh.*185.177.216.15.*3002" 2>/dev/null || true
sleep 2

# 4. Выгружаем старые launchd job'ы если есть
launchctl unload "$LAUNCH_AGENTS/$TUNNEL_PLIST" 2>/dev/null || true
launchctl unload "$LAUNCH_AGENTS/$WATCHDOG_PLIST" 2>/dev/null || true
sleep 1

# 5. Загружаем и запускаем
launchctl load "$LAUNCH_AGENTS/$TUNNEL_PLIST"
launchctl load "$LAUNCH_AGENTS/$WATCHDOG_PLIST"
echo "✅ LaunchAgents загружены"

# 6. Ждём и проверяем
echo ""
echo "⏳ Ожидание поднятия туннеля (10 сек)..."
sleep 10

if curl -sf --connect-timeout 5 "http://185.177.216.15:3002" >/dev/null 2>&1; then
    echo "✅ http://185.177.216.15:3002 — доступен"
else
    echo "⚠️  http://185.177.216.15:3002 — пока недоступен (туннель может подняться через минуту)"
    echo "   Логи туннеля: /tmp/atra-tunnel-185.log, /tmp/atra-tunnel-185.err.log"
fi

echo ""
echo "=== Готово ==="
echo ""
echo "📋 Установлено:"
echo "   • Туннель: автозапуск при входе в систему, KeepAlive (перезапуск при падении)"
echo "   • Watchdog: проверка каждые 2 минуты; при недоступности 185:3002 туннель перезапускается"
echo ""
echo "🌐 Frontend через 185: http://185.177.216.15:3002"
echo ""
echo "📝 Команды:"
echo "   Статус туннеля:    launchctl list | grep atra.frontend-tunnel"
echo "   Логи туннеля:      tail -f /tmp/atra-tunnel-185.log"
echo "   Логи watchdog:     tail -f /tmp/atra-tunnel-185-watchdog.log"
echo "   Отключить:         launchctl unload $LAUNCH_AGENTS/$TUNNEL_PLIST"
echo "                      launchctl unload $LAUNCH_AGENTS/$WATCHDOG_PLIST"
echo ""

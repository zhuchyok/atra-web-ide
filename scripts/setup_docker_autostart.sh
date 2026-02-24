#!/bin/bash
# Настройка автозапуска Docker Desktop при старте Mac
# Запускать один раз: bash scripts/setup_docker_autostart.sh

echo "=============================================="
echo "🐳 Настройка автозапуска Docker Desktop"
echo "=============================================="
echo ""

# 1. Проверка установки Docker Desktop
if ! command -v docker &> /dev/null; then
    echo "❌ Docker не установлен"
    echo "   Установите Docker Desktop: https://www.docker.com/products/docker-desktop"
    exit 1
fi

echo "✅ Docker установлен: $(docker --version)"
echo ""

# 2. Настройка автозапуска через Dock
echo "[1/3] Настройка автозапуска Docker Desktop..."

# Путь к Docker Desktop
DOCKER_APP="/Applications/Docker.app"

if [ -d "$DOCKER_APP" ]; then
    # Создаем симлинк в ~/Library/LaunchAgents для автозапуска
    # Но проще использовать встроенную настройку Docker Desktop

    echo "   ✅ Docker Desktop найден: $DOCKER_APP"
    echo ""
    echo "   📝 Для автозапуска Docker Desktop:"
    echo "   1. Откройте Docker Desktop"
    echo "   2. Перейдите в Settings → General"
    echo "   3. Включите 'Start Docker Desktop when you log in'"
    echo ""
    echo "   Или выполните команду:"
    echo "   defaults write com.docker.docker 'StartAtLogin' -bool true"

    # Пытаемся установить через defaults
    defaults write com.docker.docker 'StartAtLogin' -bool true 2>/dev/null && \
        echo "   ✅ Автозапуск настроен через defaults" || \
        echo "   ⚠️  Не удалось настроить автоматически, сделайте вручную в Docker Desktop"
else
    echo "   ⚠️  Docker Desktop не найден в /Applications"
    echo "   Установите Docker Desktop: https://www.docker.com/products/docker-desktop"
fi

echo ""

# 3. Проверка restart policy в docker-compose
echo "[2/3] Проверка restart policy в docker-compose.yml..."

COMPOSE_FILE="knowledge_os/docker-compose.yml"
if [ -f "$COMPOSE_FILE" ]; then
    if grep -q "restart: always" "$COMPOSE_FILE"; then
        echo "   ✅ Контейнеры настроены с 'restart: always'"
        echo "   Они будут автоматически запускаться при старте Docker"
    else
        echo "   ⚠️  'restart: always' не найден в docker-compose.yml"
    fi
else
    echo "   ⚠️  docker-compose.yml не найден"
fi

echo ""

# 4. Создание скрипта для автозапуска контейнеров
echo "[3/3] Создание скрипта автозапуска контейнеров..."

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
AUTOSTART_SCRIPT="$ROOT/scripts/auto_start_containers.sh"

cat > "$AUTOSTART_SCRIPT" << 'AUTOEOF'
#!/bin/bash
# Автозапуск контейнеров корпорации ATRA
# Запускается после старта Docker Desktop

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Ждем пока Docker запустится
MAX_WAIT=60
WAITED=0
while ! docker info >/dev/null 2>&1; do
    if [ $WAITED -ge $MAX_WAIT ]; then
        echo "⚠️ Docker не запустился за $MAX_WAIT секунд"
        exit 1
    fi
    sleep 2
    WAITED=$((WAITED + 2))
done

# Запускаем контейнеры
echo "🚀 Запуск контейнеров корпорации ATRA..."
docker-compose -f knowledge_os/docker-compose.yml up -d db
sleep 5
docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent veronica-agent knowledge_os_api knowledge_os_worker 2>/dev/null || true

# Проверяем Redis
if ! docker ps | grep -q atra-redis; then
    docker run -d --name atra-redis --network atra-network -p 6379:6379 redis:7-alpine 2>/dev/null || true
fi

echo "✅ Контейнеры запущены"
AUTOEOF

chmod +x "$AUTOSTART_SCRIPT"
echo "   ✅ Скрипт создан: $AUTOSTART_SCRIPT"

echo ""
echo "=============================================="
echo "✅ НАСТРОЙКА ЗАВЕРШЕНА"
echo "=============================================="
echo ""
echo "📋 Что нужно сделать:"
echo ""
echo "1. Настройте автозапуск Docker Desktop:"
echo "   - Откройте Docker Desktop"
echo "   - Settings → General → 'Start Docker Desktop when you log in'"
echo ""
echo "2. (Опционально) Настройте автозапуск контейнеров:"
echo "   - Создайте launchd service для $AUTOSTART_SCRIPT"
echo "   - Или запускайте вручную после старта Docker"
echo ""
echo "3. После перезагрузки Mac:"
echo "   - Docker Desktop запустится автоматически"
echo "   - Контейнеры запустятся автоматически (restart: always)"
echo ""
echo "💡 Альтернатива: Запускайте вручную:"
echo "   bash scripts/start_full_corporation.sh"
echo ""

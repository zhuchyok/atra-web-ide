#!/bin/bash
# Автоматическое выполнение на Mac Studio
# Этот скрипт пытается выполнить команды на Mac Studio через разные методы

set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

MAC_STUDIO_IP="192.168.1.64"
MAC_STUDIO_USER="bikos"
MAC_STUDIO_PATH="~/Documents/atra-web-ide"
REMOTE_SERVER="root@185.177.216.15"

echo "=============================================="
echo "🚀 АВТОМАТИЧЕСКИЙ ЗАПУСК НА MAC STUDIO"
echo "=============================================="
echo ""

# Метод 1: Прямой SSH к Mac Studio
echo "[1/3] Попытка прямого SSH подключения..."
if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} "echo 'OK'" 2>/dev/null; then
    echo "   ✅ SSH подключение работает"
    echo "   🚀 Выполнение скрипта на Mac Studio..."
    ssh ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} "cd ${MAC_STUDIO_PATH} && bash scripts/start_all_on_mac_studio.sh" 2>&1
    exit 0
fi
echo "   ❌ Прямой SSH недоступен"
echo ""

# Метод 2: Через удаленный сервер (если есть доступ к Mac Studio с сервера)
echo "[2/3] Попытка через удаленный сервер..."
if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no ${REMOTE_SERVER} "echo 'OK'" 2>/dev/null; then
    echo "   ✅ Удаленный сервер доступен"
    echo "   🔍 Проверка доступа к Mac Studio с сервера..."
    
    # Пробуем выполнить через сервер (если на сервере есть доступ к Mac Studio)
    if ssh ${REMOTE_SERVER} "ssh -o ConnectTimeout=3 -o StrictHostKeyChecking=no ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} 'echo OK' 2>/dev/null" 2>/dev/null; then
        echo "   ✅ Доступ к Mac Studio через сервер работает"
        echo "   🚀 Выполнение через сервер..."
        ssh ${REMOTE_SERVER} "ssh ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} 'cd ${MAC_STUDIO_PATH} && bash scripts/start_all_on_mac_studio.sh'" 2>&1
        exit 0
    else
        echo "   ⚠️  Сервер не имеет доступа к Mac Studio"
    fi
else
    echo "   ⚠️  Удаленный сервер недоступен"
fi
echo ""

# Метод 3: Создание файла-триггера для автоматического выполнения
echo "[3/3] Создание файла-триггера..."
TRIGGER_FILE="${ROOT}/.mac_studio_auto_start"
cat > "$TRIGGER_FILE" << 'EOF'
#!/bin/bash
# Автоматический запуск при обнаружении на Mac Studio
cd ~/Documents/atra-web-ide
if [ -f "scripts/start_all_on_mac_studio.sh" ]; then
    bash scripts/start_all_on_mac_studio.sh
    rm -f .mac_studio_auto_start
fi
EOF
chmod +x "$TRIGGER_FILE"
echo "   ✅ Файл-триггер создан: $TRIGGER_FILE"
echo ""

# Финальная инструкция
echo "=============================================="
echo "⚠️  АВТОМАТИЧЕСКОЕ ВЫПОЛНЕНИЕ НЕВОЗМОЖНО"
echo "=============================================="
echo ""
echo "📝 ВЫПОЛНИТЕ НА MAC STUDIO (в терминале Cursor):"
echo ""
echo "   cd ~/Documents/atra-web-ide"
echo "   bash scripts/start_all_on_mac_studio.sh"
echo ""
echo "   ИЛИ (если файл-триггер обнаружен):"
echo ""
echo "   bash .mac_studio_auto_start"
echo ""
echo "📋 Скрипт автоматически:"
echo "   ✅ Проверит Docker"
echo "   ✅ Создаст сеть"
echo "   ✅ Проверит MLX/Ollama"
echo "   ✅ Импортирует данные (если есть)"
echo "   ✅ Запустит все контейнеры"
echo "   ✅ Проверит доступность"
echo ""
echo "⏱️  Время выполнения: ~1-2 минуты"
echo ""

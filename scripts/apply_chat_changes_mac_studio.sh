#!/bin/bash
# Применение изменений чата на Mac Studio

MAC_STUDIO_USER="${MAC_STUDIO_USER:-bikos}"
MAC_STUDIO_IP="${MAC_STUDIO_IP:-192.168.1.64}"
MAC_STUDIO_PATH="${MAC_STUDIO_PATH:-~/Documents/atra-web-ide}"

echo "🔄 ПРИМЕНЕНИЕ ИЗМЕНЕНИЙ ЧАТА НА MAC STUDIO"
echo ""

# Проверка SSH
if ! ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} "echo 'OK'" 2>/dev/null; then
    echo "❌ Mac Studio недоступен (${MAC_STUDIO_IP})"
    echo "   Проверьте подключение или используйте VPN/туннель"
    exit 1
fi

echo "✅ Mac Studio доступен"

# Копирование файлов
echo ""
echo "📁 Копирование измененных файлов..."

rsync -avz --progress -e "ssh -o StrictHostKeyChecking=no" \
    frontend/src/stores/chat.js \
    ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/frontend/src/stores/

rsync -avz --progress -e "ssh -o StrictHostKeyChecking=no" \
    backend/app/routers/chat.py \
    ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/backend/app/routers/

rsync -avz --progress -e "ssh -o StrictHostKeyChecking=no" \
    backend/app/services/ollama.py \
    ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/backend/app/services/

rsync -avz --progress -e "ssh -o StrictHostKeyChecking=no" \
    backend/app/services/victoria.py \
    ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/backend/app/services/

rsync -avz --progress -e "ssh -o StrictHostKeyChecking=no" \
    docker-compose.yml \
    ${MAC_STUDIO_USER}@${MAC_STUDIO_IP}:${MAC_STUDIO_PATH}/

echo ""
echo "🔄 Пересборка и перезапуск на Mac Studio..."

ssh ${MAC_STUDIO_USER}@${MAC_STUDIO_IP} << 'REMOTE'
cd ~/Documents/atra-web-ide
echo "Пересборка backend..."
docker-compose build backend
echo "Перезапуск сервисов..."
docker-compose restart backend frontend
echo "✅ Готово!"
REMOTE

echo ""
echo "✅ ВСЕ ИЗМЕНЕНИЯ ПРИМЕНЕНЫ НА MAC STUDIO!"

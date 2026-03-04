#!/usr/bin/env bash
# Деплой сервиса orders-api (POST /api/orders) на VDS.
# Устраняет 404 при отправке формы заказа. После деплоя в NPM добавить Custom Location /api/orders → setki21-orders-api:3010.
# Запуск: ./scripts/deploy_setki21_orders_api_vds.sh

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SETKI21_ROOT="${SETKI21_ROOT:-/Users/bikos/Documents/dev/setki-21}"
VDS_HOST="${VDS_HOST:-root@45.10.43.248}"
REMOTE_APP="/home/atra/app"

echo "=== 1. Заливка orders-api на VDS ==="
ssh "$VDS_HOST" "mkdir -p ${REMOTE_APP}/setki21_orders_api"
rsync -az "${SETKI21_ROOT}/orders-api/" "${VDS_HOST}:${REMOTE_APP}/setki21_orders_api/"
# Переменные SMTP и ORDER_EMAIL из setki-21/.env (заявки на почту организации)
if [ -f "${SETKI21_ROOT}/.env" ]; then
  echo "Копирую .env (SMTP, ORDER_EMAIL) на VDS..."
  rsync -az "${SETKI21_ROOT}/.env" "${VDS_HOST}:${REMOTE_APP}/setki21_orders_api/.env"
fi

echo ""
echo "=== 2. Сборка образа и запуск setki21-orders-api ==="
ssh "$VDS_HOST" "cd ${REMOTE_APP}/setki21_orders_api && docker build -t setki21-orders-api:latest . && docker stop setki21-orders-api 2>/dev/null; docker rm setki21-orders-api 2>/dev/null; true"

# Запуск с .env (заявки приходят на ORDER_EMAIL из .env, по умолчанию info@setki21.ru)
# Подключение к atra-network нужно, чтобы NPM (atra-nginx-proxy) резолвил setki21-orders-api
if ssh "$VDS_HOST" "test -f ${REMOTE_APP}/setki21_orders_api/.env"; then
  ssh "$VDS_HOST" "cd ${REMOTE_APP}/setki21_orders_api && docker run -d --name setki21-orders-api --restart unless-stopped -p 3010:3010 --env-file .env setki21-orders-api:latest; docker network connect atra-network setki21-orders-api 2>/dev/null || true"
else
  ssh "$VDS_HOST" "docker run -d --name setki21-orders-api --restart unless-stopped -p 3010:3010 -e SMTP_HOST=smtp.timeweb.ru -e ORDER_EMAIL=info@setki21.ru setki21-orders-api:latest; docker network connect atra-network setki21-orders-api 2>/dev/null || true" || true
  echo "Внимание: .env не найден. Заявки не будут уходить на почту. Добавь на VDS ${REMOTE_APP}/setki21_orders_api/.env с SMTP_USER, SMTP_PASS, ORDER_EMAIL."
fi

# Образец конфига NPM с location /api/orders — скопирован для справки
rsync -az "${REPO_ROOT}/scripts/npm_proxy_setki21.conf" "${VDS_HOST}:${REMOTE_APP}/setki21_orders_api/npm_proxy_setki21.conf.example" 2>/dev/null || true

echo ""
echo "Готово. setki21-orders-api слушает порт 3010, заявки приходят на ORDER_EMAIL (info@setki21.ru)."
echo "Чтобы форма заказа не давала 404, в NPM для www.setki21.ru добавь Custom Location (выше /api):"
echo "  Path: /api/orders   Forward: 127.0.0.1:3010  (или IP хоста:3010, если NPM в Docker)."
echo "Пример конфига: ${REMOTE_APP}/setki21_orders_api/npm_proxy_setki21.conf.example"

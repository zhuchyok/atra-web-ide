#!/usr/bin/env bash
# Деплой сайта Сетки 21 (Nuxt) на VDS.
# Сборка из /Users/bikos/Documents/dev/setki-21, заливка в setki21_site/ на сервере.
# Запуск: ./scripts/deploy_setki21_site_vds.sh

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SETKI21_ROOT="${SETKI21_ROOT:-/Users/bikos/Documents/dev/setki-21}"
VDS_HOST="${VDS_HOST:-root@45.10.43.248}"
REMOTE_APP="/home/atra/app"

echo "=== 1. Сборка Nuxt (generate) ==="
cd "$SETKI21_ROOT"
# Для админки и калькулятора: API на том же домене, NPM проксирует /api → atra-kernel
export NUXT_PUBLIC_API_URL="${NUXT_PUBLIC_API_URL:-https://www.setki21.ru}"
npm run generate

echo ""
echo "=== 2. Заливка .output/public на VDS ==="
ssh "$VDS_HOST" "mkdir -p ${REMOTE_APP}/setki21_site"
rsync -az --delete "${SETKI21_ROOT}/.output/public/" "${VDS_HOST}:${REMOTE_APP}/setki21_site/"

echo ""
echo "=== 3. Конфиг nginx для SPA (index + try_files) ==="
ssh "$VDS_HOST" "mkdir -p ${REMOTE_APP}/setki21_nginx"
rsync -az "${REPO_ROOT}/setki21_nginx/" "${VDS_HOST}:${REMOTE_APP}/setki21_nginx/"

echo ""
echo "=== 4. Перезапуск setki21-site ==="
# Старый docker-compose на VDS падает с --force-recreate (ContainerConfig); делаем stop + rm + up
ssh "$VDS_HOST" "cd ${REMOTE_APP} && \
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then \
    docker compose stop setki21-site 2>/dev/null; docker compose rm -f setki21-site 2>/dev/null; docker compose up -d setki21-site; \
  else \
    docker-compose stop setki21-site 2>/dev/null; docker-compose rm -f setki21-site 2>/dev/null; docker-compose up -d setki21-site; \
  fi"

echo ""
echo "Готово. Проверь: https://www.setki21.ru"
echo "В NPM для www.setki21.ru должен быть Forward: setki21-site:80 и Custom Locations /api, /health → atra-kernel:8081."

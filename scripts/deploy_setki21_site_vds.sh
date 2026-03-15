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
echo "=== 5. Верификация: живой сайт = сборка на VDS ==="
if [ -n "${SKIP_SETKI21_VERIFY:-}" ]; then
  echo "Верификация пропущена. Проверь вручную: docs/runbooks/SETKI21_DEPLOY_VERIFY_FAIL.md"
else
  VDS_HASH="$(ssh "$VDS_HOST" "grep -o 'entry\\.[^\\\"]*\\.css' ${REMOTE_APP}/setki21_site/index.html | head -1" 2>/dev/null || true)"
  LIVE_HASH="$(
    bash -lc '
      for attempt in 1 2 3 4 5 6 7 8 9 10; do
        HASH="$(curl -sS --max-time 15 "https://www.setki21.ru/" | grep -o '\''entry\.[^\"]*\.css'\'' | head -1 || true)"
        if [ -n "$HASH" ]; then
          printf "%s" "$HASH"
          exit 0
        fi
        sleep 3
      done
    ' || true
  )"

  echo "VDS hash:  ${VDS_HASH:-<empty>}"
  echo "Live hash: ${LIVE_HASH:-<empty>}"

  if [ -z "$VDS_HASH" ] || [ -z "$LIVE_HASH" ] || [ "$VDS_HASH" != "$LIVE_HASH" ]; then
    echo "Верификация не прошла: живой сайт отдаёт другую сборку или недоступен."
    echo "Runbook: docs/runbooks/SETKI21_DEPLOY_VERIFY_FAIL.md"
    exit 1
  fi

  echo "Верификация OK: живой сайт отдаёт ту же сборку."
fi

echo ""
echo "Готово. Проверь: https://www.setki21.ru"
echo "В NPM для www.setki21.ru должен быть Forward: setki21-site:80."
echo "Если верификация упала, см. docs/runbooks/SETKI21_DEPLOY_VERIFY_FAIL.md"

#!/usr/bin/env bash
# Деплой moskit-api на VDS: синхронизация исходников setki-21, сборка образа, создание БД, запуск.
# Логин/пароль админки остаются как сейчас: admin@setki21.ru и пароль из .env.atra (миграция 004).
# Запуск: ./scripts/deploy_moskit_api_vds.sh

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SETKI21_ROOT="${SETKI21_ROOT:-/Users/bikos/Documents/dev/setki-21}"
VDS_HOST="${VDS_HOST:-root@45.10.43.248}"
REMOTE_APP="/home/atra/app"
REMOTE_SRC="${REMOTE_APP}/setki21_src"

echo "=== 1. Заливка исходников setki-21 на VDS ==="
ssh "$VDS_HOST" "mkdir -p ${REMOTE_SRC}"
rsync -az --delete \
  --exclude 'node_modules' \
  --exclude '.nuxt' \
  --exclude '.output' \
  --exclude 'moskit-api/target' \
  --exclude 'moskit-core/target' \
  "${SETKI21_ROOT}/" "${VDS_HOST}:${REMOTE_SRC}/"

echo ""
echo "=== 2. Заливка docker-compose и скриптов ==="
ssh "$VDS_HOST" "mkdir -p ${REMOTE_APP}/scripts"
rsync -az "${REPO_ROOT}/docker-compose.vds.yml" "${VDS_HOST}:${REMOTE_APP}/docker-compose.yml"
rsync -az "${REPO_ROOT}/scripts/create_moskit_db_vds.sh" "${VDS_HOST}:${REMOTE_APP}/scripts/"
ssh "$VDS_HOST" "chmod +x ${REMOTE_APP}/scripts/create_moskit_db_vds.sh"

# Найти контейнер postgres (может иметь префикс в Docker Compose V1)
CONTAINER=$(ssh "$VDS_HOST" "docker ps --filter name=postgres --format '{{.Names}}' | grep postgres | head -n 1")
if [ -z "$CONTAINER" ]; then
  echo "Error: Postgres container not found"
  exit 1
fi

echo ""
echo "=== 3. Создание БД moskit (если ещё нет) ==="
ssh "$VDS_HOST" "cd ${REMOTE_APP} && ([ -f .env ] && set a && . ./.env; set +a); POSTGRES_CONTAINER=${CONTAINER} bash scripts/create_moskit_db_vds.sh"

echo ""
echo "=== 4. Сборка образа moskit-api на VDS ==="
# CACHEBUST чтобы не подхватить слой с заглушкой main(); без этого образ может содержать пустой бинарник.
CACHEBUST=$(date +%s)
ssh "$VDS_HOST" "cd ${REMOTE_SRC} && docker build --build-arg CACHEBUST=${CACHEBUST} -f moskit-api/Dockerfile -t moskit-api:latest ."

echo ""
echo "=== 5. Запуск moskit-api ==="
# Старый docker-compose на VDS падает с --force-recreate (ContainerConfig); делаем stop + rm + up
ssh "$VDS_HOST" "cd ${REMOTE_APP} && \
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then \
    docker compose stop moskit-api 2>/dev/null; docker compose rm -f moskit-api 2>/dev/null; docker compose up -d moskit-api; \
  else \
    docker-compose stop moskit-api 2>/dev/null; docker-compose rm -f moskit-api 2>/dev/null; docker-compose up -d moskit-api; \
  fi"

echo ""
echo "Готово. API Сетки 21: moskit-api:8080."
echo "Вход в админку: admin@setki21.ru и пароль из .env.atra (миграция 004)."
echo ""
echo "NPM: обнови proxy www.setki21.ru — /api и /health должны указывать на moskit-api:8080."
echo "Конфиг-образец: scripts/npm_proxy_setki21.conf (скопировать в NPM proxy_host/1.conf и перезагрузить nginx)."

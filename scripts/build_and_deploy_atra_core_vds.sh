#!/usr/bin/env bash
# Сборка atra-core на VDS (native amd64) и перезапуск контейнера.
# Запуск из корня репозитория: ./scripts/build_and_deploy_atra_core_vds.sh
# Или полный путь: /Users/bikos/Documents/atra-web-ide/scripts/build_and_deploy_atra_core_vds.sh

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VDS_HOST="${VDS_HOST:-root@45.10.43.248}"
RUST_DIR="rust_core"
REMOTE_APP="/home/atra/app"

echo "=== 1. Синхронизация rust_core на VDS ==="
rsync -az --exclude target "${REPO_ROOT}/${RUST_DIR}/" "${VDS_HOST}:${REMOTE_APP}/${RUST_DIR}/"

echo ""
echo "=== 2. Сборка образа на VDS (native amd64) ==="
ssh "${VDS_HOST}" "cd ${REMOTE_APP}/${RUST_DIR} && docker build -t atra-core:latest ."

echo ""
echo "=== 3. Перезапуск контейнера atra-kernel ==="
ssh "${VDS_HOST}" "docker rm -f atra-kernel 2>/dev/null; cd ${REMOTE_APP} && /usr/bin/docker-compose up -d atra-core"

echo ""
echo "=== 4. Проверка (ожидание 3 сек) ==="
sleep 3
if ssh "${VDS_HOST}" "curl -sf http://127.0.0.1:8081/health"; then
  echo ""
  echo "OK: atra-core отвечает на /health"
else
  echo "Проверка: curl не удался, смотри логи: ssh ${VDS_HOST} 'docker logs atra-kernel'"
fi

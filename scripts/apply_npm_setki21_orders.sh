#!/usr/bin/env bash
# Применяет конфиг NPM с location /api/orders для www.setki21.ru.
# Запуск с хоста: ./scripts/apply_npm_setki21_orders.sh
# Или на VDS: скрипт копируется и выполняется на сервере.

set -e

REPO_ROOT="$(cd "$(dirname "$0")/.." 2>/dev/null && pwd)"
VDS_HOST="${VDS_HOST:-root@45.10.43.248}"
REMOTE_APP="/home/atra/app"

# Копируем актуальный конфиг на VDS
if [ -n "$REPO_ROOT" ] && [ -f "${REPO_ROOT}/scripts/npm_proxy_setki21.conf" ]; then
  echo "Копирую npm_proxy_setki21.conf на VDS..."
  rsync -az "${REPO_ROOT}/scripts/npm_proxy_setki21.conf" "${VDS_HOST}:${REMOTE_APP}/npm_proxy_setki21.conf"
fi

echo "Применяю конфиг NPM на VDS..."
ssh "$VDS_HOST" 'bash -s' << 'REMOTE'
set -e
REMOTE_APP="${REMOTE_APP:-/home/atra/app}"
CONF_SRC="${REMOTE_APP}/npm_proxy_setki21.conf"

# NPM data (путь на VDS: nginx_proxy/data/nginx/proxy_host)
for dir in "${REMOTE_APP}/nginx_proxy/data/nginx/proxy_host" "${REMOTE_APP}/data/nginx/proxy_host" "${REMOTE_APP}/nginx/proxy_host" "/data/nginx/proxy_host"; do
  if [ -d "$dir" ]; then
    for f in "$dir"/*.conf; do
      [ -f "$f" ] || continue
      if grep -q "www.setki21.ru\|setki21" "$f" 2>/dev/null; then
        echo "Найден конфиг setki21: $f"
        cp -a "$f" "${f}.bak"
        cp "$CONF_SRC" "$f"
        echo "Заменён на конфиг с /api/orders. Бэкап: ${f}.bak"
        break 2
      fi
    done
  fi
done

# Перезагрузка nginx в контейнере NPM (если есть)
for c in $(docker ps -q --filter "name=npm" --filter "name=nginx" 2>/dev/null); do
  if docker exec "$c" nginx -t 2>/dev/null; then
    docker exec "$c" nginx -s reload 2>/dev/null && echo "Nginx перезагружен в контейнере $c"
  fi
done

# Или системный nginx
if command -v nginx >/dev/null 2>&1 && nginx -t 2>/dev/null; then
  nginx -s reload 2>/dev/null && echo "Системный nginx перезагружен"
fi
REMOTE

echo "Готово. Проверь: https://www.setki21.ru — отправка формы заказа не должна давать 404."

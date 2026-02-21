#!/usr/bin/env bash
# Singularity 15.0: установка Open WebUI «с нуля» — создаётся админ, затем бутстрап (системный промпт + файл для инструмента).
# ВНИМАНИЕ: удаляет данные Open WebUI (чаты, пользователи). Для чистого первого запуска или сброса.
# Запуск: ./scripts/openwebui_fresh_install_singularity_15.sh

set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== Open WebUI: установка с нуля (Singularity 15.0) ==="
echo "Будет удалён volume open-webui-data. Продолжить? (y/N)"
read -r ans
if [ "$ans" != "y" ] && [ "$ans" != "Y" ]; then
  echo "Отменено."
  exit 0
fi

export OPENWEBUI_ADMIN_EMAIL="${OPENWEBUI_ADMIN_EMAIL:-admin@atra.local}"
export OPENWEBUI_ADMIN_PASSWORD="${OPENWEBUI_ADMIN_PASSWORD:-atra-admin-2026}"

echo "Останавливаю open-webui..."
docker compose -f knowledge_os/docker-compose.yml stop open-webui 2>/dev/null || true
echo "Удаляю volume open-webui-data..."
docker volume rm open-webui-data 2>/dev/null || true
echo "Запускаю open-webui (создастся админ: $OPENWEBUI_ADMIN_EMAIL)..."
docker compose -f knowledge_os/docker-compose.yml up -d open-webui
echo "Жду 25 с, пока Open WebUI поднимется и создаст админа..."
sleep 25
echo "Запускаю бутстрап (логин + генерация файла)..."
python3 scripts/openwebui_bootstrap_singularity_15.py
echo ""
echo "Готово. Войдите в http://localhost:3005 с логином $OPENWEBUI_ADMIN_EMAIL и паролем из OPENWEBUI_ADMIN_PASSWORD."
echo "Системный промпт и инструкция по инструменту: configs/openwebui_singularity_15_oneload/SYSTEM_PROMPT_AND_TOOL.txt"

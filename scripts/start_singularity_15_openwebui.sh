#!/usr/bin/env bash
# Singularity 15.0: поднять Victoria + Open WebUI (и опционально бэкенд) для сценария Open WebUI → ask_victoria → Victoria.
# Запуск из корня репозитория: ./scripts/start_singularity_15_openwebui.sh [--with-backend]

set -e
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

WITH_BACKEND=false
for arg in "$@"; do
  case "$arg" in
    --with-backend) WITH_BACKEND=true ;;
  esac
done

echo "=== Singularity 15.0: запуск Victoria + Open WebUI ==="
echo "Репозиторий: $REPO_ROOT"
echo ""

echo "1. Сеть atra-network..."
docker network create atra-network 2>/dev/null || true

echo "2. Запуск Knowledge OS: db, redis, victoria-agent, open-webui..."
docker compose -f knowledge_os/docker-compose.yml up -d db redis victoria-agent open-webui

if "$WITH_BACKEND"; then
  echo "3. Запуск бэкенда atra-web-ide..."
  docker compose up -d backend
else
  echo "3. Бэкенд не запускаем (для метрик и прокси добавьте: $0 --with-backend)"
fi

echo ""
echo "=== Дальнейшие шаги ==="
echo "  • Open WebUI:    http://localhost:3005"
echo "  • Rust Gateway:  http://localhost:8081/health"
echo "  • Victoria:      http://localhost:8010/health (с хоста)"
echo ""
echo "  В Open WebUI:"
echo "  1. System Prompt модели → вставить текст из docs/SINGULARITY_15_GOLDEN_PERSONA.md"
echo "  2. Workspace → Tools → Import Tools → выбрать configs/openwebui_ask_victoria_tool.py"
echo "     (в контейнере файл смонтирован как /workspace/configs/openwebui_ask_victoria_tool.py)"
echo "  3. Valves инструмента: VICTORIA_URL=http://localhost:8081/v1/chat/completions, USE_BACKEND_PROXY=false"
echo "     (если поднят бэкенд и нужен прокси: VICTORIA_URL=http://atra-web-ide-backend:8080, USE_BACKEND_PROXY=true)"
echo "  4. Тест: запрос «Проверь бэкенд» или «Кратко ответь: какой у тебя статус?»"
echo ""
echo "Настройка Open WebUI одной командой (системный промпт + инструкция):"
echo "  python3 scripts/openwebui_bootstrap_singularity_15.py"
echo "  (файл для копирования: configs/openwebui_singularity_15_oneload/SYSTEM_PROMPT_AND_TOOL.txt)"
echo "Установка с нуля (создаёт админа, затем бутстрап): ./scripts/openwebui_fresh_install_singularity_15.sh"
echo ""
echo "Подробно: docs/OPENWEBUI_SINGULARITY_15_RUNBOOK.md"
echo "Проверка: ./scripts/verify_singularity_15_openwebui.sh"

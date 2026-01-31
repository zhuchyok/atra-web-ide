#!/bin/bash
# Одна точка входа: проверить агентов. При сбое — вывести команды для ручного запуска.
# Запускать из корня репо: bash scripts/migration/continue_agents.sh

set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"

echo "=============================================="
echo "Victoria / Veronica — проверка"
echo "=============================================="
echo ""

if bash "$ROOT/scripts/migration/verify_agents.sh"; then
  echo ""
  echo "Всё в порядке. Дальше ничего делать не нужно."
  exit 0
fi

echo ""
echo "----------------------------------------------"
echo "Проверка не прошла. Сделай вручную:"
echo ""
echo "  1. Docker Desktop запущен?"
echo "  2. В корне репо выполни:"
echo ""
echo "     docker-compose -f knowledge_os/docker-compose.yml up -d db"
echo "     # подожди 1–2 мин"
echo "     docker-compose -f knowledge_os/docker-compose.yml up -d victoria-agent veronica-agent"
echo "     # подожди ~30 с"
echo "     bash scripts/migration/verify_agents.sh"
echo ""
echo "  3. Логи: docker logs victoria-agent  docker logs veronica-agent"
echo "  4. MLX/Ollama на localhost:11434?"
echo "----------------------------------------------"
exit 1

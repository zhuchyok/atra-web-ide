#!/usr/bin/env bash
# Прогон куратора: тестирует Victoria по ВСЕМ эталонам (все 19+ файлов).
# Использование:
#   ./scripts/run_curator_and_compare.sh              # полный прогон
#   ./scripts/run_curator_and_compare.sh --quick       # быстрый (60 сек на запрос)
#   ./scripts/run_curator_and_compare.sh --limit 5     # только 5 эталонов
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

VICTORIA_URL="${VICTORIA_URL:-http://localhost:8010}"
LIMIT=""
QUICK=""
for arg in "$@"; do
  case "$arg" in
    --quick)   QUICK="--quick" ;;
    --limit=*) LIMIT="--limit ${arg#*=}" ;;
  esac
done

echo "=== Проверка Victoria ($VICTORIA_URL) ==="
if curl -sf --connect-timeout 5 "${VICTORIA_URL}/health" >/dev/null 2>&1; then
  echo "OK"
else
  echo "Victoria недоступна. Попробуйте: docker compose -f knowledge_os/docker-compose.agents.yml up -d victoria-agent"
  exit 1
fi

echo ""
echo "=== Прогон куратора по всем эталонам ==="
python3 scripts/curator_full_evaluation.py $QUICK $LIMIT
echo ""
echo "Готово."

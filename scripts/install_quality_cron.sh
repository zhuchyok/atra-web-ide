#!/bin/bash
# Устанавливает cron для ежедневного запуска пайплайна качества RAG.
# Запуск: из корня репозитория: ./scripts/install_quality_cron.sh

set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
SETUP_FAIL=0

CRON_MARKER="atra-web-ide quality pipeline"
CRON_LINE="0 3 * * * (cd ${REPO_ROOT} && mkdir -p logs && ./scripts/run_quality_pipeline.sh >> logs/quality_pipeline.log 2>&1) # ${CRON_MARKER}"

echo "Проект: ${REPO_ROOT}"
echo "Строка cron: ${CRON_LINE}"
mkdir -p logs
echo "Каталог logs/ создан."

# Удаляем старую запись с тем же маркером и добавляем новую
if (crontab -l 2>/dev/null | grep -v "${CRON_MARKER}" | grep -v "^#.*quality_pipeline" ; echo "${CRON_LINE}") | crontab - 2>/dev/null; then
  echo "Cron установлен: ежедневно в 03:00."
else
  echo "❌ Не удалось изменить crontab. Добавьте вручную (crontab -e):"
  echo "${CRON_LINE}"
  SETUP_FAIL=1
fi

if [ "$SETUP_FAIL" -eq 0 ]; then
  if crontab -l 2>/dev/null | grep -q "${CRON_MARKER}"; then
    echo "✅ Cron marker подтверждён: ${CRON_MARKER}"
    crontab -l | grep -E "quality|${CRON_MARKER}" || true
  else
    echo "❌ Cron marker не найден после установки"
    SETUP_FAIL=1
  fi
fi

exit "$SETUP_FAIL"

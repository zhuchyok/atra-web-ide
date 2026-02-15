#!/usr/bin/env bash
# Куратор при деплое: быстрый прогон + сравнение с эталонами.
# Использование: после деплоя (docker-compose up или выкат) выполнить один раз:
#   ./scripts/run_curator_post_deploy.sh
# Таймаут среды: не менее 10 мин (CURATOR_RUNBOOK §1, §1.5).
# См. docs/CURATOR_RUNBOOK.md «Куратор при деплое».
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
exec ./scripts/run_curator_and_compare.sh

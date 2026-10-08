#!/bin/bash
# Ночная консилиум-битва с catch-up guard (v147.1):
# launchd календарь иногда пропускает срабатывание — этот guard делает
# пропущенный ночной прогон безопасным: свежая битва (<20ч) → выход.
set -u
ROOT="/Users/bikos/Documents/atra-web-ide"
RESULTS_DIR="$ROOT/configs/evals/results"
LATEST=$(ls -1t "$RESULTS_DIR"/battle_*.json 2>/dev/null | head -1)

if [[ -n "$LATEST" ]]; then
  AGE_H=$(( ($(date +%s) - $(stat -f %m "$LATEST")) / 3600 ))
  if [[ "$AGE_H" -lt 20 ]]; then
    echo "[nightly-battle] свежая битва есть (${AGE_H}ч) — пропуск"
    exit 0
  fi
fi

# [v149.37] Битва конкурирует с экспертами за слоты qwen38 (ночь 07.10: 36 ошибок
# при живом бэклоге). При очереди >20 задач — сдвиг не нужен: бэклог важнее.
PENDING=$(docker exec knowledge_postgres psql -U admin -d knowledge_os -t -c "SELECT count(*) FROM tasks WHERE status='pending';" 2>/dev/null | tr -d ' ')
if [ "${PENDING:-0}" -gt 20 ]; then
  echo "[nightly-battle] очередь велика (${PENDING} pending) — перенос битвы, попробует завтра"
  exit 0
fi

cd "$ROOT" || exit 1
exec /opt/homebrew/bin/python3 scripts/consilium_ab.py

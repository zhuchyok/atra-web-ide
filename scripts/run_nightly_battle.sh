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

cd "$ROOT" || exit 1
exec /opt/homebrew/bin/python3 scripts/consilium_ab.py

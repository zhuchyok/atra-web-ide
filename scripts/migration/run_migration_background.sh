#!/bin/bash
# Запуск миграции в фоне. Лог: ~/migration/migration.log
set -e
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
mkdir -p ~/migration
LOG=~/migration/migration.log
echo "Запуск миграции в фоне. Лог: $LOG"
nohup python3 scripts/migration/corporation_full_migration.py >> "$LOG" 2>&1 &
echo "PID: $!"
echo "Следить: tail -f $LOG"

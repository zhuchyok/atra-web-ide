#!/usr/bin/env bash
set -euo pipefail

# Restores services paused during "distillation isolation mode".
# Safe to run multiple times.

SERVICES=(
  expert-worker-anna
  knowledge_os-expert-worker-light-1
  veronica-agent
  knowledge_rest
  performance-watchdog
  knowledge_evolution
  board-scheduler
  open-webui
  knowledge_os_worker
  knowledge_os_orchestrator
  victoria-visual-search
  knowledge_nightly
  corporation-dashboard
  quality-service
)

echo "[restore_full_power] Starting paused services..."
for svc in "${SERVICES[@]}"; do
  if docker ps -a --format '{{.Names}}' | grep -Fxq "$svc"; then
    if docker start "$svc" >/dev/null 2>&1; then
      echo "  - started: $svc"
    else
      echo "  - skipped (already running or failed): $svc"
    fi
  else
    echo "  - not found: $svc"
  fi
done

echo "[restore_full_power] Done."
echo "[restore_full_power] Current summary:"
docker ps --format 'table {{.Names}}\t{{.Status}}'

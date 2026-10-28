#!/usr/bin/env bash
# docker_task_watchdog.sh
# Runs task management scripts inside the Docker worker container.

set -euo pipefail
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

log() { echo "[$(date '+%H:%M:%S')] [TASK-WATCHDOG] $*"; }

if ! command -v docker >/dev/null 2>&1; then
    log "docker binary not found in PATH, skipping cycle"
    exit 0
fi

if ! docker ps --format '{{.Names}}' | rg -x 'knowledge_os_worker' >/dev/null 2>&1; then
    log "container knowledge_os_worker is not running, skipping cycle"
    exit 0
fi

log "Running Stuck Tasks Watchdog..."
docker exec knowledge_os_worker python3 /app/knowledge_os/scripts/reset_stuck_tasks.py || \
    log "reset_stuck_tasks.py returned non-zero (continuing)"

log "Running Failed Tasks Analyzer..."
docker exec knowledge_os_worker python3 /app/knowledge_os/scripts/failed_tasks_analyzer.py || \
    log "failed_tasks_analyzer.py returned non-zero (continuing)"

log "Task management cycle complete."

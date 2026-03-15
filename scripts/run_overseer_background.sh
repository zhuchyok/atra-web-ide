#!/bin/bash
# [SINGULARITY 21.19] Autonomous Overseer Wrapper
# Runs the overseer cycle and logs results.

ROOT_DIR="/Users/bikos/Documents/atra-web-ide"
LOG_FILE="$ROOT_DIR/docs/curator_reports/overseer_background.log"

cd "$ROOT_DIR"
echo "[$(date)] 🕵️ Starting background Overseer cycle..." >> "$LOG_FILE"

source knowledge_os/.venv/bin/activate
python3 knowledge_os/app/autonomous_overseer.py >> "$LOG_FILE" 2>&1

echo "[$(date)] ✅ Cycle finished." >> "$LOG_FILE"
echo "-----------------------------------" >> "$LOG_FILE"

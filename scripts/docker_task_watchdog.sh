#!/usr/bin/env bash
# docker_task_watchdog.sh
# Runs task management scripts inside the Docker worker container.

echo "🔍 Running Stuck Tasks Watchdog..."
docker exec knowledge_os_worker python3 /app/knowledge_os/scripts/reset_stuck_tasks.py

echo "🔍 Running Failed Tasks Analyzer..."
docker exec knowledge_os_worker python3 /app/knowledge_os/scripts/failed_tasks_analyzer.py

echo "✅ Task management cycle complete."

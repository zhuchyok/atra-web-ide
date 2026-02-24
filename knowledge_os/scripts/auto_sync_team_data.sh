#!/bin/bash
# Автоматическая синхронизация данных команды
# Можно добавить в cron для автоматической синхронизации

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

# Загрузка переменных окружения если есть
if [ -f ".env.team_sync" ]; then
    source .env.team_sync
fi

# Выполнение синхронизации
echo "🔄 Автоматическая синхронизация данных команды..."
python3 scripts/sync_team_data.py sync

echo "✅ Синхронизация завершена"

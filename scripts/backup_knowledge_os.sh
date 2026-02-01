#!/usr/bin/env bash
# Бэкап БД Knowledge OS (работает на Mac и Linux, с Docker или локально)
# Рекомендации экспертов: регулярный бэкап для восстановления после инцидентов
# Использование: ./scripts/backup_knowledge_os.sh
# Cron: 0 2 * * * cd /path/to/atra-web-ide && ./scripts/backup_knowledge_os.sh
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# BACKUP_DIR: Mac — в проекте, Linux/сервер — ~/Documents/dev/atra/backups или /root/...
if [ -d "$HOME/Documents/dev/atra/backups" ]; then
  BACKUP_DIR="$HOME/Documents/dev/atra/backups"
elif [ -d "/root/knowledge_os/backups" ]; then
  BACKUP_DIR="/root/knowledge_os/backups"
else
  BACKUP_DIR="$ROOT/backups"
fi

mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
GZ_FILE="$BACKUP_DIR/knowledge_os_${TIMESTAMP}.sql.gz"

echo "--- Backup Started: $(date) ---"
echo "   Цель: $GZ_FILE"

# Вариант 1: через Docker (если knowledge_postgres запущен)
if docker ps --format '{{.Names}}' | grep -q '^knowledge_postgres$'; then
  docker exec knowledge_postgres pg_dump -U admin -d knowledge_os | gzip > "$GZ_FILE"
# Вариант 2: локальный pg_dump
elif command -v pg_dump >/dev/null 2>&1; then
  PGPASSWORD="${PGPASSWORD:-secret}" pg_dump -U admin -h localhost -d knowledge_os | gzip > "$GZ_FILE"
else
  echo "❌ knowledge_postgres не запущен и pg_dump недоступен"
  exit 1
fi

SIZE=$(stat -f%z "$GZ_FILE" 2>/dev/null || stat -c%s "$GZ_FILE" 2>/dev/null || echo 0)
echo "✅ Готово: $(basename "$GZ_FILE") ($SIZE bytes)"

# Хранить последние 7 дней
find "$BACKUP_DIR" -name "knowledge_os_*.sql.gz" -mtime +7 -delete 2>/dev/null || true

echo "--- Backup Finished: $(date) ---"

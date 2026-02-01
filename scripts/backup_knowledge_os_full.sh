#!/usr/bin/env bash
# Полный бэкап Knowledge OS: локально (Mac Studio) + Google Drive
# Правило 3-2-1: local + offsite в облаке. (Telegram убран — лимит 50 MB, БД >50 MB)
# Mac Studio / Linux, Docker-aware
#
# Использование: ./scripts/backup_knowledge_os_full.sh
# Cron: 0 2 * * * cd /path/to/atra-web-ide && ./scripts/backup_knowledge_os_full.sh >> /tmp/backup_knowledge_os.log 2>&1
#
# Переменные (.env или export):
#   RCLONE_GDRIVE_REMOTE — имя rclone remote для Google Drive (например gdrive)
#   BACKUP_GDRIVE_ENABLED=true|false (по умолчанию true если rclone настроен)
set -e

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Загрузка .env (без перезаписи уже установленных переменных)
if [ -f "$ROOT/.env" ]; then
  set -a
  source "$ROOT/.env" 2>/dev/null || true
  set +a
fi

# --- Конфигурация ---
if [ -d "$HOME/Documents/dev/atra/backups" ]; then
  BACKUP_DIR="$HOME/Documents/dev/atra/backups"
elif [ -d "/root/knowledge_os/backups" ]; then
  BACKUP_DIR="/root/knowledge_os/backups"
else
  BACKUP_DIR="$ROOT/backups"
fi

RETENTION_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="knowledge_os_${TIMESTAMP}.sql.gz"
GZ_FILE="$BACKUP_DIR/$BACKUP_NAME"

# Telegram: TELEGRAM_CHAT_ID или TELEGRAM_USER_ID (для личного чата = user_id)
BACKUP_GDRIVE_ENABLED="${BACKUP_GDRIVE_ENABLED:-true}"

# rclone config path (Mac vs Linux)
RCLONE_CONF="${RCLONE_CONFIG:-$HOME/.config/rclone/rclone.conf}"
[ "$USER" = "root" ] && RCLONE_CONF="${RCLONE_CONFIG:-/root/.config/rclone/rclone.conf}"
RCLONE_GDRIVE_REMOTE="${RCLONE_GDRIVE_REMOTE:-gdrive}"

# Человекочитаемый размер (без numfmt — работает на macOS)
human_size() {
  local b=${1:-0}
  [ "$b" -ge 1073741824 ] && echo "$((b / 1073741824)) GB" && return
  [ "$b" -ge 1048576 ]    && echo "$((b / 1048576)) MB" && return
  [ "$b" -ge 1024 ]       && echo "$((b / 1024)) KB" && return
  echo "${b} B"
}

# stat: Mac -f%z, Linux -c%s
get_size() {
  stat -f%z "$1" 2>/dev/null || stat -c%s "$1" 2>/dev/null || echo 0
}

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

# --- 1. Локальный бэкап ---
log "--- Backup Started (local + GDrive) ---"
mkdir -p "$BACKUP_DIR"
log "   Цель: $GZ_FILE"

if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^knowledge_postgres$'; then
  docker exec knowledge_postgres pg_dump -U admin -d knowledge_os | gzip > "$GZ_FILE"
elif command -v pg_dump >/dev/null 2>&1; then
  PGPASSWORD="${PGPASSWORD:-secret}" pg_dump -U admin -h localhost -d knowledge_os | gzip > "$GZ_FILE"
else
  log "❌ knowledge_postgres не запущен и pg_dump недоступен"
  exit 1
fi

SIZE=$(get_size "$GZ_FILE")
log "✅ Локальный бэкап: $(basename "$GZ_FILE") ($(human_size "$SIZE"))"

# --- 2. Google Drive через rclone ---
GDRIVE_OK=false
if [ "$BACKUP_GDRIVE_ENABLED" = "true" ] && command -v rclone >/dev/null 2>&1 && [ -f "$RCLONE_CONF" ]; then
  if RCLONE_CONFIG="$RCLONE_CONF" rclone listremotes 2>/dev/null | grep -q "^${RCLONE_GDRIVE_REMOTE}:$"; then
    log "   Синхронизация в Google Drive (remote: $RCLONE_GDRIVE_REMOTE)..."
    if RCLONE_CONFIG="$RCLONE_CONF" rclone copy "$GZ_FILE" "${RCLONE_GDRIVE_REMOTE}:knowledge_os_backups/"; then
      log "✅ Google Drive: загружено"
      GDRIVE_OK=true
    else
      log "⚠️ Google Drive: ошибка rclone copy"
    fi
  else
    log "⚠️ Google Drive: remote '$RCLONE_GDRIVE_REMOTE' не найден. Запустите: rclone config"
  fi
else
  if [ "$BACKUP_GDRIVE_ENABLED" = "true" ]; then
    log "   Google Drive: rclone не установлен или конфиг отсутствует ($RCLONE_CONF)"
  else
    log "   Google Drive: отключен (BACKUP_GDRIVE_ENABLED=$BACKUP_GDRIVE_ENABLED)"
  fi
fi

# --- Очистка старых локальных бэкапов ---
find "$BACKUP_DIR" -name "knowledge_os_*.sql.gz" -mtime +$RETENTION_DAYS -delete 2>/dev/null || true

# --- Итог ---
log "--- Backup Finished ---"
log "   Local: ✅ | GDrive: $([ "$GDRIVE_OK" = true ] && echo '✅' || echo '⚠️')"
exit 0

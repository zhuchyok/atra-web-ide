#!/usr/bin/env bash
set -euo pipefail
export PATH="/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

SRC="$HOME/atra_backups/knowledge_postgres"
REMOTE="${GDRIVE_REMOTE:-gdrive}:ATRA_BACKUP/knowledge_postgres"
KEEP_DAYS_REMOTE="${KEEP_DAYS_REMOTE:-30}"

mkdir -p "$HOME/Library/Logs/atra"

rclone mkdir "${GDRIVE_REMOTE:-gdrive}:ATRA_BACKUP/knowledge_postgres" >/dev/null 2>&1 || true

# [v149.5] Порядок шагов ВАЖЕН: сначала retention (освобождаем квоту),
# потом загрузка только свежих дампов. Старый порядок (copy → delete) при
# переполненной квоте падал на copy (set -e) до delete — офсайт копился/старел.
rclone delete "$REMOTE" --include "*.dump" --min-age "${KEEP_DAYS_REMOTE}d" --drive-use-trash=false \
  --log-file "$HOME/Library/Logs/atra/gdrive_sync.err.log" --log-level INFO

rclone copy "$SRC" "$REMOTE" --include "*.dump" --max-age "${KEEP_DAYS_REMOTE}d" --transfers 2 --checkers 4 \
  --log-file "$HOME/Library/Logs/atra/gdrive_sync.out.log" --log-level INFO

echo "[gdrive-sync] done"

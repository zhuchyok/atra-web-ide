#!/bin/bash
# [v149.10] Еженедельная ротация логов-пожирателей (>256MB → обнуление).
# truncate-safe: файлы, открытые процессами, сохраняют inode.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
LIMIT=268435456  # 256MB
for f in \
  /opt/homebrew/var/log/ollama.log \
  "$HOME/Library/Logs/atra-auto-recovery.error.log" \
  "$HOME/Library/Logs/atra-auto-recovery.log" \
  "$HOME/Library/Logs/atra-mlx-api-server.log" \
  "$HOME/Library/Logs/atra-mlx-api-server.error.log" \
  "$HOME/Library/Logs/atra/mlx_api_server.err.log" \
  /Users/bikos/Documents/atra-web-ide/logs/mlx_api_server.log \
  "$HOME/Library/Logs/atra/employees-sync-daemon.error.log"
do
  [ -f "$f" ] || continue
  SIZE=$(stat -f %z "$f" 2>/dev/null || echo 0)
  [ "$SIZE" -gt "$LIMIT" ] && : > "$f" && echo "$(date '+%F %T') rotated: $f ($((SIZE/1048576))MB)"
done
exit 0

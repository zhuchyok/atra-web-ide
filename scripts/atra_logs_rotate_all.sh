#!/bin/bash
# [v150.14] Универсальная ротация atra-логов-пожирателей.
# Для каждого лога из списка: если >50MB — скопировать содержимое в <name>.<ts>.gz,
# затем обнулить оригинал трюкейтом (: > file, inode/fd процессов-владельцев сохраняется,
# НЕ rm), хранить 3 последних .gz-архива на файл.
# maintenance-флаг /tmp/atra_maintenance_mode (ставит scripts/maintenance.sh) → пропуск прогона.
# Запуск: LaunchAgent com.atra.log-rotate-all (StartInterval 3600) или руками.
# Дополнительно можно передать пути логов аргументами — они будут обработаны тем же правилом.
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

ROTATE_LOG="$HOME/Library/Logs/atra/rotate_all.log"
MAINTENANCE_FLAG="/tmp/atra_maintenance_mode"
LIMIT=$((50 * 1024 * 1024))   # порог ротации: 50MB
KEEP=3                        # сколько последних .gz-архивов оставлять на файл

# Список наблюдаемых логов: аудит волны-14 (15.10) + покрытие старого atra_logs_rotate.sh
# + прочие найденные >50MB-файлы ~/Library/Logs.
LOGS=(
  "/opt/homebrew/var/log/tailscaled.log"  # [v150.16] аудит-3.0
  /opt/homebrew/var/log/ollama.log
  "$HOME/Library/Logs/atra-mlx-monitor.error.log"
  "$HOME/Library/Logs/atra-ollama-hands.err.log"
  "$HOME/Library/Logs/atra-ollama-hands.log"
  "$HOME/Library/Logs/atra-self-check.log"
  "$HOME/Library/Logs/atra-self-check.err.log"
  "$HOME/Library/Logs/atra-mlx-api-server.log"
  "$HOME/Library/Logs/atra-mlx-api-server.error.log"
  "$HOME/Library/Logs/atra-auto-recovery.log"
  "$HOME/Library/Logs/atra-auto-recovery.error.log"
  "$HOME/Library/Logs/model-tracker.err.log"
  "$HOME/Library/Logs/ssh-tunnel-headscale.err.log"
  "$HOME/Library/Logs/ssh-tunnel-headscale.log"
  "$HOME/Library/Logs/victoria-mcp.err.log"
  "$HOME/Library/Logs/ollama-watchdog.log"
  "$HOME/Library/Logs/atra-curator.log"
  "$HOME/Library/Logs/atra-curator.error.log"
  "$HOME/Library/Logs/atra/mlx_api_server.err.log"
  "$HOME/Library/Logs/atra/employees-sync-daemon.error.log"
  /Users/bikos/Documents/atra-web-ide/logs/mlx_api_server.log
)
# Дополнительные файлы из аргументов командной строки.
LOGS+=("$@")

mkdir -p "$(dirname "$ROTATE_LOG")"
say() { echo "$(date '+%F %T') $*" >> "$ROTATE_LOG"; }

# MAINTENANCE MODE: при ручных операциях с инфраструктурой автоматика молчит.
if [ -f "$MAINTENANCE_FLAG" ]; then say "maintenance mode — skip run"; exit 0; fi

say "=== run start (pid $$) ==="
for f in "${LOGS[@]}"; do
  [ -f "$f" ] || continue
  size=$(stat -f %z "$f" 2>/dev/null) || continue
  [ "$size" -gt "$LIMIT" ] || continue

  ts=$(date '+%Y%m%d_%H%M%S')
  arch="$f.$ts.gz"
  # 1) Архив: gzip-копия содержимого; оригинал не трогаем, пока архив не готов.
  if ! gzip -c "$f" > "$arch.part" 2>>"$ROTATE_LOG"; then
    say "ERROR gzip failed, skip: $f"
    rm -f "$arch.part"
    continue
  fi
  mv "$arch.part" "$arch"
  # 2) Трюкейт оригинала: inode сохраняется, процессы-владельцы продолжают писать в тот же fd.
  : > "$f"
  asize=$(stat -f %z "$arch" 2>/dev/null || echo 0)
  say "rotated: $f $((size / 1048576))MB -> $(basename "$arch") $((asize / 1048576))MB"
  # 3) Чистим старые архивы: оставляем только $KEEP последних.
  ls -1t "$f".*.gz 2>/dev/null | tail -n +$((KEEP + 1)) | while IFS= read -r old; do
    rm -f "$old" && say "pruned old archive: $old"
  done
done
say "=== run end ==="
exit 0

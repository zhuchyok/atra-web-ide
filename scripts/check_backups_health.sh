#!/usr/bin/env bash
# Проверка свежести бэкапов knowledge_postgres (v143).
# Локальный дамп не старше MAX_AGE_HOURS часов, офсайт-копия на gdrive присутствует.
# При проблемах — алерт в ntfy. Cron: 04:00 ежедневно.
set -u

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_DIR="${LOCAL_BACKUP_DIR:-$HOME/atra_backups/knowledge_postgres}"
GDRIVE_REMOTE="${GDRIVE_REMOTE:-gdrive}"
GDRIVE_PATH="${GDRIVE_PATH:-ATRA_BACKUP/knowledge_postgres}"
MAX_AGE_HOURS="${MAX_AGE_HOURS:-25}"
NTFY_URL="${NTFY_URL:-https://ntfy.sh/atra_victoria_curator}"

ERRORS=0
MESSAGES=""

echo "[check] локальный бэкап: $LOCAL_DIR"
LATEST_LOCAL=$(ls -1t "$LOCAL_DIR"/*.dump 2>/dev/null | head -n 1 || echo "")
if [[ -z "$LATEST_LOCAL" ]]; then
  echo "❌ Локальный бэкап не найден!"
  ERRORS=$((ERRORS + 1))
  MESSAGES="$MESSAGES
❌ Локальный дамп не найден в $LOCAL_DIR"
else
  AGE_HOURS=$(( ($(date +%s) - $(stat -f %m "$LATEST_LOCAL" 2>/dev/null || echo 0)) / 3600 ))
  SIZE=$(stat -f %z "$LATEST_LOCAL" 2>/dev/null || echo 0)
  echo "  свежий: $(basename "$LATEST_LOCAL") (${AGE_HOURS}ч, $(du -h "$LATEST_LOCAL" | cut -f1))"
  if [[ "$AGE_HOURS" -gt "$MAX_AGE_HOURS" ]]; then
    echo "❌ Локальный бэкап слишком старый: ${AGE_HOURS} часов"
    ERRORS=$((ERRORS + 1))
    MESSAGES="$MESSAGES
❌ Дамп устарел: ${AGE_HOURS}ч (лимит ${MAX_AGE_HOURS}ч)"
  elif [[ "$SIZE" -lt 1000000 ]]; then
    echo "❌ Локальный бэкап слишком маленький: ${SIZE} bytes"
    ERRORS=$((ERRORS + 1))
    MESSAGES="$MESSAGES
❌ Дамп подозрительно мал: ${SIZE} bytes"
  else
    echo "✅ Локальный бэкап OK"
  fi
fi

echo "[check] Google Drive: ${GDRIVE_REMOTE}:${GDRIVE_PATH}"
GDRIVE_MAX_AGE_HOURS="${GDRIVE_MAX_AGE_HOURS:-49}"
if command -v rclone >/dev/null 2>&1; then
  LATEST_GDRIVE=$(rclone lsf "${GDRIVE_REMOTE}:${GDRIVE_PATH}" --include "*.dump" --max-depth 1 2>/dev/null | sort | tail -n 1 || echo "")
  if [[ -z "$LATEST_GDRIVE" ]]; then
    echo "❌ Google Drive бэкап не найден!"
    ERRORS=$((ERRORS + 1))
    MESSAGES="$MESSAGES
❌ Офсайт-копия на gdrive не найдена"
  else
    # [v149.5] Возраст офсайт-копии по имени файла: YYYY-MM-DD_HH-MM-SS.
    # Только «наличие» маскировало неделю без аплоадов (quota exceeded).
    GD_DATE=$(echo "$LATEST_GDRIVE" | grep -oE '[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2}' | head -n 1)
    if [[ -n "$GD_DATE" ]]; then
      GD_EPOCH=$(date -j -f "%Y-%m-%d_%H-%M-%S" "$GD_DATE" +%s 2>/dev/null || echo 0)
      GD_AGE_HOURS=$(( ($(date +%s) - GD_EPOCH) / 3600 ))
      echo "  офсайт: $LATEST_GDRIVE (${GD_AGE_HOURS}ч)"
      if [[ "$GD_AGE_HOURS" -gt "$GDRIVE_MAX_AGE_HOURS" ]]; then
        echo "❌ Офсайт-бэкап устарел: ${GD_AGE_HOURS}ч (лимит ${GDRIVE_MAX_AGE_HOURS}ч)"
        ERRORS=$((ERRORS + 1))
        MESSAGES="$MESSAGES
❌ Офсайт-копия на gdrive устарела: ${GD_AGE_HOURS}ч (файл $LATEST_GDRIVE) — проверь gdrive sync (квота?)"
      else
        echo "✅ Google Drive бэкап OK: $LATEST_GDRIVE"
      fi
    else
      echo "✅ Google Drive бэкап OK (возраст не распознан): $LATEST_GDRIVE"
    fi
  fi
else
  echo "⚠️ rclone не найден — офсайт-проверка пропущена"
  ERRORS=$((ERRORS + 1))
  MESSAGES="$MESSAGES
⚠️ rclone не найден — офсайт-проверка пропущена"
fi

if [[ "$ERRORS" -eq 0 ]]; then
  echo "✅ Все бэкапы в порядке"
  exit 0
fi

echo "❌ Обнаружены проблемы (код: $ERRORS)"
# Алерт в ntfy (не блокируем код выхода нотификацией)
curl -s -m 10 -H "Title: 🔴 ATRA: бэкапы под угрозой" -H "Priority: high" \
  -H "Tags: red_circle,floppy_disk" -d "Проблем с бэкапами: $ERRORS
$MESSAGES" "$NTFY_URL" >/dev/null 2>&1 || true
exit "$ERRORS"

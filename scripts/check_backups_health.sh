#!/usr/bin/env bash
# Проверка свежести бэкапов knowledge_postgres (v143).
# Локальный дамп не старше MAX_AGE_HOURS часов, офсайт-копия на gdrive присутствует.
# При проблемах — алерт в ntfy. Cron: 04:00 ежедневно.
set -u

# ATRA_FORCE_PATH lets CI/smoke inject mocks ahead of brew (same pattern as container scripts).
if [[ -n "${ATRA_FORCE_PATH:-}" ]]; then
  export PATH="$ATRA_FORCE_PATH"
else
  export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_DIR="${LOCAL_BACKUP_DIR:-$HOME/atra_backups/knowledge_postgres}"
GDRIVE_REMOTE="${GDRIVE_REMOTE:-gdrive}"
GDRIVE_PATH="${GDRIVE_PATH:-ATRA_BACKUP/knowledge_postgres}"
MAX_AGE_HOURS="${MAX_AGE_HOURS:-25}"
NTFY_URL="${NTFY_URL:-https://ntfy.sh/atra_victoria_curator}"
NTFY_COOLDOWN_SEC="${NTFY_COOLDOWN_SEC:-21600}"  # 6h same-alert dedup

ERRORS=0
MESSAGES=""

# CI / mktemp-HOME sandboxes (health-scripts-smoke runs auto_setup with HOME=$mktemp/home)
# must not page the real curator topic.
# Match only: /tmp/tmp.XXX, /tmp/tmp.XXX/home, /var/folders/.../T/tmp.XXX[/home]
# Do NOT match arbitrary children like .../tmp.XXX/realhome (used by dedup smoke).
is_sandbox_home() {
  [[ "${HOME:-}" =~ ^/tmp/tmp\.[^/]+(/home)?$ ]] && return 0
  [[ "${HOME:-}" =~ ^/var/folders/[^/]+/[^/]+/T/tmp\.[^/]+(/home)?$ ]] && return 0
  return 1
}

should_skip_ntfy() {
  if [[ "${ATRA_SKIP_NTFY:-}" == "1" || "${ATRA_SKIP_NTFY:-}" == "true" ]]; then
    echo "skip: ATRA_SKIP_NTFY"
    return 0
  fi
  if [[ -z "${NTFY_URL}" ]]; then
    echo "skip: empty NTFY_URL"
    return 0
  fi
  if [[ "${CI:-}" == "true" || "${GITHUB_ACTIONS:-}" == "true" ]]; then
    echo "skip: CI"
    return 0
  fi
  if is_sandbox_home; then
    echo "skip: sandbox HOME=${HOME}"
    return 0
  fi
  return 1
}

ntfy_state_path() {
  # Prefer a durable host log dir; fall back under /tmp when HOME is fake.
  if is_sandbox_home; then
    echo "/tmp/atra_backup_health_ntfy.state"
    return
  fi
  local dir="${HOME}/Library/Logs/atra"
  mkdir -p "$dir" 2>/dev/null || true
  if [[ -d "$dir" ]]; then
    echo "$dir/backup_health_ntfy.state"
  else
    echo "/tmp/atra_backup_health_ntfy.state"
  fi
}

# Dedup identical alert body for NTFY_COOLDOWN_SEC (default 6h).
ntfy_allowed() {
  local body="$1"
  local state
  state="$(ntfy_state_path)"
  local now hash prev_ts=0 prev_hash=""
  now="$(date +%s)"
  hash="$(printf '%s' "$body" | shasum -a 256 2>/dev/null | awk '{print $1}')"
  if [[ -z "$hash" ]]; then
    hash="$(printf '%s' "$body" | cksum | awk '{print $1}')"
  fi
  if [[ -f "$state" ]]; then
    # format: <epoch> <hash>
    read -r prev_ts prev_hash <"$state" || true
  fi
  if [[ -n "$prev_hash" && "$prev_hash" == "$hash" && -n "$prev_ts" ]]; then
    if (( now - prev_ts < NTFY_COOLDOWN_SEC )); then
      echo "dedup: same alert within ${NTFY_COOLDOWN_SEC}s (age=$((now - prev_ts))s)" >&2
      return 1
    fi
  fi
  printf '%s %s\n' "$now" "$hash" >"$state" 2>/dev/null || true
  return 0
}

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
ALERT_BODY="Проблем с бэкапами: $ERRORS
$MESSAGES"

skip_reason=""
if skip_reason="$(should_skip_ntfy)"; then
  echo "🔕 ntfy пропущен ($skip_reason)"
elif ! ntfy_allowed "$ALERT_BODY"; then
  echo "🔕 ntfy пропущен (rate-limit/dedup)"
else
  # Алерт в ntfy (не блокируем код выхода нотификацией)
  curl -s -m 10 -H "Title: 🔴 ATRA: бэкапы под угрозой" -H "Priority: high" \
    -H "Tags: red_circle,floppy_disk" -d "$ALERT_BODY" "$NTFY_URL" >/dev/null 2>&1 || true
fi
exit "$ERRORS"

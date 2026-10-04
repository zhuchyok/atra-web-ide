#!/bin/bash
# [v149.14] Мозг всегда тёплый — БЕЗОПАСНО:
#  - грузим только если свободной RAM ≥ 40% (загрузка 29GB под давлением = segfault всего сервера)
#  - после неудачи: бэкофф 30 мин + kickstart ollama (сегфолт отравляет очередь сервера на 503)
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
M="${VICTORIA_BRAIN_MODEL:-victoria-qwen38:latest}"
U="${OLLAMA_BASE_URL:-http://localhost:11434}"
LOCK=/tmp/brain_keepalive.backoff
LOG="$HOME/Library/Logs/atra/brain_keepalive.log"

ts() { date '+%F %T'; }

# 1. Уже загружена — тихо выходим
if curl -s --max-time 5 "$U/api/ps" | grep -q "\"$M\""; then exit 0; fi

# 2. Бэкофф после недавней неудачи (30 мин)
if [ -f "$LOCK" ] && [ $(( $(date +%s) - $(stat -f %m "$LOCK") )) -lt 1800 ]; then exit 0; fi

# 3. Свободной памяти ≥ 40%? (иначе загрузка 29GB рискует сегфолтом)
FREE=$(memory_pressure -Q 2>/dev/null | grep -oE '[0-9]+%' | head -1 | tr -d '%')
[ -z "$FREE" ] && FREE=50
if [ "$FREE" -lt 40 ]; then echo "$(ts) skip: RAM free ${FREE}% < 40%" >> "$LOG"; exit 0; fi

# 4. Пробуем загрузить
curl -s --max-time 240 "$U/api/generate" \
  -d "{\"model\":\"$M\",\"prompt\":\"ok\",\"stream\":false,\"keep_alive\":\"12h\"}" >/dev/null 2>&1

# 5. Проверка результата
if curl -s --max-time 5 "$U/api/ps" | grep -q "\"$M\""; then
  echo "$(ts) brain warmed (RAM free ${FREE}%)" >> "$LOG"
else
  echo "$(ts) LOAD FAILED (RAM free ${FREE}%) — backoff 30m + ollama restart" >> "$LOG"
  touch "$LOCK"
  launchctl kickstart -k gui/$(id -u)/homebrew.mxcl.ollama 2>/dev/null
fi
exit 0

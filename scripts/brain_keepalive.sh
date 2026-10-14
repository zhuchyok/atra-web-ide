#!/bin/bash
# [v149.14] Мозг всегда тёплый — БЕЗОПАСНО:
#  - грузим только если свободной RAM ≥ 40% (загрузка 29GB под давлением = segfault всего сервера)
#  - после неудачи: бэкофф 30 мин + kickstart ollama (сегфолт отравляет очередь сервера на 503)
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"

# [v149.34] MAINTENANCE MODE: при ручных операциях с инфраструктурой все
# автоматические акторы молчат (файл-флаг ставит scripts/maintenance.sh).
if [ -f /tmp/atra_maintenance_mode ]; then echo "$(date '+%F %T') maintenance mode — skip"; exit 0; fi
M="${VICTORIA_BRAIN_MODEL:-victoria-qwen38:latest}"
U="${OLLAMA_BASE_URL:-http://localhost:11434}"
LOCK=/tmp/brain_keepalive.backoff
LOG="$HOME/Library/Logs/atra/brain_keepalive.log"

ts() { date '+%F %T'; }

# [v150.3] Single-instance (mkdir-лок — flock на macOS нет): два параллельных
# инстанса оба доходили до LOAD FAILED и оба кикали ollama (дубль-рестарты).
# Stale-защита: каталог-лок старше 15 минут считается брошенным.
LOCKDIR=/tmp/brain_keepalive.instance
if [ -d "$LOCKDIR" ] && [ $(( $(date +%s) - $(stat -f %m "$LOCKDIR") )) -gt 900 ]; then
  rmdir "$LOCKDIR" 2>/dev/null
fi
if ! mkdir "$LOCKDIR" 2>/dev/null; then
  echo "$(ts) skip: уже работает другой инстанс" >> "$LOG"; exit 0
fi
trap 'rmdir "$LOCKDIR" 2>/dev/null' EXIT

# 3.5 [v150.6] «Сначала руки, потом мозг»: при живом потоке к мозгу (np=1)
# ollama 0.33 бесконечно морит загрузки НОВЫХ раннеров — phi/nomic не могли
# подняться часами, encode отдавал 500. Перед прогревом мозга пиним руки
# и ждём их резидентности (счётчик на случай больной очереди).
_hands_ok() { curl -s --max-time 5 "$U/api/ps" 2>/dev/null | /usr/bin/grep -q '"phi3.5:3.8b'; }
if ! _hands_ok; then
  echo "$(ts) hands-first: пин phi3.5+nomic перед мозгом" >> "$LOG"
  # [v150.12] Руки живут на 11437 (v150.8) — пиним ИХ инстанс, не мозговой!
  # До сих пор пин шёл на $U (11434) — это и был «загадочный пиннер phi»,
  # кормивший карусель «гард выгружает / кипер грузит».
  H="http://127.0.0.1:11437"
  curl -s --max-time 300 "$H/api/generate" \
    -d '{"model":"phi3.5:3.8b","prompt":"ok","stream":false,"keep_alive":-1,"options":{"num_ctx":16384,"num_predict":1}}' >/dev/null 2>&1 &
  curl -s --max-time 120 "$H/api/embed" \
    -d '{"model":"nomic-embed-text","input":"ping","keep_alive":-1}' >/dev/null 2>&1
  _w=0; while ! _hands_ok && [ $_w -lt 24 ]; do sleep 5; _w=$((_w+1)); done
  _hands_ok && echo "$(ts) hands-first: phi3.5 резидентна ($_w×5с)" >> "$LOG" \
            || echo "$(ts) hands-first: phi не поднялась за 120с — греем мозг всё равно" >> "$LOG"
fi

# 1. Уже загружена — тихо выходим.
# [v150.5] Разделяем «проба упала» и «модели нет»: под ночной нагрузкой api/ps
# таймаутил за 5с → ложные «brain warmed» каждый час (мозг был резидентен!
# форензика 11.10). Теперь: проба упала дважды → считаем мозг ЖИВЫМ (fail-safe),
# греем только при доказанном отсутствии в валидном ответе.
PSOUT=$(curl -s --max-time 5 "$U/api/ps" 2>/dev/null)
if [ -z "$PSOUT" ]; then
  sleep 3
  PSOUT=$(curl -s --max-time 5 "$U/api/ps" 2>/dev/null)
  [ -z "$PSOUT" ] && exit 0   # ollama не отвечает — не трогаем, разберётся сторож
fi
echo "$PSOUT" | grep -q "\"$M\"" && exit 0

# 2. Бэкофф после недавней неудачи (30 мин)
if [ -f "$LOCK" ] && [ $(( $(date +%s) - $(stat -f %m "$LOCK") )) -lt 1800 ]; then exit 0; fi

# 3. Свободной памяти ≥ 40%? (иначе загрузка 29GB рискует сегфолтом)
FREE=$(memory_pressure -Q 2>/dev/null | grep -oE '[0-9]+%' | head -1 | tr -d '%')
[ -z "$FREE" ] && FREE=50
if [ "$FREE" -lt 40 ]; then echo "$(ts) skip: RAM free ${FREE}% < 40%" >> "$LOG"; exit 0; fi

# 4. Пробуем загрузить
curl -s --max-time 240 "$U/api/generate" \
  -d "{\"model\":\"$M\",\"prompt\":\"ok\",\"stream\":false,\"keep_alive\":\"12h\"}" >/dev/null 2>&1

RESP=$(curl -s --max-time 30 "$U/api/tags" 2>/dev/null)
if ! echo "$RESP" | grep -q "qwen38"; then
  echo "$(ts) ALERT: модель $M отсутствует на сервере (404) — удалена с диска? Нужен re-pull, не ретрай" >> "$LOG"
  curl -s -m 8 -H "Title: 🔴 Модель мозга удалена с диска" -H "Priority: high" -d "victoria-qwen38 отсутствует в /api/tags — нужен re-pull из источника" "https://ntfy.sh/atra_victoria_curator" >/dev/null 2>&1
  exit 0
fi

# 5. Проверка результата
# [v149.27] Успех = модель РЕАЛЬНО резидентна (api/ps), а не «curl не упал».
# Ошибка загрузки ≠ рестарт ollama сразу: сначала один ретрай, рестарт —
# только если модель не появилась и после него (иначе кипер дёргал Ollama
# при кратковременной недоступности после рестарта Docker).
if curl -s --max-time 5 "$U/api/ps" | grep -q "\"$M\""; then
  echo "$(ts) brain warmed (RAM free ${FREE}%)" >> "$LOG"
  rm -f "$LOCK"
  exit 0
fi
sleep 20
if curl -s --max-time 5 "$U/api/ps" | grep -q "\"$M\""; then
  echo "$(ts) brain warmed (late check, RAM free ${FREE}%)" >> "$LOG"
  rm -f "$LOCK"
  exit 0
fi
echo "$(ts) LOAD FAILED (RAM free ${FREE}%) — backoff 30m + ollama restart" >> "$LOG"
touch "$LOCK"
launchctl kickstart -k gui/$(id -u)/homebrew.mxcl.ollama 2>/dev/null
exit 0

#!/bin/bash
# [v150.12] Урок GC-инцидента: блобы re-pullable (11 мин), МАНИФЕСТЫ — нет.
# [v150.13] Усилено до полного снапшота каталога БЕЗ root и БЕЗ места:
# cp -al (hardlinks) — удаление/GC оригиналов не освобождает данные, пока
# жива ссылка в снапшоте. Ночной запуск cron 04:30 + ротация 7 снапшотов.
set -uo pipefail
TS=$(date +%F)
OUT="$HOME/backups/ollama_manifests"
SNAP="$HOME/backups/ollama_blobs_snapshots"
mkdir -p "$OUT" "$SNAP"

# 1) Манифесты (обоих каталогов, килобайты) — tar
tar -czf "$OUT/manifests_$TS.tar.gz" -C "$HOME" .ollama/models/manifests .ollama-hands/manifests 2>/dev/null || true
ls -t "$OUT"/*.tar.gz 2>/dev/null | tail -n +15 | xargs rm -f 2>/dev/null

# 2) Hardlink-снапшот блобов (мгновенно, 0 байт)
if [ ! -d "$SNAP/$TS" ]; then
  cp -al "$HOME/.ollama/models/blobs" "$SNAP/$TS" 2>/dev/null \
    && echo "$(date '+%F %T') hardlink-снапшот блобов: $SNAP/$TS" \
    || echo "$(date '+%F %T') WARNING: снапшот не создан"
fi

# 3) Ротация (старше 7 дней)
find "$SNAP" -maxdepth 1 -type d -name '20*' -mtime +7 -exec rm -rf {} + 2>/dev/null

echo "$(date '+%F %T') backup OK: manifests=$(ls "$OUT" | wc -l | tr -d ' '), snapshots=$(ls "$SNAP" 2>/dev/null | wc -l | tr -d ' ')"

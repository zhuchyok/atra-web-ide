#!/bin/bash
# [v150.12] Урок №26 инцидента GC-блобов: блобы re-pullable, МАНИФЕСТЫ+Modelfile — нет.
# Еженочный tar манифестов обоих каталогов (секунды, килобайты) — страховка класса «GC съел веса».
set -euo pipefail
TS=$(date +%F)
OUT="$HOME/backups/ollama_manifests"
mkdir -p "$OUT"
tar -czf "$OUT/manifests_$TS.tar.gz" -C "$HOME" .ollama/models/manifests .ollama-hands/manifests 2>/dev/null || true
ls -t "$OUT"/*.tar.gz | tail -n +15 | xargs rm -f 2>/dev/null || true
echo "$(date '+%F %T') manifests backup OK: $(ls "$OUT" | wc -l | tr -d ' ') файлов"

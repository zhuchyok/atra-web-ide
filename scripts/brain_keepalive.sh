#!/bin/bash
# [v149.9] Мозг всегда тёплый: если victoria-qwen38 не резидентна — грузим.
# Гарантия контракта v149.4 независимо от разгрузчиков (ice/shadow/board/unload-политик).
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin"
M="${VICTORIA_BRAIN_MODEL:-victoria-qwen38:latest}"
U="${OLLAMA_BASE_URL:-http://localhost:11434}"
LOADED=$(curl -s --max-time 5 "$U/api/ps" | grep -c "\"$M\"" || true)
if [ "$LOADED" -eq 0 ]; then
  curl -s --max-time 120 "$U/api/generate" \
    -d "{\"model\":\"$M\",\"prompt\":\"ok\",\"stream\":false,\"keep_alive\":\"2h\"}" >/dev/null 2>&1
  echo "$(date '+%F %T') brain re-warmed: $M"
fi

#!/bin/bash
# toggle_strict_local.sh — быстрый переключатель STRICT_LOCAL
# Использование:
#   bash scripts/toggle_strict_local.sh on   → STRICT_LOCAL=true  (100% локальный режим)
#   bash scripts/toggle_strict_local.sh off  → STRICT_LOCAL=false (веб-поиск разрешён)
#   bash scripts/toggle_strict_local.sh      → показать текущее значение

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env"

current=$(grep "^STRICT_LOCAL=" "$ENV_FILE" | cut -d= -f2)
mode="${1:-status}"

case "$mode" in
  on)
    sed -i '' 's/^STRICT_LOCAL=.*/STRICT_LOCAL=true/' "$ENV_FILE"
    echo "🔒 STRICT_LOCAL=true — веб-поиск ЗАБЛОКИРОВАН, только локальные модели"
    echo "   Перезапустите Victoria: docker restart victoria-agent veronica-agent"
    ;;
  off)
    sed -i '' 's/^STRICT_LOCAL=.*/STRICT_LOCAL=false/' "$ENV_FILE"
    echo "🌐 STRICT_LOCAL=false — веб-поиск РАЗРЕШЁН (SearXNG → DuckDuckGo)"
    echo "   Перезапустите Victoria: docker restart victoria-agent veronica-agent"
    ;;
  status|"")
    echo "Текущий режим: STRICT_LOCAL=${current:-не задан}"
    if [ "$current" = "true" ]; then
      echo "🔒 Локальный режим АКТИВЕН — веб-поиск заблокирован"
    else
      echo "🌐 Веб-поиск РАЗРЕШЁН — провайдеры: $(grep '^WEB_SEARCH_PROVIDERS=' "$ENV_FILE" | cut -d= -f2)"
    fi
    ;;
  *)
    echo "Использование: $0 [on|off|status]"
    exit 1
    ;;
esac

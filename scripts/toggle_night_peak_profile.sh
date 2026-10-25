#!/bin/bash
# toggle_night_peak_profile.sh — night peak guard profile for local hardware
# Usage:
#   bash scripts/toggle_night_peak_profile.sh on [--apply]
#   bash scripts/toggle_night_peak_profile.sh off [--apply]
#   bash scripts/toggle_night_peak_profile.sh status
#
# Profile intent:
# - "on": prioritize interactive stability under burst (strong background throttling)
# - "off": balanced defaults for daytime throughput

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ENV_FILE="$ROOT/.env"
MODE="${1:-status}"
APPLY_FLAG="${2:-}"

if [ ! -f "$ENV_FILE" ]; then
  echo "❌ .env not found: $ENV_FILE"
  exit 1
fi

set_kv() {
  local key="$1"
  local value="$2"
  if grep -q "^${key}=" "$ENV_FILE"; then
    # macOS BSD sed syntax
    sed -i '' "s|^${key}=.*|${key}=${value}|" "$ENV_FILE"
  else
    printf "\n%s=%s\n" "$key" "$value" >> "$ENV_FILE"
  fi
}

show_status() {
  echo "Night peak profile variables:"
  for key in \
    SEMANTIC_CACHE_EMBED_CONCURRENCY \
    EMBED_OLLAMA_CONCURRENCY \
    SEMANTIC_CACHE_EMBED_COOLDOWN_SEC \
    EMBED_UPSTREAM_COOLDOWN_SEC \
    ORCHESTRATOR_BACKGROUND_SOURCES \
    ORCHESTRATOR_BACKGROUND_MAX_DISPATCH_PER_CYCLE \
    ORCHESTRATOR_BACKGROUND_RETRY_MIN
  do
    local line
    line="$(grep "^${key}=" "$ENV_FILE" || true)"
    if [ -n "$line" ]; then
      echo "  $line"
    else
      echo "  ${key}=<not set>"
    fi
  done
}

apply_services() {
  echo "🔁 Recreating runtime services to apply .env changes..."
  (
    cd "$ROOT/knowledge_os"
    docker compose -f docker-compose.yml -f docker-compose.agents.yml up -d --force-recreate \
      victoria-agent \
      knowledge_os_orchestrator \
      knowledge_os_worker \
      knowledge_vector_core \
      expert-worker-anna \
      expert-worker-victoria \
      expert-worker-heavy \
      expert-worker-dynamic-1 \
      expert-worker-dynamic-2 \
      expert-worker-dynamic-3 \
      expert-worker-dynamic-4 \
      expert-worker-dynamic-5
  )
  echo "✅ Services recreated"
}

case "$MODE" in
  on)
    # Aggressive profile for night burst protection
    set_kv "SEMANTIC_CACHE_EMBED_CONCURRENCY" "1"
    set_kv "EMBED_OLLAMA_CONCURRENCY" "2"
    set_kv "SEMANTIC_CACHE_EMBED_COOLDOWN_SEC" "8"
    set_kv "EMBED_UPSTREAM_COOLDOWN_SEC" "8"
    set_kv "ORCHESTRATOR_BACKGROUND_SOURCES" "security_responder,nightly_hypothesis_debate"
    set_kv "ORCHESTRATOR_BACKGROUND_MAX_DISPATCH_PER_CYCLE" "0"
    set_kv "ORCHESTRATOR_BACKGROUND_RETRY_MIN" "7"
    echo "🌙 Night peak profile: ON"
    show_status
    if [ "$APPLY_FLAG" = "--apply" ]; then
      apply_services
    else
      echo "ℹ️ Run with --apply to recreate services now"
    fi
    ;;
  off)
    # Balanced defaults for regular operation
    set_kv "SEMANTIC_CACHE_EMBED_CONCURRENCY" "2"
    set_kv "EMBED_OLLAMA_CONCURRENCY" "3"
    set_kv "SEMANTIC_CACHE_EMBED_COOLDOWN_SEC" "5"
    set_kv "EMBED_UPSTREAM_COOLDOWN_SEC" "5"
    set_kv "ORCHESTRATOR_BACKGROUND_SOURCES" "security_responder,nightly_hypothesis_debate"
    set_kv "ORCHESTRATOR_BACKGROUND_MAX_DISPATCH_PER_CYCLE" "1"
    set_kv "ORCHESTRATOR_BACKGROUND_RETRY_MIN" "5"
    echo "☀️ Night peak profile: OFF (balanced)"
    show_status
    if [ "$APPLY_FLAG" = "--apply" ]; then
      apply_services
    else
      echo "ℹ️ Run with --apply to recreate services now"
    fi
    ;;
  status|"")
    show_status
    ;;
  *)
    echo "Usage: $0 [on|off|status] [--apply]"
    exit 1
    ;;
esac

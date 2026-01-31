#!/bin/bash
# Проверка Victoria и Veronica после миграции.
# Требует: Docker, стек Knowledge OS (victoria-agent, veronica-agent), MLX/Ollama на :11434.

VIC="${1:-http://localhost:8010}"
VER="${2:-http://localhost:8011}"

echo "=============================================="
echo "Проверка агентов Victoria / Veronica"
echo "=============================================="
echo "Victoria: $VIC"
echo "Veronica: $VER"
echo ""

err=0

check() {
  local name="$1"
  local url="$2"
  if curl -sf --connect-timeout 5 "$url" >/dev/null 2>&1; then
    echo "  OK $name"
  else
    echo "  FAIL $name ($url)"
    err=$((err + 1))
  fi
}

echo "Health:"
check "Victoria /health" "$VIC/health"
check "Veronica /health" "$VER/health"
echo ""

echo "Status:"
curl -sf -o /dev/null --connect-timeout 5 "$VIC/status" 2>/dev/null && echo "  OK Victoria /status" || { echo "  FAIL Victoria /status"; err=$((err+1)); }
curl -sf -o /dev/null --connect-timeout 5 "$VER/status" 2>/dev/null && echo "  OK Veronica /status" || { echo "  FAIL Veronica /status"; err=$((err+1)); }
echo ""

if [ $err -eq 0 ]; then
  echo "Все проверки пройдены."
else
  echo "Ошибок: $err. Убедитесь, что Docker, Knowledge OS и MLX (localhost:11434) запущены."
  exit 1
fi
echo "=============================================="

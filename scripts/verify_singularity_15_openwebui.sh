#!/usr/bin/env bash
# Проверка готовности сценария Open WebUI → ask_victoria → Victoria.
# Запуск из корня репозитория: ./scripts/verify_singularity_15_openwebui.sh

set -e
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

OK=0
FAIL=0

check() {
  if "$@"; then
    echo "  OK   $*"
    OK=$((OK + 1))
    return 0
  else
    echo "  FAIL $*"
    FAIL=$((FAIL + 1))
    return 1
  fi
}

echo "=== Проверка Singularity 15.0 ==="
echo ""

echo "Victoria (порт 8010)..."
if curl -sf --connect-timeout 3 -o /dev/null -w "" "http://localhost:8010/health" 2>/dev/null; then
  echo "  OK   Victoria /health"
  OK=$((OK + 1))
else
  echo "  FAIL Victoria не отвечает на :8010. Запустите: ./scripts/start_singularity_15_openwebui.sh"
  FAIL=$((FAIL + 1))
fi

echo ""
echo "Open WebUI (порт 3005)..."
if curl -sf --connect-timeout 3 -o /dev/null -w "" "http://localhost:3005" 2>/dev/null; then
  echo "  OK   Open WebUI доступен"
  OK=$((OK + 1))
else
  echo "  FAIL Open WebUI не отвечает на :3005"
  FAIL=$((FAIL + 1))
fi

echo ""
echo "Бэкенд (порт 8080, опционально)..."
if curl -sf --connect-timeout 2 -o /dev/null -w "" "http://localhost:8080/health" 2>/dev/null; then
  echo "  OK   Backend /health"
  OK=$((OK + 1))
  echo "  Проверка ask-victoria (таймаут 90 с, первый запрос к Victoria может быть долгим)..."
  if RESP=$(curl -sf --max-time 90 -X POST "http://localhost:8080/api/chat/ask-victoria" \
    -H "Content-Type: application/json" \
    -d '{"goal":"Кратко ответь: один плюс один?"}' 2>/dev/null); then
    if echo "$RESP" | grep -qE '[0-9]|два|two|2'; then
      echo "  OK   ask-victoria вернул ответ"
      OK=$((OK + 1))
    else
      echo "  WARN ask-victoria ответ: ${RESP:0:80}..."
    fi
  else
    echo "  WARN ask-victoria не ответил (таймаут или ошибка)"
  fi
else
  echo "  skip Backend не запущен (не обязательно для прямого вызова Victoria)"
fi

echo ""
echo "Файлы конфигурации..."
check test -f "configs/openwebui_ask_victoria_tool.py"
check test -f "docs/SINGULARITY_15_GOLDEN_PERSONA.md"
check test -f "docs/OPENWEBUI_SINGULARITY_15_RUNBOOK.md"

echo ""
if [ "$FAIL" -gt 0 ]; then
  echo "Итог: $OK проверок OK, $FAIL не прошли. Исправьте и перезапустите проверку."
  exit 1
fi
echo "Итог: все $OK проверок пройдены. Настройте в Open WebUI системный промпт и инструмент (см. runbook)."

#!/usr/bin/env bash
# Проверка цепочки Open WebUI → Ollama (модель victoria-wisdom-v3.5).
# Загрузка модели полностью локальная, интернет не используется.
# Запуск из корня репозитория: ./scripts/verify_openwebui_ollama.sh [--warmup]

set -e
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
MODEL_NAME="${OLLAMA_MODEL:-victoria-wisdom-v3.5}"
WARMUP=false
[[ "${1:-}" == "--warmup" ]] && WARMUP=true

echo "=== Проверка Open WebUI → Ollama ==="
echo "Ollama: $OLLAMA_HOST"
echo "Модель: $MODEL_NAME"
echo ""

# 1. Ollama на хосте
echo "--- 1. Ollama на хосте ---"
if curl -sf --connect-timeout 3 -o /dev/null -w "" "$OLLAMA_HOST/api/tags" 2>/dev/null; then
  echo "  OK   $OLLAMA_HOST доступен"
else
  echo "  FAIL Ollama не отвечает. Запустите Ollama на хосте (ollama serve)."
  exit 1
fi

# 2. Список моделей
echo ""
echo "--- 2. Список моделей ---"
TAGS=$(curl -sf --connect-timeout 5 "$OLLAMA_HOST/api/tags" 2>/dev/null || echo "{}")
if echo "$TAGS" | grep -q "$MODEL_NAME"; then
  echo "  OK   Модель $MODEL_NAME есть в списке"
else
  echo "  FAIL Модель $MODEL_NAME не найдена. Создайте: bash knowledge_os/scripts/assemble_victoria_wisdom.sh"
  echo "  Доступные: $(echo "$TAGS" | grep -o '"name":"[^"]*"' | head -5 | tr '\n' ' ')"
  exit 1
fi

# 3. Доступ из контейнера Open WebUI (если контейнер запущен)
echo ""
echo "--- 3. Доступ из контейнера open-webui ---"
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^open-webui$'; then
  if docker exec open-webui curl -sf --connect-timeout 5 -o /dev/null -w "" "http://host.docker.internal:11434/api/tags" 2>/dev/null; then
    echo "  OK   Контейнер open-webui видит Ollama на host.docker.internal:11434"
  else
    echo "  WARN Контейнер не достучался до Ollama (host.docker.internal). Проверьте сеть Docker."
  fi
else
  echo "  skip Контейнер open-webui не запущен"
fi

# 4. Open WebUI доступен
echo ""
echo "--- 4. Open WebUI (порт 3005) ---"
if curl -sf --connect-timeout 3 -o /dev/null -w "" "http://localhost:3005" 2>/dev/null; then
  echo "  OK   Open WebUI доступен на :3005"
else
  echo "  WARN Open WebUI не отвечает на :3005"
fi

# 5. Опционально: прогрев модели (долго при первом запуске)
if "$WARMUP"; then
  echo ""
  echo "--- 5. Прогрев модели (может занять 2–5 мин) ---"
  echo "  Вызов: ollama run $MODEL_NAME 'ping'"
  if command -v ollama >/dev/null 2>&1; then
    if command -v timeout >/dev/null 2>&1; then
      RUN="timeout 300 ollama run $MODEL_NAME ping"
    else
      RUN="ollama run $MODEL_NAME ping"
    fi
    if eval "$RUN" 2>/dev/null | head -1 >/dev/null; then
      echo "  OK   Модель прогрета, дальше в Open WebUI не должна висеть «Загрузка…»"
    else
      echo "  WARN Прогрев не удался или таймаут. Проверьте: ollama ps"
    fi
  else
    echo "  skip ollama не в PATH (запуск с хоста)"
  fi
fi

echo ""
echo "Итог: цепочка проверена. Загрузка модели в Open WebUI идёт локально (интернет не нужен)."
echo "Если в UI всё ещё «Загрузка…» — подождите 3–5 мин при первом выборе модели или выполните: ./scripts/verify_openwebui_ollama.sh --warmup"

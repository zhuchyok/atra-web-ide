#!/bin/bash
# docker-entrypoint.sh — защитный слой перед запуском victoria-agent
# Предотвращает: (1) бесконечный restart loop при синтаксических ошибках,
#                (2) накопление зомби-процессов enhanced_orchestrator.py
set -e

MAIN_MODULE="src/agents/bridge/victoria_server.py"

# --- 1. Syntax check: fail fast, не давая Docker крутить restart loop ---
echo "[entrypoint] Проверка синтаксиса $MAIN_MODULE..."
if ! python3 -m py_compile "/app/$MAIN_MODULE" 2>&1; then
    echo "[entrypoint] КРИТИЧЕСКАЯ ОШИБКА: синтаксическая ошибка в $MAIN_MODULE"
    echo "[entrypoint] Останавливаем контейнер (не restart loop). Исправьте код и пересоберите образ."
    exit 1
fi
echo "[entrypoint] Синтаксис OK."

# --- 2. Cleanup: убиваем зомби-процессы enhanced_orchestrator от предыдущих запусков ---
# ВАЖНО: проверяем только python-процессы через /proc/$pid/exe чтобы избежать false-positive
# (pgrep -f совпадает со своим bash-потомком, т.к. строка поиска содержит имя файла)
ZOMBIE_COUNT=0
for pid in $(ls /proc | grep -E '^[0-9]+$' 2>/dev/null); do
    exe=$(readlink /proc/$pid/exe 2>/dev/null || echo "")
    if echo "$exe" | grep -q "python"; then
        cmd=$(cat /proc/$pid/cmdline 2>/dev/null | tr '\0' ' ')
        if echo "$cmd" | grep -Fq "enhanced_orchestrator.py"; then
            ZOMBIE_COUNT=$((ZOMBIE_COUNT + 1))
        fi
    fi
done
if [ "$ZOMBIE_COUNT" -gt 0 ]; then
    echo "[entrypoint] Найдено $ZOMBIE_COUNT зомби-оркестраторов (только python) — чистим..."
    for pid in $(ls /proc | grep -E '^[0-9]+$' 2>/dev/null); do
        exe=$(readlink /proc/$pid/exe 2>/dev/null || echo "")
        if echo "$exe" | grep -q "python"; then
            cmd=$(cat /proc/$pid/cmdline 2>/dev/null | tr '\0' ' ')
            if echo "$cmd" | grep -Fq "enhanced_orchestrator.py"; then
                kill -9 $pid 2>/dev/null || true
            fi
        fi
    done
    echo "[entrypoint] Зомби-процессы убиты."
fi

# --- 3. Запускаем основной процесс ---
echo "[entrypoint] Запуск: $@"
exec "$@"

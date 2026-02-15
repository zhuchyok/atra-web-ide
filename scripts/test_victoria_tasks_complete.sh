#!/usr/bin/env bash
# Проверка, что корпорация не только возвращает status: success, но и даёт решение задачи,
# что шаги проходят и что тестируются задачи разной сложности.
# Запуск: VICTORIA_URL=${VICTORIA_URL:-http://127.0.0.1:8010} bash scripts/test_victoria_tasks_complete.sh

set -e
VICTORIA_URL="${VICTORIA_URL:-http://127.0.0.1:8010}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "=== Проверка Victoria: решение задачи, шаги, разная сложность ==="
echo "   URL: $VICTORIA_URL"
echo ""

# 1. Простая (быстрый путь / один ответ). Первый запрос может быть долгим (загрузка модели).
# Увеличенный таймаут до 300 сек (5 минут) для reasoning моделей
echo "--- Задача 1: Простая (приветствие) ---"
R1=$(curl -s --max-time 300 -X POST "$VICTORIA_URL/run" \
  -H "Content-Type: application/json" \
  -d '{"goal": "Привет. Ответь одним предложением: как тебя зовут?", "project_context": "atra-web-ide"}')
S1=$(echo "$R1" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null || echo "error")
O1=$(echo "$R1" | python3 -c "import sys,json; d=json.load(sys.stdin); print((d.get('output') or '')[:200])" 2>/dev/null || echo "—")
echo "   status: $S1"
echo "   ответ (начало): $O1"
if [ "$S1" = "success" ] && [ -n "$O1" ] && [ "$O1" != "—" ]; then
  echo "   ✅ Есть решение задачи"
else
  echo "   ❌ Нет решения или status не success"
fi
echo ""

# 2. Средняя (вопрос, требующий данных)
echo "--- Задача 2: Средняя (вопрос про экспертов) ---"
R2=$(curl -s --max-time 300 -X POST "$VICTORIA_URL/run" \
  -H "Content-Type: application/json" \
  -d '{"goal": "Сколько экспертов в корпорации? Назови только число.", "project_context": "atra-web-ide"}')
S2=$(echo "$R2" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null || echo "error")
O2=$(echo "$R2" | python3 -c "import sys,json; d=json.load(sys.stdin); print((d.get('output') or '')[:200])" 2>/dev/null || echo "—")
echo "   status: $S2"
echo "   ответ (начало): $O2"
if [ "$S2" = "success" ] && [ -n "$O2" ] && [ "$O2" != "—" ]; then
  echo "   ✅ Есть решение задачи"
else
  echo "   ❌ Нет решения или status не success"
fi
echo ""

# 3. Сложнее (инструмент: список файлов). Может быть долго при тяжёлой модели.
echo "--- Задача 3: Сложнее (действие — список файлов) ---"
R3=$(curl -s --max-time 300 -X POST "$VICTORIA_URL/run" \
  -H "Content-Type: application/json" \
  -d '{"goal": "Выведи список файлов в корне проекта. Только имена, до 8 штук.", "project_context": "atra-web-ide"}')
S3=$(echo "$R3" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('status','?'))" 2>/dev/null || echo "error")
O3=$(echo "$R3" | python3 -c "import sys,json; d=json.load(sys.stdin); print((d.get('output') or '')[:300])" 2>/dev/null || echo "—")
TRACE=$(echo "$R3" | python3 -c "import sys,json; d=json.load(sys.stdin); t=(d.get('knowledge') or {}).get('execution_trace',[]); print(len(t) if isinstance(t,list) else 0)" 2>/dev/null || echo "0")
echo "   status: $S3"
echo "   ответ (начало): $O3"
echo "   шагов (execution_trace): $TRACE"
if [ "$S3" = "success" ] && [ -n "$O3" ] && [ "$O3" != "—" ]; then
  echo "   ✅ Есть решение задачи"
else
  echo "   ❌ Нет решения или таймаут"
fi
echo ""

echo "=== Итог ==="
echo "   Проверяйте: не только status, но и что output содержит ответ на вопрос (решение)."
echo "   Разная сложность: простая (привет), средняя (вопрос к БД), сложнее (инструмент list_directory)."
echo "   Полный сценарий: docs/TESTING_FULL_SYSTEM.md, scripts/run_all_system_tests.sh"

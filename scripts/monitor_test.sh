#!/bin/bash
# Скрипт мониторинга теста создания сайта
# Проверяет статус каждые 5 минут

cd "$(dirname "$0")/.."

echo "📊 МОНИТОРИНГ ТЕСТА СОЗДАНИЯ САЙТА"
echo "Проверка каждые 5 минут..."
echo ""

while true; do
    clear
    echo "=========================================="
    echo "📊 СТАТУС ТЕСТА - $(date '+%H:%M:%S')"
    echo "=========================================="
    echo ""

    # Проверка процесса
    if ps aux | grep "run_website_test.py" | grep -v grep > /dev/null; then
        echo "✅ Тест выполняется"
    else
        echo "✅ Тест завершен"
        echo ""
        echo "📊 ФИНАЛЬНЫЕ РЕЗУЛЬТАТЫ:"
        python3 << 'PYEOF'
import json
import glob
import os
from datetime import datetime

trace_files = sorted(glob.glob("logs/task_trace_result_*.json"), reverse=True)
if trace_files:
    latest = trace_files[0]
    with open(latest) as f:
        data = json.load(f)

    print(f"   Файл: {os.path.basename(latest)}")
    print(f"   Длительность: {data.get('duration_seconds', 0):.1f}с ({data.get('duration_seconds', 0)/60:.1f} минут)")
    print(f"   Этапов: {len(data.get('stages', []))}")

    if data.get('stages'):
        last_stage = data['stages'][-1]
        if last_stage.get('stage') == 'TASK_COMPLETE':
            result = last_stage['data'].get('result', '')
            if result:
                print(f"   Результат: {len(result)} символов")
                if 'html' in result.lower() or '<html' in result.lower():
                    print(f"   ✅✅✅ СОДЕРЖИТ HTML!")
                else:
                    print(f"   ⚠️ Не содержит HTML")
PYEOF
        break
    fi

    # Статистика генераций
    GENERATIONS=$(tail -500 logs/mlx_api_server.log 2>/dev/null | grep -E "00:0[8-9]:|00:[1-5][0-9]:" | grep "Генерация завершена" | wc -l | tr -d ' ')
    echo "📊 Генераций: $GENERATIONS"

    # Последние 3 генерации
    echo ""
    echo "Последние генерации:"
    tail -500 logs/mlx_api_server.log 2>/dev/null | grep -E "00:0[8-9]:|00:[1-5][0-9]:" | grep "Генерация завершена" | tail -3 | sed 's/.*INFO.*| //' | sed 's/ (модель.*//'

    # MLX Server статус
    echo ""
    echo "MLX Server:"
    curl -s http://localhost:11435/health 2>/dev/null | python3 -c "import sys, json; d=json.load(sys.stdin); print(f\"   Статус: {d['status']}, активных: {d['active_requests']}/{d['max_concurrent']}, моделей: {d['models_cached']}\")" 2>/dev/null || echo "   Не отвечает"

    echo ""
    echo "Следующая проверка через 5 минут..."
    sleep 300
done

echo ""
echo "✅ Мониторинг завершен"

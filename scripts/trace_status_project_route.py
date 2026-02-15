#!/usr/bin/env python3
"""
Трассировка маршрута запроса «какой статус проекта?»:
- bridge: task_type, should_use_enhanced, is_curator_standard_goal
- enhanced (если доступен): category, method

Запуск из корня репо:
  python3 scripts/trace_status_project_route.py
  docker exec victoria-agent python -m scripts.trace_status_project_route  # из контейнера (если скрипт смонтирован)

Использование: после изменений в task_detector/victoria_server/victoria_enhanced — пересобрать образ
(docker compose -f knowledge_os/docker-compose.yml build victoria-agent) и при необходимости проверить путь.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

GOAL = "какой статус проекта?"

def main():
    print("Цель:", repr(GOAL))
    print()

    # 1) Маршрутизация в bridge (task_detector, victoria_server)
    from src.agents.bridge.task_detector import (
        detect_task_type,
        should_use_enhanced,
        is_curator_standard_goal,
    )
    task_type = detect_task_type(GOAL, "")
    use_enh = should_use_enhanced(GOAL, None, True)
    is_curator = is_curator_standard_goal(GOAL)
    print("[Bridge / task_detector]")
    print("  task_type:", task_type)
    print("  should_use_enhanced(goal, None, True):", use_enh)
    print("  is_curator_standard_goal(goal):", is_curator)
    print("  => Ожидание: task_type=enhanced, use_enhanced=True, is_curator=True")
    print("  => Тогда запрос не уйдёт в Veronica и пойдёт в Enhanced.")
    print()

    # 2) Классификация в Enhanced (victoria_enhanced) — если модуль доступен
    ko_path = ROOT / "knowledge_os"
    if ko_path.is_dir():
        if str(ko_path) not in sys.path:
            sys.path.insert(0, str(ko_path))
        try:
            from app.victoria_enhanced import VictoriaEnhanced
            # Только категория и метод, без полного solve (минимальная инициализация)
            inst = VictoriaEnhanced()
            category = inst._categorize_task(GOAL)
            method = inst._select_optimal_method(category, GOAL)
            print("[VictoriaEnhanced (локально)]")
            print("  category:", category)
            print("  method:", method)
            print("  => Ожидание: category=status_query, method=simple (тогда ответ из RAG/эталона).")
        except Exception as e:
            print("[VictoriaEnhanced] не удалось загрузить или вызвать:", e)
    else:
        print("[VictoriaEnhanced] knowledge_os не найден, пропуск категории/метода")

    print()
    print("Если в прогоне куратора ответ на «какой статус проекта?» — ReAct (thought + tool),")
    print("а не эталон (дашборд, MASTER_REFERENCE): пересоберите образ и перезапустите контейнер:")
    print("  docker compose -f knowledge_os/docker-compose.yml build victoria-agent")
    print("  docker compose -f knowledge_os/docker-compose.yml up -d victoria-agent")
    return 0

if __name__ == "__main__":
    sys.exit(main())

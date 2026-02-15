#!/usr/bin/env python3
"""
Тест детектора типа задачи (TaskTypeDetector).
Проверяет, что каждый тип запроса определяется правильно для маршрутизации Victoria.
"""
import sys
import os

# Добавляем корень проекта в path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.bridge.task_detector import detect_task_type, should_use_enhanced

# При PREFER_EXPERTS_FIRST=true (по умолчанию): «напиши/сделай» → enhanced (эксперты), не Veronica. См. VERONICA_REAL_ROLE, task_detector.
test_cases = [
    ("привет", "simple_chat"),
    ("здравствуй, как дела?", "simple_chat"),
    ("напиши функцию сортировки", "enhanced"),
    ("сделай проверку кода", "enhanced"),
    ("проанализируй данные продаж", "department_heads"),
    ("разработай стратегию", "department_heads"),
    ("разработай архитектуру системы", "enhanced"),
    ("покажи файлы в frontend", "veronica"),
    ("покажи список файлов в корне проекта", "veronica"),
]

def main():
    print("Запрос (первые 30 символов)              | Ожидалось           | Определено")
    print("-" * 85)
    ok = 0
    for goal, expected_type in test_cases:
        detected = detect_task_type(goal, "")
        use_enh = should_use_enhanced(goal, None, True)
        match = "✓" if detected == expected_type else "✗"
        if detected == expected_type:
            ok += 1
        print(f"{goal[:30]:30} | {expected_type:20} | {detected:20} {match}")
    print("-" * 85)
    print(f"Итого: {ok}/{len(test_cases)} тестов пройдено")
    return 0 if ok == len(test_cases) else 1

if __name__ == "__main__":
    sys.exit(main())

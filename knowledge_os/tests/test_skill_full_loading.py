import logging
import os
import sys

# Настройка путей
ko_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ko_path not in sys.path:
    sys.path.insert(0, ko_path)

from app.skill_mapper import get_skill_mapper

logging.basicConfig(level=logging.INFO)


def test_skill_loading():
    mapper = get_skill_mapper()

    # 1. Тест классификации
    goal = "Исправь баг в функции расчета прибыли"
    skill_info = mapper.classify_task(goal)
    print("\n--- Тест классификации ---")
    print(f"Goal: {goal}")
    print(f"Detected skill: {skill_info['skill'] if skill_info else 'None'}")

    if skill_info:
        # 2. Тест загрузки инструкций
        instructions = mapper.get_skill_instructions(skill_info["skill"])
        print("\n--- Тест загрузки инструкций ---")
        print(f"Instructions length: {len(instructions)}")
        print(f"Preview (first 200 chars):\n{instructions[:200]}...")

        # Проверка на наличие ключевых слов из SKILL.md (обычно там есть 'name:', 'description:')
        if "name:" in instructions or "description:" in instructions:
            print("\n✅ Успех: Загружен полный текст SKILL.md")
        else:
            print("\n❌ Ошибка: Похоже, загружен только fallback")


if __name__ == "__main__":
    test_skill_loading()

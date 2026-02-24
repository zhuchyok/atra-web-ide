#!/usr/bin/env python3
"""
Автоматическая генерация файлов экспертов в .cursor/rules/
на основе данных из БД и employees.json.

Запуск:
    python scripts/generate_cursor_rules.py

Использование:
    - При найме/увольнении: автоматически обновляет .cursor/rules/
    - Можно запускать вручную или в CI/CD
"""

import asyncio
import asyncpg
import json
from pathlib import Path
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/knowledge")
RULES_DIR = Path(__file__).parent.parent / ".cursor" / "rules"
EMPLOYEES_JSON = Path(__file__).parent.parent / "configs" / "experts" / "employees.json"

# Template для файлов экспертов
TEMPLATE = """---
description: "{name} - {role}"
alwaysApply: true
priority: {priority}
---

# {emoji} {name} - {role_upper}

## 🎯 ОСНОВНЫЕ ОБЯЗАННОСТИ
{responsibilities}

## 🔧 ТЕХНИЧЕСКИЙ СТЕК / КОМПЕТЕНЦИИ
{tech_stack}

## 📋 КЛЮЧЕВЫЕ ПРОЦЕССЫ
{processes}

## 🎪 ВЗАИМОДЕЙСТВИЕ С ДРУГИМИ РОЛЯМИ
{interactions}

## 💡 ПРИМЕРЫ ПРОМПТОВ

```
@{name} {example_prompt}
```

## ✅ КРИТЕРИИ КАЧЕСТВА
{quality_criteria}
"""

ROLE_TEMPLATES = {
    "Backend Developer": {
        "emoji": "💻",
        "responsibilities": "- Разработка API\n- Микросервисы\n- База данных\n- Тестирование",
        "tech_stack": "```python\nPython, FastAPI, PostgreSQL, Redis\n```",
        "processes": "1. API design\n2. Implementation\n3. Testing\n4. Deployment",
        "interactions": "- Frontend team\n- DevOps\n- QA",
        "example_prompt": "Создай REST API endpoint для...",
        "quality_criteria": "- Test coverage > 80%\n- Code review passed\n- Documentation updated"
    },
    "Frontend Developer": {
        "emoji": "🎨",
        "responsibilities": "- UI компоненты\n- State management\n- Responsive design\n- Тестирование",
        "tech_stack": "```typescript\nReact, TypeScript, TailwindCSS\n```",
        "processes": "1. Component design\n2. Implementation\n3. Testing\n4. Accessibility",
        "interactions": "- Backend team\n- UI/UX designers\n- QA",
        "example_prompt": "Создай компонент для...",
        "quality_criteria": "- Lighthouse score > 90\n- Accessibility WCAG 2.1 AA\n- Mobile-friendly"
    },
    # Можно добавить шаблоны для других ролей
}

DEFAULT_TEMPLATE = {
    "emoji": "👤",
    "responsibilities": "- Основная деятельность по роли\n- Специализированные задачи\n- Координация с командой",
    "tech_stack": "```\nИнструменты и технологии роли\n```",
    "processes": "1. Анализ задачи\n2. Выполнение\n3. Проверка качества\n4. Отчетность",
    "interactions": "- Взаимодействие с командой\n- Координация проектов",
    "example_prompt": "Выполни задачу по...",
    "quality_criteria": "- Качество работы\n- Соблюдение сроков\n- Документирование"
}


async def get_experts_from_db():
    """Получить всех экспертов из БД."""
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        experts = await conn.fetch("""
            SELECT
                id,
                name,
                role,
                department,
                system_prompt,
                metadata
            FROM experts
            ORDER BY name
        """)
        return [dict(e) for e in experts]
    finally:
        await conn.close()


def load_employees_json():
    """Загрузить список из employees.json."""
    if EMPLOYEES_JSON.exists():
        with open(EMPLOYEES_JSON) as f:
            data = json.load(f)
            return data.get("employees", [])
    return []


def normalize_filename(name: str) -> str:
    """Нормализовать имя для имени файла."""
    # Удаляем пробелы, приводим к нижнему регистру
    normalized = name.lower().replace(" ", "_").replace("ё", "e")
    # Транслитерация основных русских букв
    translit = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ж': 'zh',
        'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm', 'н': 'n',
        'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u', 'ф': 'f',
        'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch', 'ъ': '', 'ы': 'y',
        'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }
    for ru, en in translit.items():
        normalized = normalized.replace(ru, en)
    return normalized


def generate_file_content(employee: dict, priority: int) -> str:
    """Генерировать содержимое файла для эксперта."""
    name = employee["name"]
    role = employee["role"]

    # Выбираем шаблон по роли или используем default
    template_data = ROLE_TEMPLATES.get(role, DEFAULT_TEMPLATE)

    content = TEMPLATE.format(
        name=name,
        role=role,
        role_upper=role.upper(),
        priority=priority,
        emoji=template_data["emoji"],
        responsibilities=template_data["responsibilities"],
        tech_stack=template_data["tech_stack"],
        processes=template_data["processes"],
        interactions=template_data["interactions"],
        example_prompt=template_data["example_prompt"],
        quality_criteria=template_data["quality_criteria"]
    )

    return content


async def generate_rules_files():
    """Основная функция генерации файлов."""

    print("🔍 Загрузка данных экспертов...")

    # Загружаем из employees.json (основной источник)
    employees = load_employees_json()

    if not employees:
        print("❌ employees.json пуст или не найден")
        return

    print(f"✅ Найдено {len(employees)} экспертов")

    # Создаем директорию если не существует
    RULES_DIR.mkdir(parents=True, exist_ok=True)

    # Получаем существующие файлы
    existing_files = set(RULES_DIR.glob("*.md"))
    generated_files = set()

    # Генерируем файлы для каждого эксперта
    for idx, employee in enumerate(employees, start=1):
        name = employee["name"]
        role = employee["role"]

        # Формируем имя файла
        filename = f"{idx:02d}_{normalize_filename(name)}.md"
        filepath = RULES_DIR / filename
        generated_files.add(filepath)

        # Проверяем, существует ли файл
        if filepath.exists():
            print(f"⏭️  Пропускаем {filename} (уже существует)")
            continue

        # Генерируем содержимое
        content = generate_file_content(employee, priority=idx)

        # Записываем файл
        filepath.write_text(content, encoding="utf-8")
        print(f"✅ Создан {filename} - {name} ({role})")

    # Опционально: удалить файлы для уволенных
    obsolete_files = existing_files - generated_files - {RULES_DIR / "atra.mdc"}
    if obsolete_files:
        print("\n⚠️  Найдены устаревшие файлы:")
        for file in obsolete_files:
            print(f"   - {file.name}")
        response = input("Удалить? (y/N): ")
        if response.lower() == 'y':
            for file in obsolete_files:
                file.unlink()
                print(f"🗑️  Удален {file.name}")

    print(f"\n✅ Готово! Обработано {len(employees)} экспертов")
    print(f"📁 Папка: {RULES_DIR}")


if __name__ == "__main__":
    asyncio.run(generate_rules_files())

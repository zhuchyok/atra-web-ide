#!/usr/bin/env python3
"""
Скрипт для проверки прогресса обучения всех сотрудников.

Анализирует:
- Базы знаний
- Программы обучения
- Заполненность разделов
- Метрики обучения
"""

import logging
import re
import sys
from pathlib import Path
from typing import Dict, List, Tuple

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Маппинг имен (кириллица -> латиница для файлов)
NAME_MAPPING = {
    "Виктория": "viktoriya",
    "Дмитрий": "dmitriy",
    "Игорь": "igor",
    "Сергей": "sergey",
    "Анна": "anna",
    "Максим": "maxim",
    "Елена": "elena",
    "Алексей": "alexey",
    "Павел": "pavel",
    "Мария": "maria",
    "Роман": "roman",
    "Ольга": "olga",
    "Татьяна": "tatyana",
    "Екатерина": "ekaterina",
    "Андрей": "andrey",
    "София": "sofia",
    "Никита": "nikita",
    "Дарья": "daria",
    "Марина": "marina",
    "Юлия": "yuliya",
    "Артем": "artem",
    "Анастасия": "anastasiya",
}

# Список всех сотрудников
TEAM_MEMBERS = [
    ("Виктория", "Team Lead"),
    ("Дмитрий", "ML Engineer"),
    ("Игорь", "Backend Developer"),
    ("Сергей", "DevOps Engineer"),
    ("Анна", "QA Engineer"),
    ("Максим", "Data Analyst"),
    ("Елена", "Monitor"),
    ("Алексей", "Security Engineer"),
    ("Павел", "Trading Strategy Developer"),
    ("Мария", "Risk Manager"),
    ("Роман", "Database Engineer"),
    ("Ольга", "Performance Engineer"),
    ("Татьяна", "Technical Writer"),
    ("Екатерина", "Financial Analyst"),
    ("Андрей", "Frontend Developer"),
    ("София", "UI/UX Designer"),
    ("Никита", "Full-stack Developer"),
    ("Дарья", "SEO & AI Visibility Specialist"),
    ("Марина", "Content Manager"),
    ("Юлия", "Legal Counsel"),
    ("Артем", "Code Reviewer"),
    ("Анастасия", "Product Manager"),
]


def analyze_knowledge_base(kb_path: Path) -> Dict[str, any]:
    """Анализирует базу знаний сотрудника"""
    if not kb_path.exists():
        return {
            "exists": False,
            "responsibility_filled": False,
            "materials_filled": False,
            "knowledge_filled": False,
            "metrics_filled": False,
            "best_practices_filled": False,
        }
    
    try:
        content = kb_path.read_text(encoding='utf-8')
    except Exception as e:
        logger.error(f"Ошибка чтения {kb_path}: {e}")
        return {
            "exists": False,
            "responsibility_filled": False,
            "materials_filled": False,
            "knowledge_filled": False,
            "metrics_filled": False,
            "best_practices_filled": False,
        }
    
    # Проверяем заполненность области ответственности
    responsibility_section = ""
    if "ОБЛАСТЬ ОТВЕТСТВЕННОСТИ" in content:
        start_idx = content.find("ОБЛАСТЬ ОТВЕТСТВЕННОСТИ")
        end_idx = content.find("##", start_idx + 1)
        if end_idx == -1:
            end_idx = len(content)
        responsibility_section = content[start_idx:end_idx]
    
    responsibility_filled = (
        "ОБЛАСТЬ ОТВЕТСТВЕННОСТИ" in content and
        not bool(re.search(r'\[Будет добавлено в процессе обучения\]', responsibility_section, re.IGNORECASE)) and
        len(responsibility_section) > 100
    )
    
    # Проверяем заполненность изученных материалов
    materials_section = ""
    if "## 📖 ИЗУЧЕННЫЕ МАТЕРИАЛЫ" in content:
        start_idx = content.find("## 📖 ИЗУЧЕННЫЕ МАТЕРИАЛЫ")
        # Ищем следующий заголовок уровня 2 (##)
        next_header = content.find("\n## ", start_idx + 1)
        if next_header == -1:
            next_header = len(content)
        materials_section = content[start_idx:next_header]
    
    materials_empty = bool(re.search(
        r'\[Будет добавлено',
        materials_section,
        re.IGNORECASE
    ))
    # Проверяем наличие списков (маркеры -)
    list_items = len(re.findall(r'^-', materials_section, re.MULTILINE))
    materials_filled = not materials_empty and list_items > 0 and (
        "Книги" in materials_section or
        "Инструменты" in materials_section or
        "Практики" in materials_section
    )
    
    # Проверяем заполненность накопленных знаний
    knowledge_section = ""
    if "## 🧠 НАКОПЛЕННЫЕ ЗНАНИЯ" in content:
        start_idx = content.find("## 🧠 НАКОПЛЕННЫЕ ЗНАНИЯ")
        # Ищем следующий заголовок уровня 2 (##)
        next_header = content.find("\n## ", start_idx + 1)
        if next_header == -1:
            next_header = len(content)
        knowledge_section = content[start_idx:next_header]
    
    knowledge_empty = bool(re.search(
        r'\[Будет добавлено',
        knowledge_section,
        re.IGNORECASE
    ))
    # Проверяем наличие списков (маркеры -)
    list_items = len(re.findall(r'^-', knowledge_section, re.MULTILINE))
    knowledge_filled = not knowledge_empty and list_items > 0 and (
        "✅ Что уже знаю:" in knowledge_section or
        "🆕 Новые знания:" in knowledge_section or
        "⚠️ Проблемы и решения:" in knowledge_section
    )
    
    # Проверяем заполненность метрик
    metrics_filled = bool(re.search(
        r'Всего задач выполнено.*[1-9]\d*',
        content,
        re.IGNORECASE
    )) or bool(re.search(
        r'Успешных решений.*[1-9]\d*',
        content,
        re.IGNORECASE
    ))
    
    # Проверяем наличие лучших практик
    best_practices_filled = "🌐 ЛУЧШИЕ ПРАКТИКИ ИЗ ИНТЕРНЕТА" in content or "ЛУЧШИЕ ПРАКТИКИ" in content
    
    # Проверяем продвинутые материалы (экспертный уровень)
    advanced_materials_filled = "🚀 ПРОДВИНУТЫЕ МАТЕРИАЛЫ" in content
    
    # Проверяем реальные кейсы
    real_cases_filled = "💼 РЕАЛЬНЫЕ КЕЙСЫ" in content
    
    # Проверяем инновационные техники (максимум)
    innovation_techniques_filled = (
        "🚀 ИННОВАЦИОННЫЕ ТЕХНИКИ" in content or 
        "ИННОВАЦИОННЫЕ ТЕХНИКИ" in content or
        "## 🚀 ИННОВАЦИОННЫЕ" in content
    )
    
    # Проверяем публикации
    publications_filled = (
        "📝 ПУБЛИКАЦИИ" in content or
        "ПУБЛИКАЦИИ И ИССЛЕДОВАНИЯ" in content or
        "## 📝 ПУБЛИКАЦИИ" in content
    )
    
    # Проверяем менторство
    mentorship_filled = (
        "👨‍🏫 МЕНТОРСТВО" in content or 
        "МЕНТОРСТВО И ОБУЧЕНИЕ" in content or
        "## 👨‍🏫 МЕНТОРСТВО" in content
    )
    
    # Проверяем награды
    awards_filled = (
        "🏆 НАГРАДЫ" in content or 
        "НАГРАДЫ И ПРИЗНАНИЕ" in content or
        "## 🏆 НАГРАДЫ" in content
    )
    
    return {
        "exists": True,
        "responsibility_filled": responsibility_filled,
        "materials_filled": materials_filled,
        "knowledge_filled": knowledge_filled,
        "metrics_filled": metrics_filled,
        "best_practices_filled": best_practices_filled,
        "advanced_materials_filled": advanced_materials_filled,
        "real_cases_filled": real_cases_filled,
        "innovation_techniques_filled": innovation_techniques_filled,
        "publications_filled": publications_filled,
        "mentorship_filled": mentorship_filled,
        "awards_filled": awards_filled,
    }


def analyze_learning_program(program_path: Path) -> Dict[str, any]:
    """Анализирует программу обучения сотрудника"""
    if not program_path.exists():
        return {
            "exists": False,
            "filled": False,
        }
    
    try:
        content = program_path.read_text(encoding='utf-8')
    except Exception as e:
        logger.error(f"Ошибка чтения {program_path}: {e}")
        return {
            "exists": False,
            "filled": False,
        }
    
    # Проверяем заполненность программы
    program_empty = bool(re.search(
        r'\[Будет добавлено в процессе обучения\]',
        content,
        re.IGNORECASE
    ))
    program_filled = not program_empty and (
        ("Книги:" in content and len(re.findall(r'^- ', content)) > 0) or
        ("Практика:" in content and len(re.findall(r'^- ', content)) > 0) or
        ("ЦЕЛИ ОБУЧЕНИЯ" in content and len(content) > 500)
    )
    
    # Проверяем экспертный уровень
    expert_level = "🌟 ЭКСПЕРТНЫЙ УРОВЕНЬ" in content or "МИРОВОЙ КЛАСС" in content
    
    # Проверяем максимальный уровень
    maximum_level = (
        "🔥 МАКСИМАЛЬНЫЙ УРОВЕНЬ" in content or 
        "МАКСИМУМ" in content or
        "## 🔥 МАКСИМАЛЬНЫЙ" in content or
        "МАКСИМАЛЬНЫЙ УРОВЕНЬ" in content
    )
    
    return {
        "exists": True,
        "filled": program_filled,
        "expert_level": expert_level,
        "maximum_level": maximum_level,
    }


def calculate_learning_percentage(
    kb_analysis: Dict,
    program_analysis: Dict,
) -> Tuple[float, Dict[str, float]]:
    """Рассчитывает процент обучения"""
    details = {}
    total = 0.0
    
    # База знаний существует: 15% (базовый прогресс)
    if kb_analysis.get("exists"):
        details["База знаний создана"] = 15.0
        total += 15.0
    else:
        details["База знаний создана"] = 0.0
    
    # Область ответственности: 5%
    if kb_analysis.get("responsibility_filled"):
        details["Область ответственности"] = 5.0
        total += 5.0
    else:
        details["Область ответственности"] = 0.0
    
    # Изученные материалы: 20%
    if kb_analysis.get("materials_filled"):
        details["Изученные материалы"] = 20.0
        total += 20.0
    else:
        details["Изученные материалы"] = 0.0
    
    # Накопленные знания: 30%
    if kb_analysis.get("knowledge_filled"):
        details["Накопленные знания"] = 30.0
        total += 30.0
    else:
        details["Накопленные знания"] = 0.0
    
    # Метрики обучения: 10%
    if kb_analysis.get("metrics_filled"):
        details["Метрики обучения"] = 10.0
        total += 10.0
    else:
        details["Метрики обучения"] = 0.0
    
    # Лучшие практики: 5%
    if kb_analysis.get("best_practices_filled"):
        details["Лучшие практики"] = 5.0
        total += 5.0
    else:
        details["Лучшие практики"] = 0.0
    
    # Программа обучения существует: 10%
    if program_analysis.get("exists"):
        details["Программа создана"] = 10.0
        total += 10.0
    else:
        details["Программа создана"] = 0.0
    
    # Программа обучения заполнена: 10%
    if program_analysis.get("filled"):
        details["Программа заполнена"] = 10.0
        total += 10.0
    else:
        details["Программа заполнена"] = 0.0
    
    # Продвинутые материалы (экспертный уровень): +15%
    if kb_analysis.get("advanced_materials_filled"):
        details["Продвинутые материалы"] = 15.0
        total += 15.0
    else:
        details["Продвинутые материалы"] = 0.0
    
    # Реальные кейсы: +10%
    if kb_analysis.get("real_cases_filled"):
        details["Реальные кейсы"] = 10.0
        total += 10.0
    else:
        details["Реальные кейсы"] = 0.0
    
    # Экспертный уровень в программе: +10%
    if program_analysis.get("expert_level"):
        details["Экспертный уровень"] = 10.0
        total += 10.0
    else:
        details["Экспертный уровень"] = 0.0
    
    # Инновационные техники (максимум): +15%
    if kb_analysis.get("innovation_techniques_filled"):
        details["Инновационные техники"] = 15.0
        total += 15.0
    else:
        details["Инновационные техники"] = 0.0
    
    # Публикации и исследования: +10%
    if kb_analysis.get("publications_filled"):
        details["Публикации"] = 10.0
        total += 10.0
    else:
        details["Публикации"] = 0.0
    
    # Менторство: +10%
    if kb_analysis.get("mentorship_filled"):
        details["Менторство"] = 10.0
        total += 10.0
    else:
        details["Менторство"] = 0.0
    
    # Награды: +10%
    if kb_analysis.get("awards_filled"):
        details["Награды"] = 10.0
        total += 10.0
    else:
        details["Награды"] = 0.0
    
    # Максимальный уровень в программе: +10%
    if program_analysis.get("maximum_level"):
        details["Максимальный уровень"] = 10.0
        total += 10.0
    else:
        details["Максимальный уровень"] = 0.0
    
    return round(total, 1), details


def main():
    """Главная функция"""
    logger.info("🔍 Анализ прогресса обучения всех сотрудников...")
    
    scripts_dir = Path(__file__).parent
    learning_programs_dir = scripts_dir / "learning_programs"
    
    results = []
    
    for name, role in TEAM_MEMBERS:
        # Получаем латинское имя для файла
        file_name = NAME_MAPPING.get(name, name.lower())
        
        # Пути к файлам
        kb_path = scripts_dir / f"{file_name}_knowledge.md"
        program_path = learning_programs_dir / f"{file_name}_program.md"
        
        # Анализируем базу знаний
        kb_analysis = analyze_knowledge_base(kb_path)
        
        # Анализируем программу обучения
        program_analysis = analyze_learning_program(program_path)
        
        # Рассчитываем процент
        percentage, details = calculate_learning_percentage(kb_analysis, program_analysis)
        
        results.append({
            "name": name,
            "role": role,
            "percentage": percentage,
            "details": details,
            "kb_exists": kb_analysis.get("exists", False),
            "program_exists": program_analysis.get("exists", False),
        })
    
    # Сортируем по проценту (от большего к меньшему)
    results.sort(key=lambda x: x["percentage"], reverse=True)
    
    # Выводим таблицу
    print("\n" + "="*100)
    print("📊 ПРОГРЕСС ОБУЧЕНИЯ ВСЕХ СОТРУДНИКОВ")
    print("="*100)
    print()
    
    # Заголовок таблицы
    print(f"{'№':<4} {'Имя':<15} {'Роль':<30} {'Прогресс':<12} {'Статус':<10}")
    print("-" * 100)
    
    # Данные таблицы
    for i, result in enumerate(results, 1):
        name = result["name"]
        role = result["role"][:28]  # Обрезаем длинные роли
        percentage = result["percentage"]
        
        # Определяем статус
        if percentage >= 80:
            status = "🟢 Отлично"
        elif percentage >= 60:
            status = "🟡 Хорошо"
        elif percentage >= 40:
            status = "🟠 Средне"
        elif percentage >= 20:
            status = "🔴 Низко"
        else:
            status = "⚫ Начало"
        
        progress_bar = "█" * int(percentage / 5) + "░" * (20 - int(percentage / 5))
        
        print(f"{i:<4} {name:<15} {role:<30} {percentage:>5.1f}% {progress_bar:<12} {status:<10}")
    
    print("-" * 100)
    
    # Статистика
    total_members = len(results)
    avg_percentage = sum(r["percentage"] for r in results) / total_members if total_members > 0 else 0
    excellent = sum(1 for r in results if r["percentage"] >= 80)
    good = sum(1 for r in results if 60 <= r["percentage"] < 80)
    medium = sum(1 for r in results if 40 <= r["percentage"] < 60)
    low = sum(1 for r in results if 20 <= r["percentage"] < 40)
    start = sum(1 for r in results if r["percentage"] < 20)
    
    print()
    print("📈 СТАТИСТИКА:")
    print(f"   Всего сотрудников: {total_members}")
    print(f"   Средний прогресс: {avg_percentage:.1f}%")
    print(f"   🟢 Отлично (80%+): {excellent} ({excellent/total_members*100:.1f}%)")
    print(f"   🟡 Хорошо (60-79%): {good} ({good/total_members*100:.1f}%)")
    print(f"   🟠 Средне (40-59%): {medium} ({medium/total_members*100:.1f}%)")
    print(f"   🔴 Низко (20-39%): {low} ({low/total_members*100:.1f}%)")
    print(f"   ⚫ Начало (<20%): {start} ({start/total_members*100:.1f}%)")
    
    print()
    print("="*100)
    
    logger.info("✅ Анализ завершен!")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

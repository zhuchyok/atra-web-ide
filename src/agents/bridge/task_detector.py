"""
Детектор типа задачи для маршрутизации запросов Victoria.
Определяет: simple_chat (приветствия, простые вопросы) → быстрый путь без Enhanced;
veronica / department_heads / enhanced — для выбора обработчика.

Мировая практика (docs/VERONICA_REAL_ROLE.md): Veronica — «руки», не «решатель».
При PREFER_EXPERTS_FIRST=true (по умолчанию) в Veronica идут только простые
одношаговые запросы (покажи файлы, выведи список); остальные execution → enhanced,
чтобы Victoria сначала задействовала экспертов (85 в БД).
"""
import os
from typing import Optional


# Ключевые слова по типам (порядок проверки важен)
SIMPLE_CHAT_KEYWORDS = [
    "привет", "здравствуй", "приветствую", "добрый день", "добрый вечер", "доброе утро",
    "как дела", "что нового", "расскажи о себе", "кто ты", "чем занимаешься",
    "спасибо", "пожалуйста", "пока", "до свидания", "удачи", "хорошего дня",
    "приветствую", "здорово", "ок", "понятно", "ясно",
]

# Простые одношаговые запросы — реальная роль Veronica (руки): только показать/вывести/прочитать
VERONICA_SIMPLE_KEYWORDS = [
    "покажи файлы", "выведи список файлов", "список файлов", "покажи список",
    "прочитай файл", "покажи файл", "содержимое файла", "выведи содержимое",
    "сделай скриншот", "проверь как выглядит", "нажми на", "открой страницу",
    "визуальная проверка", "проверь ui", "проверь ux",
]

VERONICA_KEYWORDS = [
    "выполни", "сделай", "напиши код", "исправь код", "исправь", "напиши функцию",
    "запусти", "протестируй", "проверь код", "проверь", "собери", "установи", "настрой",
    "подготовь", "создай файл", "удали файл", "переименуй", "перемести файл",
    "покажи файлы", "выведи список файлов",
]

DEPARTMENT_HEADS_KEYWORDS = [
    "проанализируй", "разработай стратегию", "оптимизируй", "спроектируй",
    "планируй", "исследуй", "изучи", "оцени", "предложи решение", "найди проблему",
    "сравни", "обобщи", "систематизируй",
]

# Запросы куратора, которые должны идти в Enhanced (RAG/эталоны), не в Veronica
CURATOR_STANDARD_KEYWORDS = [
    "статус проекта", "какой статус", "дашборд", "что умеешь", "что ты умеешь",
    "status project", "project status", "dashboard", "what can you do",
]
def is_curator_standard_goal(goal: str) -> bool:
    """
    Запрос из списка кураторских эталонов: статус проекта, что умеешь, дашборд.
    Такие запросы не должны делегироваться в Veronica — только Enhanced (simple + RAG).
    """
    if not (goal or "").strip():
        return False
    g = (goal or "").lower().strip()
    if any(kw in g for kw in CURATOR_STANDARD_KEYWORDS):
        return True
    # «какой статус проекта?», «статус по проекту»
    if "статус" in g and ("проект" in g or "дашборд" in g):
        return True
    if "что" in g and "умеешь" in g:
        return True
    return False


def _is_simple_veronica_request(goal: str) -> bool:
    """
    Запрос — одношаговое действие (показать/вывести/прочитать).
    Только такие запросы по задумке идут сразу в Veronica (руки); остальные — в enhanced (эксперты).
    """
    if not goal or len(goal.strip()) > 120:
        return False
    goal_lower = goal.lower().strip()
    if any(kw in goal_lower for kw in VERONICA_SIMPLE_KEYWORDS):
        return True
    # Короткая фраза типа «покажи файлы в src»
    if len(goal_lower) <= 50 and ("покажи" in goal_lower or "выведи" in goal_lower or "список" in goal_lower):
        return True
    return False


def detect_task_type(goal: str, context: str = "") -> str:
    """
    Определяет тип задачи для маршрутизации:
    - simple_chat: приветствия, простые вопросы → быстрый путь (agent.run без Enhanced)
    - veronica: только простые одношаговые запросы (покажи файлы, выведи список) при PREFER_EXPERTS_FIRST
    - department_heads: аналитические/стратегические
    - enhanced: сложные задачи, execution через экспертов (по умолчанию для «сделай/напиши код»)
    """
    if not (goal or "").strip():
        return "simple_chat"
    goal_lower = goal.lower().strip()
    prefer_experts_first = os.getenv("PREFER_EXPERTS_FIRST", "true").lower() in ("true", "1", "yes")

    # Кураторские эталоны (статус проекта, что умеешь, дашборд) — всегда Enhanced (RAG/эталоны)
    if is_curator_standard_goal(goal):
        return "enhanced"

    # Простые одношаговые запросы → Veronica (реальная роль: руки)
    if _is_simple_veronica_request(goal):
        return "veronica"

    # Исполнительные ключевые слова: при PREFER_EXPERTS_FIRST — в enhanced (эксперты первыми)
    for word in VERONICA_KEYWORDS:
        if word in goal_lower:
            if prefer_experts_first:
                return "enhanced"
            return "veronica"
    # Эвристики: код — при PREFER_EXPERTS_FIRST в enhanced
    if _is_code_related(goal_lower):
        return "enhanced" if prefer_experts_first else "veronica"

    # Аналитические
    for word in DEPARTMENT_HEADS_KEYWORDS:
        if word in goal_lower:
            return "department_heads"
    # Очень короткие фразы — чаще всего приветствие
    if len(goal_lower) <= 25 and any(k in goal_lower for k in SIMPLE_CHAT_KEYWORDS):
        return "simple_chat"
    # Явные приветствия
    for word in SIMPLE_CHAT_KEYWORDS:
        if word in goal_lower:
            return "simple_chat"
    # Эвристики: анализ
    if _is_analysis_related(goal_lower):
        return "department_heads"
    return "enhanced"


def _is_code_related(goal: str) -> bool:
    code_indicators = [
        "python", "javascript", "java", "код", "функция", "класс", "метод",
        "библиотека", "импорт", "компиляция", "дебаг", "тест", "lint",
    ]
    return any(i in goal for i in code_indicators)


def _is_analysis_related(goal: str) -> bool:
    analysis_indicators = [
        "данные", "анализ", "отчет", "отчёт", "график", "диаграмма",
        "статистика", "тренд", "паттерн", "корреляция", "прогноз",
        "рекомендация", "метрика", "insight",
    ]
    return any(i in goal for i in analysis_indicators)


def should_use_enhanced(goal: str, project_context: Optional[str], use_enhanced_env: bool) -> bool:
    """
    Решает, использовать ли Enhanced для данного запроса.
    Если env USE_VICTORIA_ENHANCED=true, но запрос — simple_chat, возвращаем False
    (быстрый ответ через agent.run без тяжёлого Enhanced).
    """
    if not use_enhanced_env:
        return False
    task_type = detect_task_type(goal or "", project_context or "")
    return task_type != "simple_chat"

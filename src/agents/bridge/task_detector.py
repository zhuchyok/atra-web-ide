"""
Детектор типа задачи для маршрутизации запросов Victoria.
Определяет: simple_chat (приветствия, простые вопросы) → быстрый путь без Enhanced;
veronica / department_heads / enhanced — для выбора обработчика.
"""
from typing import Optional


# Ключевые слова по типам (порядок проверки важен)
SIMPLE_CHAT_KEYWORDS = [
    "привет", "здравствуй", "приветствую", "добрый день", "добрый вечер", "доброе утро",
    "как дела", "что нового", "расскажи о себе", "кто ты", "чем занимаешься",
    "спасибо", "пожалуйста", "пока", "до свидания", "удачи", "хорошего дня",
    "приветствую", "здорово", "ок", "понятно", "ясно",
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


def detect_task_type(goal: str, context: str = "") -> str:
    """
    Определяет тип задачи для маршрутизации:
    - simple_chat: приветствия, простые вопросы → быстрый путь (agent.run без Enhanced)
    - veronica: исполнительные задачи (код, файлы, команды)
    - department_heads: аналитические/стратегические
    - enhanced: сложные комплексные задачи (по умолчанию)
    """
    if not (goal or "").strip():
        return "simple_chat"
    goal_lower = goal.lower().strip()
    # Исполнительные задачи (до simple_chat, чтобы "покажи файлы" не матчилось по "пока")
    for word in VERONICA_KEYWORDS:
        if word in goal_lower:
            return "veronica"
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
    # Эвристики: код
    if _is_code_related(goal_lower):
        return "veronica"
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

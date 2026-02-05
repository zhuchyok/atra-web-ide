"""
Strategic Question Classifier
Классификация вопросов как стратегических для передачи Совету Директоров
"""
from typing import Tuple


# Ключевые слова для стратегических вопросов
STRATEGIC_KEYWORDS = [
    # Архитектура
    "архитектур", "микросервис", "монолит", "структур", "дизайн систем",
    "масштабирован", "распределенн",
    
    # Приоритеты и планирование
    "приоритет", "приоритизир", "фокус", "направлен", "стратег", "планиро",
    "roadmap", "дорожн карт", "okr", "цел",
    
    # Рефакторинг и изменения
    "рефактор", "переписать", "переработать", "изменить подход", "переделать",
    "legacy", "технический долг", "debt",
    
    # Технологии и выбор
    "технологи", "фреймворк", "библиотек", "язык программ", "выбрать",
    "стоит ли использовать", "какую", "какой выбрать", "альтернатив",
    
    # Бюджет и ресурсы
    "бюджет", "стоимость", "ресурс", "команд", "нанять", "затрат",
    
    # Сроки и deadline
    "срок", "deadline", "когда", "как быстро", "успеть", "времен",
    
    # Качество vs скорость
    "качество", "скорость", "быстр", "надежн", "стабильн",
    "производительност", "оптимизац",
    
    # Стратегические вопросы
    "стоит ли", "нужно ли", "правильно ли", "лучше", "оптимальн",
    "рекомендуе", "советуе"
]

# Анти-ключевые слова (не стратегические)
NON_STRATEGIC_KEYWORDS = [
    # Приветствия и простые вопросы
    "привет", "здравствуй", "добрый день", "как дела", "что умеешь",
    "спасибо", "thank", "пока", "bye",
    
    # Простые факты
    "что такое", "определение", "расшифруй", "объясни простыми словами",
    
    # Простой код
    "как написать", "пример код", "синтаксис", "функция для", 
    "покажи код", "как сделать простой"
]


def is_strategic_question(content: str) -> Tuple[bool, str]:
    """
    Классифицирует вопрос как стратегический.
    
    Args:
        content: Текст вопроса пользователя
    
    Returns:
        Tuple[bool, str]: (is_strategic, reason)
        - bool: True если вопрос стратегический
        - str: причина классификации для логирования
    """
    content_lower = content.lower().strip()
    
    # 1. Проверка длины (очень короткие вопросы обычно не стратегические)
    if len(content_lower) < 15:
        return False, "too_short"
    
    # 2. Анти-ключевые слова (явно не стратегические)
    for keyword in NON_STRATEGIC_KEYWORDS:
        if keyword in content_lower:
            return False, f"non_strategic_keyword:{keyword}"
    
    # 3. Поиск стратегических ключевых слов
    strategic_matches = []
    for keyword in STRATEGIC_KEYWORDS:
        if keyword in content_lower:
            strategic_matches.append(keyword)
    
    # 4. Эвристика: если есть 2+ стратегических ключевых слова → стратегический
    if len(strategic_matches) >= 2:
        return True, f"strategic_keywords:{','.join(strategic_matches[:3])}"
    
    # 5. Эвристика: если есть 1 ключевое слово + вопросительный знак → стратегический
    if len(strategic_matches) >= 1 and '?' in content_lower:
        return True, f"strategic_keyword_with_question:{strategic_matches[0]}"
    
    # 6. Эвристика: если есть "стоит ли" / "нужно ли" + длина > 30 → стратегический
    if any(phrase in content_lower for phrase in ["стоит ли", "нужно ли", "правильно ли"]) and len(content_lower) > 30:
        return True, "strategic_phrase"
    
    # 7. Эвристика: вопросы про выбор ("какой лучше", "выбрать X или Y")
    if any(phrase in content_lower for phrase in ["какой лучше", "что лучше", "выбрать", "или"]) and len(content_lower) > 40:
        # Проверяем, что это не простой технический вопрос
        if not any(word in content_lower for word in ["синтаксис", "пример", "как написать", "функция"]):
            return True, "strategic_choice"
    
    # 8. По умолчанию: не стратегический
    return False, "no_strategic_indicators"


def get_risk_level_from_question(content: str) -> str:
    """
    Оценивает риск-уровень вопроса для предварительной оценки.
    
    Returns:
        "low" | "medium" | "high"
    """
    content_lower = content.lower()
    
    # Высокий риск: архитектура, безопасность, бюджет
    high_risk_keywords = [
        "архитектур", "безопасност", "security", "бюджет", "миграци",
        "переписать всё", "удалить", "заменить полностью"
    ]
    if any(kw in content_lower for kw in high_risk_keywords):
        return "high"
    
    # Средний риск: рефакторинг, технологии, изменения
    medium_risk_keywords = [
        "рефактор", "технологи", "фреймворк", "изменить", "переработать",
        "приоритет", "срок"
    ]
    if any(kw in content_lower for kw in medium_risk_keywords):
        return "medium"
    
    # Низкий риск по умолчанию
    return "low"

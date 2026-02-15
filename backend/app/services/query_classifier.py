"""
QueryClassifier — классификация запроса для градации путей (горячий путь / RAG / full).
Используется в режиме Ask: simple → шаблон, factual → RAG-light (позже), complex → Agent.
"""
import re
import random
import logging
from typing import Dict, Optional, List

logger = logging.getLogger(__name__)

# Паттерны для простых запросов (приветствия, благодарность, прощание)
SIMPLE_PATTERNS = [
    r"привет|здравствуй|здравствуйте|добрый\s+(день|вечер|утро)",
    r"хай|hello|hi\b|hey\b",
    r"как\s+дела|как\s+ты|как\s+сам",
    r"спасибо|благодарю|thanks|thank\s+you",
    r"пока|до\s+свидания|bye|goodbye",
    r"ок|хорошо|понятно|ясно\b",
    r"отлично|супер|круто\b",
]
# Информационные запросы — быстрый путь без LLM (что умеешь, кто ты, чем помочь)
INFORMATIONAL_PATTERNS = [
    r"что\s+(ты\s+)?умеешь|что\s+умеешь",
    r"кто\s+ты|представься|расскажи\s+о\s+себе",
    r"чем\s+(можешь\s+)?помочь|твои?\s+возможности|чем\s+занимаешься",
    r"what\s+can\s+you\s+do|who\s+are\s+you|your\s+capabilities",
]

# Паттерны для фактуальных вопросов (короткий ответ, возможно с RAG)
FACTUAL_PATTERNS = [
    r"сколько|когда|где\b|как\s+сделать|как\s+настроить",
    r"что\s+такое|кто\s+такой|что\s+значит",
    r"какой\s+(порт|url|адрес)|какой\s+верси",
]

# Максимальная длина для рассмотрения как "простой" (символы)
SIMPLE_MAX_LEN = 80

# Варианты шаблонных ответов (случайный выбор для разнообразия)
TEMPLATE_RESPONSES: Dict[str, List[str]] = {
    "привет": [
        "Привет! Чем могу помочь?",
        "Здравствуйте! Готов помочь с вопросами.",
        "Приветствую! Задавайте свой вопрос.",
    ],
    "как дела": [
        "Всё отлично, работаю в полную силу!",
        "Спасибо, хорошо. А у вас?",
        "Отлично, готов помогать вам!",
    ],
    "спасибо": [
        "Всегда рад помочь!",
        "Пожалуйста! Обращайтесь ещё.",
        "Рад был помочь!",
    ],
    "пока": [
        "До свидания! Хорошего дня.",
        "Всего доброго!",
        "Пока! Буду ждать ваших вопросов.",
    ],
    "понятно": [
        "Хорошо. Если что-то ещё понадобится — пишите.",
        "Понятно. Обращайтесь, если появятся вопросы.",
    ],
    "что умеешь": [
        "Я Виктория, Team Lead Atra Core. Отвечаю на вопросы, составляю планы, помогаю с кодом и архитектурой. "
        "Могу вызывать экспертов, искать в базе знаний, анализировать проект. Переключитесь в режим «Чат» для быстрых ответов или «План» для пошаговых планов.",
        "Я — ИИ-агент Singularity 10.0. Помогаю с задачами: чат, планирование, анализ кода, RAG по базе знаний, вызов экспертов. "
        "В режиме «Агент» — полный ReAct с шагами; в «Чат» — быстрее для простых вопросов.",
    ],
}


def classify_query(query: str) -> Dict[str, str | float]:
    """
    Определяет тип запроса: simple, factual, complex.

    Returns:
        {"type": "simple"|"factual"|"complex", "confidence": 0.0-1.0}
    """
    if not query or not query.strip():
        return {"type": "simple", "confidence": 0.95}

    text = query.strip().lower()
    # Информационные («что умеешь», «кто ты») — простой путь без LLM
    for pattern in INFORMATIONAL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return {"type": "simple", "confidence": 0.95}
    # Простые приветствия / короткие реплики
    if len(text) <= SIMPLE_MAX_LEN:
        for pattern in SIMPLE_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return {"type": "simple", "confidence": 0.95}
    # Фактуальные вопросы
    for pattern in FACTUAL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return {"type": "factual", "confidence": 0.85}
    # По умолчанию — сложный (полный анализ, Agent)
    return {"type": "complex", "confidence": 0.7}


def get_template_response(query: str, expert_name: Optional[str] = None) -> Optional[str]:
    """
    Возвращает шаблонный ответ для простых запросов (горячий путь, без LLM).
    Использует TEMPLATE_RESPONSES для разнообразия; при отсутствии ключа — общий ответ.
    Если запрос не распознан как шаблонный — возвращает None.
    """
    classification = classify_query(query)
    if classification["type"] != "simple":
        return None

    text = query.strip().lower()
    expert = (expert_name or "Виктория").strip()

    # Приветствия — из набора вариантов
    if re.search(r"привет|здравствуй|хай|hello|hi\b|hey\b|добрый", text):
        return random.choice(TEMPLATE_RESPONSES["привет"])
    if re.search(r"как\s+дела|как\s+ты|как\s+сам", text):
        return random.choice(TEMPLATE_RESPONSES["как дела"])
    if re.search(r"спасибо|благодарю|thanks|thank", text):
        return random.choice(TEMPLATE_RESPONSES["спасибо"])
    if re.search(r"пока|до\s+свидания|bye|goodbye", text):
        return random.choice(TEMPLATE_RESPONSES["пока"])
    if re.search(r"^ок$|^хорошо$|^понятно$|^ясно$|^отлично$|^супер$|^круто$", text):
        return random.choice(TEMPLATE_RESPONSES["понятно"])

    # Информационные: что умеешь, кто ты, чем помочь
    for pattern in INFORMATIONAL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return random.choice(TEMPLATE_RESPONSES["что умеешь"])

    return random.choice(TEMPLATE_RESPONSES["привет"])


# Паттерны и ключевые слова для рекомендации перейти в режим Агент (Фаза 2, день 3–4)
COMPLEX_KEYWORDS = [
    "анализ", "сравнение", "оценка", "рекомендация", "стратегия", "план",
    "оптимизация", "улучшение", "диагностика", "отладка", "исследование",
]
COMPLEX_VERBS = [
    "проанализируй", "сравни", "оцени", "рекомендуй", "разработай",
    "оптимизируй", "улучши", "диагностируй", "исследуй",
]
COMPLEX_CONNECTORS = [
    "если", "то", "иначе", "потому что", "так как", "следовательно", "поэтому",
]
AGENT_SUGGESTION_THRESHOLD = 0.6
MAX_COMPLEXITY_SIGNALS = 2.5  # нормализация: один глагол (1.5) даёт score 0.6


def analyze_complexity(query: str) -> Dict:
    """
    Анализ сложности запроса для рекомендации перейти в режим Агент.
    Возвращает результат classify_query + suggest_agent, complexity_score, complexity_reason.
    """
    base = classify_query(query)
    query_lower = (query or "").strip().lower()
    complexity_signals = 0.0
    reasons: List[str] = []

    # Рекомендация только для complex-запросов
    if base.get("type") != "complex":
        return {
            **base,
            "suggest_agent": False,
            "complexity_score": 0.0,
            "complexity_reason": "",
        }

    # Ключевые слова
    for kw in COMPLEX_KEYWORDS:
        if kw in query_lower:
            complexity_signals += 1.0
            reasons.append(f"ключевое слово: {kw}")
            break
    # Глаголы
    for verb in COMPLEX_VERBS:
        if verb in query_lower:
            complexity_signals += 1.5
            reasons.append(f"глагол: {verb}")
            break
    # Связки
    for conn in COMPLEX_CONNECTORS:
        if conn in query_lower:
            complexity_signals += 0.5
            reasons.append("логические связки")
            break
    # Длина
    words = len(query_lower.split())
    if words > 15:
        complexity_signals += 1.0
        reasons.append(f"длинный запрос ({words} слов)")
    # Несколько вопросов
    if query_lower.count("?") > 1:
        complexity_signals += 1.0
        reasons.append("несколько вопросов")

    score = min(complexity_signals / MAX_COMPLEXITY_SIGNALS, 1.0)
    suggest = score >= AGENT_SUGGESTION_THRESHOLD
    reason_text = "; ".join(reasons[:3]) if reasons else "запрос средней сложности"

    return {
        **base,
        "suggest_agent": suggest,
        "complexity_score": round(score, 2),
        "complexity_reason": reason_text,
    }

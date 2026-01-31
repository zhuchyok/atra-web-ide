"""
Общий валидатор результата задачи.
Используется: Task Distribution (manager_review), Smart Worker (проверка после выполнения).
Часть оптимальной архитектуры: единая проверка в цепочке БД и реалтайм.
"""
import logging
from typing import Tuple

logger = logging.getLogger(__name__)


def validate_task_result(description: str, result: str) -> Tuple[bool, float]:
    """
    Проверить результат задачи по описанию/требованиям.
    
    Args:
        description: Описание задачи или требования (title + description).
        result: Результат выполнения.
    
    Returns:
        (is_valid, score) — прошла ли проверка и оценка 0.0..1.0.
    """
    if not result or not isinstance(result, str) or len(result.strip()) == 0:
        return False, 0.0
    
    result_lower = result.strip().lower()
    desc_lower = (description or "").strip().lower()
    
    # Индикаторы ошибки в ответе
    error_indicators = [
        '⚠️', '❌', '⌛', 'error', 'failed', 'недоступен', 'не могу',
        'все источники недоступны', 'ошибка связи', 'не удалось'
    ]
    if any(ind in result_lower for ind in error_indicators):
        return False, 0.2
    
    # Базовая релевантность: есть ли пересечение слов с задачей
    relevance_score = 0.5
    if desc_lower:
        req_words = set(desc_lower.split())
        res_words = set(result_lower.split())
        common = req_words.intersection(res_words)
        if common:
            relevance_score += min(len(common) / max(len(req_words), 1), 0.3)
    
    # Длина результата
    if len(result.strip()) >= 100:
        relevance_score += 0.1
    if len(result.strip()) >= 500:
        relevance_score += 0.1
    
    final_score = min(relevance_score, 0.95)
    is_valid = final_score >= 0.5
    
    return is_valid, final_score

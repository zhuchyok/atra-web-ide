"""
Task Trace Hooks - Перехватчики для детального трейсинга задач
Отслеживает выбор моделей, промпты, решения на всех этапах

Best practices:
- Graceful degradation при недоступности tracer
- Явная обработка всех ошибок
- Гарантированное логирование через fallback
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Глобальный трейсер (будет установлен из тестового скрипта)
_global_tracer = None


def set_tracer(tracer):
    """Установить глобальный трейсер"""
    global _global_tracer
    _global_tracer = tracer


def log_model_selection(
    who: str,
    task: str,
    selected_model: str,
    reason: str,
    available_models: Optional[List[str]] = None,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """
    Логировать выбор модели.

    Best practice: Безопасное логирование с обработкой ошибок.

    Args:
        who: Кто выбирает модель
        task: Описание задачи
        selected_model: Выбранная модель
        reason: Причина выбора
        available_models: Доступные модели
        context: Дополнительный контекст
    """
    try:
        # Всегда логируем через обычный logger (fallback)
        logger.info(
            f"🤖 [MODEL SELECTION] {who} → '{selected_model}' | "
            f"Задача: '{task[:50]}...' | Причина: {reason}"
        )

        if context:
            logger.debug(f"   Контекст: {json.dumps(context, ensure_ascii=False, indent=2)}")

        # Пытаемся логировать через tracer (если доступен)
        if _global_tracer:
            try:
                _global_tracer.log_model_selection(
                    who, task, selected_model, reason, available_models or [], context or {}
                )
            except Exception as tracer_error:
                # Логируем ошибку, но не прерываем выполнение
                logger.warning(f"⚠️ Ошибка при логировании в tracer: {tracer_error}", exc_info=True)
    except Exception as e:
        # Критическая ошибка - логируем, но не прерываем выполнение
        logger.error(f"❌ Критическая ошибка при логировании выбора модели: {e}", exc_info=True)


def log_prompt(who: str, stage: str, prompt: str, model: str = None):
    """Логировать промпт"""
    if _global_tracer:
        _global_tracer.log_prompt(who, stage, prompt, model)

    logger.debug(f"💬 [PROMPT] {who} ({stage}) → Модель: {model or 'N/A'}")
    logger.debug(f"   Промпт ({len(prompt)} символов):\n{prompt[:500]}...")


def log_decision(who: str, decision: str, reason: str, data: dict = None):
    """Логировать решение"""
    if _global_tracer:
        _global_tracer.log_decision(who, decision, reason, data)

    logger.info(f"🎯 [DECISION] {who}: {decision} | Причина: {reason}")
    if data:
        logger.debug(f"   Данные: {json.dumps(data, ensure_ascii=False, indent=2)}")


def log_stage(stage_name: str, data: dict):
    """Логировать этап"""
    if _global_tracer:
        _global_tracer.log_stage(stage_name, data)

    logger.info(f"📋 [STAGE] {stage_name}: {json.dumps(data, ensure_ascii=False, indent=2)}")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль генерации сигналов
Вынесен из signal_live.py для рефакторинга

Примечание: Основная функция generate_signal остается в signal_live.py
для обратной совместимости. Этот модуль реэкспортирует её.
"""

import logging

logger = logging.getLogger(__name__)

# Реэкспорт функции generate_signal из ядра
try:
    from src.signals.core import generate_signal_base as generate_signal
    __all__ = ['generate_signal']
    logger.debug("✅ generate_signal_base импортирован из src.signals.core")
except ImportError as e:
    logger.error("❌ Ошибка импорта generate_signal_base: %s", e)

    async def generate_signal(*args, **kwargs):
        """Заглушка для generate_signal"""
        logger.error("generate_signal недоступен (ошибка импорта)")
        return None, None

    __all__ = ['generate_signal']

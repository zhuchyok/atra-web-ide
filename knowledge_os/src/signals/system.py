#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль основной системы сигналов
Вынесен из signal_live.py для рефакторинга

Примечание: Основная функция run_hybrid_signal_system_fixed остается в signal_live.py
для обратной совместимости. Этот модуль реэкспортирует её.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Dict, Optional

from src.signals.core import run_hybrid_signal_system_fixed

logger = logging.getLogger(__name__)

_SIGNAL_FUNCS: Optional[Dict[str, Callable[..., Awaitable]]] = None


def _load_signal_functions() -> Dict[str, Callable[..., Awaitable]]:
    """
    Ленивая загрузка функций из signal_live, чтобы избежать циклических импортов.
    """
    global _SIGNAL_FUNCS  # noqa: PLW0603
    if _SIGNAL_FUNCS is not None:
        return _SIGNAL_FUNCS

    try:
        from signal_live import (  # noqa: WPS433
            process_symbol_signals as _process_symbol_signals,
            health_check_correlations as _health_check_correlations,
            periodic_health_check_correlations as _periodic_health_check_correlations,
        )
    except ImportError as exc:
        logger.error("❌ Не удалось импортировать функции системы сигналов: %s", exc)
        raise

    def _ensure_async(func: Callable[..., Awaitable]) -> Callable[..., Awaitable]:
        if asyncio.iscoroutinefunction(func):
            return func

        logger.warning("ℹ️ Функция %s не async. Оборачиваем в корутину.", func.__name__)

        async def _wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return _wrapper

    _SIGNAL_FUNCS = {
        "process": _ensure_async(_process_symbol_signals),
        "health": _ensure_async(_health_check_correlations),
        "periodic": _ensure_async(_periodic_health_check_correlations),
    }
    logger.debug("✅ Функции системы сигналов загружены из signal_live.py")
    return _SIGNAL_FUNCS


async def process_symbol_signals(*args, **kwargs):
    funcs = _load_signal_functions()
    return await funcs["process"](*args, **kwargs)


async def health_check_correlations(*args, **kwargs):
    funcs = _load_signal_functions()
    return await funcs["health"](*args, **kwargs)


async def periodic_health_check_correlations(*args, **kwargs):
    funcs = _load_signal_functions()
    return await funcs["periodic"](*args, **kwargs)


__all__ = [
    "run_hybrid_signal_system_fixed",
    "process_symbol_signals",
    "health_check_correlations",
    "periodic_health_check_correlations",
]


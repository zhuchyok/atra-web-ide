#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль отправки сигналов.

Здесь реализуется ленивое подключение фактической реализации `send_signal`
из `signal_live.py`, чтобы исключить циклические импорты во время старта
основного приложения (main.py).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable, Optional

logger = logging.getLogger(__name__)

_SEND_SIGNAL_IMPL: Optional[Callable[..., Awaitable[bool]]] = None


def _load_send_signal() -> Callable[..., Awaitable[bool]]:
    """
    Импортирует реализацию send_signal из signal_live при первом обращении.
    Используем внутренний импорт, чтобы избежать частично инициализированного
    модуля во время старта системы.
    """
    global _SEND_SIGNAL_IMPL  # noqa: PLW0603

    if _SEND_SIGNAL_IMPL is not None:
        return _SEND_SIGNAL_IMPL

    try:
        from signal_live import send_signal as _send_signal  # noqa: WPS433
    except ImportError as exc:
        logger.error("❌ Не удалось импортировать send_signal: %s", exc)
        raise
    else:
        if not asyncio.iscoroutinefunction(_send_signal):
            logger.warning(
                "ℹ️ send_signal (%s) не является асинхронной функцией. Оборачиваем в корутину.",
                type(_send_signal),
            )

            async def _async_wrapper(*args, **kwargs) -> bool:
                return _send_signal(*args, **kwargs)

            _SEND_SIGNAL_IMPL = _async_wrapper
        else:
            _SEND_SIGNAL_IMPL = _send_signal

        logger.debug("✅ send_signal успешно загружен из signal_live.py")
        return _SEND_SIGNAL_IMPL


async def send_signal(*args, **kwargs) -> bool:
    """
    Ленивая обертка над send_signal из signal_live.py.
    """
    impl = _load_send_signal()
    return await impl(*args, **kwargs)


__all__ = ["send_signal"]

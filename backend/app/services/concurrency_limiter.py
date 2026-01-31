"""
Ограничение одновременных запросов к Victoria (снижение 500 при нагрузке).
При перегрузке возвращаем 503 вместо обрушения бэкенда.
"""
import asyncio
import logging
from typing import AsyncGenerator, TypeVar

from app.config import get_settings

logger = logging.getLogger(__name__)

_semaphore: asyncio.Semaphore | None = None
_wait_sec: float = 45.0


def _ensure_semaphore() -> asyncio.Semaphore:
    global _semaphore, _wait_sec
    if _semaphore is None:
        s = get_settings()
        limit = getattr(s, "max_concurrent_victoria", 25)
        _wait_sec = getattr(s, "victoria_concurrent_wait_sec", 45.0)
        _semaphore = asyncio.Semaphore(limit)
        logger.info("Concurrency limiter: max_concurrent_victoria=%s, wait_sec=%s", limit, _wait_sec)
    return _semaphore


async def acquire_victoria_slot() -> bool:
    """
    Захватить слот на запрос к Victoria (с таймаутом).
    Returns:
        True — слот получен, False — таймаут (нужно вернуть 503).
    """
    sem = _ensure_semaphore()
    try:
        await asyncio.wait_for(sem.acquire(), timeout=_wait_sec)
        return True
    except asyncio.TimeoutError:
        logger.warning("Victoria concurrency limit: wait timeout (%.0fs)", _wait_sec)
        return False


def release_victoria_slot() -> None:
    """Освободить слот после завершения запроса к Victoria."""
    sem = _ensure_semaphore()
    sem.release()


T = TypeVar("T")


async def with_victoria_slot(agen: AsyncGenerator[T, None]) -> AsyncGenerator[T, None]:
    """Обёртка над async generator: освобождает слот в finally."""
    try:
        async for x in agen:
            yield x
    finally:
        release_victoria_slot()

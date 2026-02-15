"""
Общий HTTP-клиент для переиспользования соединений (мировая практика: connection pooling).

Вместо создания httpx.AsyncClient() на каждый запрос используем один клиент на процесс
с лимитами (max_connections, keepalive). При миграции на Rust здесь можно подставить
обёртку над Rust HTTP-клиентом с тем же контрактом: get_client() -> client.
"""
import asyncio
import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

# Лимиты по умолчанию: не перегружать Ollama/внешние сервисы, переиспользовать соединения
DEFAULT_LIMITS = httpx.Limits(
    max_keepalive_connections=20,
    max_connections=50,
    keepalive_expiry=30.0,
)

_client: Optional[httpx.AsyncClient] = None
_lock = asyncio.Lock()


async def get_http_client(limits: Optional[httpx.Limits] = None) -> httpx.AsyncClient:
    """Ленивая инициализация общего клиента. Потокобезопасно."""
    global _client
    async with _lock:
        if _client is None or _client.is_closed:
            if _client is not None and _client.is_closed:
                logger.debug("Shared HTTP client was closed, re-initializing")
            _client = httpx.AsyncClient(
                limits=limits or DEFAULT_LIMITS,
                timeout=httpx.Timeout(10.0),
            )
            logger.debug("Shared HTTP client initialized")
        return _client


async def close_http_client() -> None:
    """Закрыть клиент (вызывать при shutdown приложения)."""
    global _client
    async with _lock:
        if _client is not None:
            await _client.aclose()
            _client = None
            logger.debug("Shared HTTP client closed")

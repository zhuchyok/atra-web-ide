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


def _http2_available() -> bool:
    """Return True when optional http2 dependency is installed."""
    try:
        import h2  # type: ignore  # noqa: F401

        return True
    except Exception:
        return False


async def get_http_client(limits: Optional[httpx.Limits] = None) -> httpx.AsyncClient:
    """Ленивая инициализация общего клиента. Потокобезопасно."""
    global _client
    async with _lock:
        if _client is None or _client.is_closed:
            if _client is not None and _client.is_closed:
                logger.debug("Shared HTTP client was closed, re-initializing")
            use_http2 = _http2_available()
            _client = httpx.AsyncClient(
                limits=limits or DEFAULT_LIMITS,
                timeout=httpx.Timeout(10.0),
                # Keep HTTP/2 optimization when h2 is available; otherwise fallback safely.
                http2=use_http2,
            )
            if not use_http2:
                logger.info("Shared HTTP client: h2 not installed, using HTTP/1.1 fallback")
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

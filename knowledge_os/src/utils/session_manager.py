import asyncio
import logging
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


class SessionManager:
    _instance: Optional["SessionManager"] = None
    _session: Optional[aiohttp.ClientSession] = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SessionManager, cls).__new__(cls)
        return cls._instance

    async def get_session(self) -> aiohttp.ClientSession:
        async with self._lock:
            if self._session is None or self._session.closed:
                timeout = aiohttp.ClientTimeout(total=60, connect=15, sock_read=30)
                self._session = aiohttp.ClientSession(timeout=timeout)
                logger.info("🆕 Создана новая общая aiohttp сессия")
            return self._session

    async def close(self):
        async with self._lock:
            if self._session and not self._session.closed:
                await self._session.close()
                self._session = None
                logger.info("🛑 Общая aiohttp сессия закрыта")


session_manager = SessionManager()

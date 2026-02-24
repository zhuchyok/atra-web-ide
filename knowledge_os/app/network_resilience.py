"""
Network Resilience Module - устойчивость к потере интернета
Обеспечивает работу системы даже при отсутствии интернета
"""

import asyncio
import logging
import os
import socket
from functools import wraps
from typing import Any, Callable, Optional

import httpx

logger = logging.getLogger(__name__)


class NetworkResilience:
    """Класс для обеспечения устойчивости к потере интернета"""

    def __init__(self):
        self.internet_available = True
        self.last_check = None
        self.check_interval = 60  # Проверка каждую минуту
        self.local_only_mode = False

    async def check_internet(self, timeout: float = 3.0) -> bool:
        """
        Проверка доступности интернета

        Args:
            timeout: Таймаут проверки в секундах

        Returns:
            True если интернет доступен, False иначе
        """
        try:
            # Пробуем подключиться к надежным DNS серверам
            test_hosts = [
                ("8.8.8.8", 53),  # Google DNS
                ("1.1.1.1", 53),  # Cloudflare DNS
                ("208.67.222.222", 53),  # OpenDNS
            ]

            for host, port in test_hosts:
                try:
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(timeout)
                    result = sock.connect_ex((host, port))
                    sock.close()
                    if result == 0:
                        self.internet_available = True
                        self.last_check = asyncio.get_event_loop().time()
                        return True
                except Exception:
                    continue

            # Если не удалось подключиться к DNS, пробуем HTTP запрос
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.get("http://www.google.com", follow_redirects=True)
                    if response.status_code == 200:
                        self.internet_available = True
                        self.last_check = asyncio.get_event_loop().time()
                        return True
            except Exception:
                pass

            self.internet_available = False
            self.last_check = asyncio.get_event_loop().time()
            return False

        except Exception as e:
            logger.warning(f"⚠️ Ошибка проверки интернета: {e}")
            self.internet_available = False
            return False

    async def ensure_internet_check(self):
        """Проверяет интернет если прошло достаточно времени"""
        if self.last_check is None:
            await self.check_internet()
        else:
            elapsed = asyncio.get_event_loop().time() - self.last_check
            if elapsed > self.check_interval:
                await self.check_internet()

    def is_internet_available(self) -> bool:
        """Возвращает последний известный статус интернета"""
        return self.internet_available

    def set_local_only_mode(self, enabled: bool):
        """Включает/выключает режим только локальных моделей"""
        self.local_only_mode = enabled
        logger.info(f"🌐 Режим только локальных моделей: {'включен' if enabled else 'выключен'}")


# Глобальный экземпляр
_network_resilience = NetworkResilience()


def network_aware(func: Callable) -> Callable:
    """
    Декоратор для функций, которые требуют интернет
    Автоматически проверяет доступность интернета и обрабатывает ошибки
    """

    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Проверяем интернет перед выполнением
        await _network_resilience.ensure_internet_check()

        if not _network_resilience.is_internet_available():
            logger.warning("⚠️ Интернет недоступен, функция может не работать")

        try:
            return await func(*args, **kwargs)
        except (
            httpx.HTTPError,
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.NetworkError,
            OSError,
            ConnectionError,
        ) as e:
            # Сетевая ошибка - проверяем интернет
            logger.warning(f"🌐 Сетевая ошибка в {func.__name__}: {e}")
            await _network_resilience.check_internet()

            if not _network_resilience.is_internet_available():
                logger.error(f"❌ Интернет недоступен, {func.__name__} не может выполниться")
                raise ConnectionError(f"Интернет недоступен: {e}")

            # Интернет доступен, но была ошибка - пробуем еще раз
            logger.info(f"🔄 Повторная попытка {func.__name__} после проверки интернета")
            return await func(*args, **kwargs)

    return wrapper


async def safe_http_request(
    url: str, method: str = "GET", timeout: float = 10.0, max_retries: int = 3, **kwargs
) -> Optional[httpx.Response]:
    """
    Безопасный HTTP запрос с обработкой сетевых ошибок

    Args:
        url: URL для запроса
        method: HTTP метод
        timeout: Таймаут запроса
        max_retries: Максимальное количество попыток
        **kwargs: Дополнительные параметры для httpx

    Returns:
        Response объект или None если не удалось выполнить запрос
    """
    is_local = url.startswith(
        ("http://localhost", "http://127.0.0.1", "http://host.docker.internal")
    )
    if not is_local:
        await _network_resilience.ensure_internet_check()

    if not _network_resilience.is_internet_available() and not is_local:
        logger.warning(f"⚠️ Интернет недоступен, пропускаем запрос к {url}")
        return None

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                if method.upper() == "GET":
                    response = await client.get(url, **kwargs)
                elif method.upper() == "POST":
                    response = await client.post(url, **kwargs)
                else:
                    response = await client.request(method, url, **kwargs)

                return response

        except (
            httpx.HTTPError,
            httpx.TimeoutException,
            httpx.ConnectError,
            httpx.NetworkError,
            OSError,
            ConnectionError,
        ) as e:
            logger.warning(f"🌐 Сетевая ошибка (попытка {attempt + 1}/{max_retries}): {e}")

            if attempt < max_retries - 1:
                # Проверяем интернет перед следующей попыткой
                await _network_resilience.check_internet()
                if not _network_resilience.is_internet_available() and not url.startswith(
                    ("http://localhost", "http://127.0.0.1", "http://host.docker.internal")
                ):
                    logger.error(f"❌ Интернет недоступен, прекращаем попытки для {url}")
                    return None

                # Экспоненциальная задержка
                delay = 2**attempt
                await asyncio.sleep(delay)
            else:
                logger.error(f"❌ Не удалось выполнить запрос к {url} после {max_retries} попыток")
                return None

    return None


def get_network_resilience() -> NetworkResilience:
    """Возвращает глобальный экземпляр NetworkResilience"""
    return _network_resilience

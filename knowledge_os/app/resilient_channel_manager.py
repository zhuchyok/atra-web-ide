"""
Resilient Channel Manager - система дублированных каналов с автоматическим переключением.

Обеспечивает:
- Дублирование критических каналов (Ollama, MLX, Database, etc.)
- Автоматическое переключение при сбоях
- Health checks всех каналов
- Автоматическое восстановление
- Мониторинг и метрики
"""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


class ChannelStatus(Enum):
    """Статус канала"""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class Channel:
    """Канал связи"""

    name: str
    url: str
    priority: int  # 1 = высший приоритет
    health_check_url: Optional[str] = None
    health_check_func: Optional[Callable] = None
    status: ChannelStatus = ChannelStatus.UNKNOWN
    last_check: Optional[datetime] = None
    failure_count: int = 0
    success_count: int = 0
    last_success: Optional[datetime] = None
    last_failure: Optional[datetime] = None
    avg_response_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.health_check_url is None:
            # Автоматически определяем health check URL
            if "/api/" in self.url:
                self.health_check_url = self.url.replace("/api/chat", "/api/tags").replace(
                    "/api/generate", "/api/tags"
                )
            else:
                self.health_check_url = (
                    f"{self.url}/health" if not self.url.endswith("/") else f"{self.url}health"
                )


class ResilientChannelManager:
    """
    Менеджер дублированных каналов с автоматическим переключением.

    Принципы:
    1. Дублирование: несколько каналов для одной функции
    2. Health checks: постоянный мониторинг состояния
    3. Автоматическое переключение: при сбое переключается на резервный
    4. Автоматическое восстановление: попытки восстановить упавший канал
    5. Метрики: отслеживание производительности
    """

    def __init__(
        self,
        health_check_interval: int = 30,
        failure_threshold: int = 3,
        recovery_attempt_interval: int = 60,
        max_response_time: float = 5.0,
    ):
        self.channels: Dict[str, List[Channel]] = {}
        self.active_channels: Dict[str, Channel] = {}
        self.health_check_interval = health_check_interval
        self.failure_threshold = failure_threshold
        self.recovery_attempt_interval = recovery_attempt_interval
        self.max_response_time = max_response_time
        self.monitoring_active = False
        self._monitoring_task: Optional[asyncio.Task] = None
        self._stats: Dict[str, Dict[str, Any]] = {}

    def register_channel(
        self,
        service_name: str,
        name: str,
        url: str,
        priority: int = 1,
        health_check_url: Optional[str] = None,
        health_check_func: Optional[Callable] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Регистрация канала для сервиса"""
        if service_name not in self.channels:
            self.channels[service_name] = []
            self._stats[service_name] = {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "switches": 0,
                "recoveries": 0,
            }

        channel = Channel(
            name=name,
            url=url,
            priority=priority,
            health_check_url=health_check_url,
            health_check_func=health_check_func,
            metadata=metadata or {},
        )

        self.channels[service_name].append(channel)
        self.channels[service_name].sort(key=lambda x: x.priority)

        if service_name not in self.active_channels:
            self.active_channels[service_name] = channel

        logger.info(
            f"✅ [RESILIENT] Зарегистрирован канал {name} для {service_name} (приоритет: {priority})"
        )

    async def check_channel_health(self, channel: Channel) -> Tuple[bool, float]:
        """Проверка здоровья канала"""
        start_time = time.time()

        try:
            if channel.health_check_func:
                result = await channel.health_check_func(channel)
                response_time = (time.time() - start_time) * 1000
                return result, response_time

            if channel.health_check_url:
                async with httpx.AsyncClient(timeout=5.0) as client:
                    response = await client.get(channel.health_check_url)
                    response_time = (time.time() - start_time) * 1000
                    is_healthy = response.status_code == 200

                    if "api/tags" in channel.health_check_url:
                        try:
                            data = response.json()
                            is_healthy = is_healthy and "models" in data
                        except:
                            is_healthy = False

                    return is_healthy, response_time

            logger.warning(f"⚠️ [RESILIENT] Канал {channel.name} не имеет health check")
            return True, (time.time() - start_time) * 1000

        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            logger.debug(f"⚠️ [RESILIENT] Health check для {channel.name} провалился: {e}")
            return False, response_time

    async def get_best_channel(self, service_name: str) -> Optional[Channel]:
        """Получить лучший доступный канал для сервиса"""
        if service_name not in self.channels:
            return None

        channels = self.channels[service_name]

        for channel in channels:
            await self.update_channel_status(channel)

        active_channel = self.active_channels.get(service_name)
        if active_channel and active_channel.status == ChannelStatus.HEALTHY:
            return active_channel

        healthy_channels = [c for c in channels if c.status == ChannelStatus.HEALTHY]
        if healthy_channels:
            best_channel = min(healthy_channels, key=lambda x: x.priority)
            if best_channel != active_channel:
                logger.info(
                    f"🔄 [RESILIENT] Переключение {service_name}: {active_channel.name if active_channel else 'None'} → {best_channel.name}"
                )
                self.active_channels[service_name] = best_channel
                self._stats[service_name]["switches"] += 1
            return best_channel

        if channels:
            best_channel = min(channels, key=lambda x: x.priority)
            if best_channel != active_channel:
                self.active_channels[service_name] = best_channel
                self._stats[service_name]["switches"] += 1
            return best_channel

        return None

    async def update_channel_status(self, channel: Channel):
        """Обновление статуса канала"""
        is_healthy, response_time = await self.check_channel_health(channel)

        channel.last_check = datetime.now()
        channel.avg_response_time = (channel.avg_response_time * 0.9) + (response_time * 0.1)

        if is_healthy:
            channel.success_count += 1
            channel.last_success = datetime.now()

            if channel.status == ChannelStatus.UNHEALTHY:
                logger.info(f"✅ [RESILIENT] Канал {channel.name} восстановлен!")
                channel.status = ChannelStatus.HEALTHY
                channel.failure_count = 0
            elif channel.status == ChannelStatus.UNKNOWN:
                channel.status = ChannelStatus.HEALTHY
            elif response_time > self.max_response_time * 1000:
                channel.status = ChannelStatus.DEGRADED
            else:
                channel.status = ChannelStatus.HEALTHY
        else:
            channel.failure_count += 1
            channel.last_failure = datetime.now()

            if channel.failure_count >= self.failure_threshold:
                channel.status = ChannelStatus.UNHEALTHY
                logger.warning(
                    f"⚠️ [RESILIENT] Канал {channel.name} помечен как UNHEALTHY ({channel.failure_count} провалов)"
                )
            elif channel.failure_count >= self.failure_threshold // 2:
                channel.status = ChannelStatus.DEGRADED

    async def execute_with_fallback(
        self, service_name: str, func: Callable, *args, **kwargs
    ) -> Any:
        """Выполнить функцию с автоматическим fallback"""
        self._stats[service_name]["total_requests"] += 1

        channels = self.channels.get(service_name, [])
        if not channels:
            raise ValueError(f"Нет зарегистрированных каналов для {service_name}")

        for channel in sorted(channels, key=lambda x: x.priority):
            try:
                result = await func(channel, *args, **kwargs)
                self._stats[service_name]["successful_requests"] += 1

                if self.active_channels.get(service_name) != channel:
                    logger.info(f"🔄 [RESILIENT] Переключение {service_name} на {channel.name}")
                    self.active_channels[service_name] = channel
                    self._stats[service_name]["switches"] += 1

                return result

            except Exception as e:
                logger.warning(f"⚠️ [RESILIENT] Канал {channel.name} провалился: {e}")
                self._stats[service_name]["failed_requests"] += 1
                channel.failure_count += 1
                channel.last_failure = datetime.now()

                if self.active_channels.get(service_name) == channel:
                    channel.status = ChannelStatus.UNHEALTHY
                continue

        raise Exception(f"Все каналы для {service_name} провалились")

    async def start_monitoring(self):
        """Запуск фонового мониторинга"""
        if self.monitoring_active:
            return

        self.monitoring_active = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("✅ [RESILIENT] Мониторинг каналов запущен")

    async def _monitoring_loop(self):
        """Основной цикл мониторинга"""
        while self.monitoring_active:
            try:
                for service_name, channels in self.channels.items():
                    for channel in channels:
                        await self.update_channel_status(channel)

                        if channel.status == ChannelStatus.UNHEALTHY:
                            if channel.last_failure:
                                time_since_failure = (
                                    datetime.now() - channel.last_failure
                                ).total_seconds()
                                if time_since_failure >= self.recovery_attempt_interval:
                                    logger.info(
                                        f"🔄 [RESILIENT] Попытка восстановления канала {channel.name}"
                                    )
                                    is_healthy, _ = await self.check_channel_health(channel)
                                    if is_healthy:
                                        channel.status = ChannelStatus.HEALTHY
                                        channel.failure_count = 0
                                        self._stats[service_name]["recoveries"] += 1
                                        logger.info(
                                            f"✅ [RESILIENT] Канал {channel.name} восстановлен!"
                                        )

                await asyncio.sleep(self.health_check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ [RESILIENT] Ошибка в цикле мониторинга: {e}")
                await asyncio.sleep(5)

    def get_stats(self, service_name: Optional[str] = None) -> Dict[str, Any]:
        """Получить статистику"""
        if service_name:
            return {
                "service": service_name,
                "stats": self._stats.get(service_name, {}),
                "channels": [
                    {
                        "name": c.name,
                        "status": c.status.value,
                        "priority": c.priority,
                        "failure_count": c.failure_count,
                        "avg_response_time_ms": c.avg_response_time,
                    }
                    for c in self.channels.get(service_name, [])
                ],
                "active_channel": self.active_channels.get(service_name).name
                if service_name in self.active_channels
                else None,
            }
        else:
            return {
                "services": list(self.channels.keys()),
                "stats": self._stats,
                "monitoring_active": self.monitoring_active,
            }


_resilient_manager: Optional[ResilientChannelManager] = None


def get_resilient_manager() -> ResilientChannelManager:
    """Получить глобальный экземпляр"""
    global _resilient_manager
    if _resilient_manager is None:
        _resilient_manager = ResilientChannelManager()
        asyncio.create_task(_resilient_manager.start_monitoring())
    return _resilient_manager

import asyncio
import logging
from typing import Any, Dict

import docker

logger = logging.getLogger(__name__)


class ContainerIsolationManager:
    """
    Автоматически изолирует аномальные контейнеры.
    Реализует карантин и троттлинг.
    """

    def __init__(self):
        try:
            self.client = docker.from_env()
            self.quarantine_net = "quarantine-net"
            self._ensure_quarantine()
        except Exception as e:
            self.client = None
            logger.error(f"❌ IsolationManager error: {e}")

    def _ensure_quarantine(self):
        if not self.client:
            return
        try:
            self.client.networks.get(self.quarantine_net)
        except docker.errors.NotFound:
            self.client.networks.create(self.quarantine_net, driver="bridge", internal=True)
            logger.info(f"🛡️ Создана сеть карантина: {self.quarantine_net}")

    async def isolate_container(self, container_name: str, severity: str):
        """Применяет меры изоляции в зависимости от тяжести."""
        if not self.client:
            return

        try:
            container = self.client.containers.get(container_name)

            if severity == "critical":
                logger.error(f"☣️ [QUARANTINE] Изоляция агрессора: {container_name}")
                # Отключаем от всех сетей и переводим в карантин
                for net_name in container.attrs["NetworkSettings"]["Networks"].keys():
                    self.client.networks.get(net_name).disconnect(container)
                self.client.networks.get(self.quarantine_net).connect(container)

            elif severity == "high":
                logger.warning(f"📉 [THROTTLING] Ограничение ресурсов: {container_name}")
                # Троттлинг до 10% CPU
                container.update(cpu_period=100000, cpu_quota=10000)

        except Exception as e:
            logger.error(f"❌ Ошибка при изоляции {container_name}: {e}")


_manager = None


def get_isolation_manager():
    global _manager
    if _manager is None:
        _manager = ContainerIsolationManager()
    return _manager

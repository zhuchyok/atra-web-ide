"""
Service Monitor - Мониторинг сервисов (Docker, HTTP, процессы)
Основано на Clawdbot + интеграция с SelfCheckSystem
Публикует события в Event Bus при изменениях статуса сервисов
"""

import asyncio
import logging
import httpx
import subprocess
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum

from app.event_bus import get_event_bus, Event, EventType

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Статус сервиса"""
    UP = "up"
    DOWN = "down"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class Service:
    """Информация о сервисе"""
    name: str
    service_type: str  # "docker", "http", "process"
    endpoint: Optional[str] = None  # URL для HTTP или имя контейнера/процесса
    port: Optional[int] = None
    health_check_path: Optional[str] = None  # Путь для health check (например, "/health")
    check_interval: int = 30  # Интервал проверки в секундах
    timeout: int = 5  # Таймаут проверки в секундах


class ServiceMonitor:
    """
    Service Monitor - мониторинг сервисов с публикацией событий
    
    Мониторит:
    - Docker контейнеры
    - HTTP сервисы (health checks)
    - Процессы
    
    Интегрируется с SelfCheckSystem для автоматического исправления
    """
    
    def __init__(
        self,
        services: Optional[List[Service]] = None,
        check_interval: int = 30
    ):
        """
        Инициализация Service Monitor
        
        Args:
            services: Список сервисов для мониторинга
            check_interval: Интервал проверки в секундах
        """
        self.services: Dict[str, Service] = {}
        self.service_statuses: Dict[str, ServiceStatus] = {}
        self.check_interval = check_interval
        self.event_bus = get_event_bus()
        self.running = False
        self._monitoring_task: Optional[asyncio.Task] = None
        
        # Добавляем сервисы по умолчанию
        default_services = self._get_default_services()
        all_services = (services or []) + default_services
        
        for service in all_services:
            self.add_service(service)
        
        logger.info(f"✅ Service Monitor инициализирован: {len(self.services)} сервисов")
    
    def _get_default_services(self) -> List[Service]:
        """Получить список сервисов по умолчанию для мониторинга"""
        return [
            Service(
                name="Victoria Agent",
                service_type="http",
                endpoint="http://localhost:8010",
                port=8010,
                health_check_path="/health"
            ),
            Service(
                name="Veronica Agent",
                service_type="http",
                endpoint="http://localhost:8011",
                port=8011,
                health_check_path="/health"
            ),
            Service(
                name="MLX API Server",
                service_type="http",
                endpoint="http://localhost:11435",
                port=11435,
                health_check_path="/health",
                check_interval=10,
                timeout=5
            ),
            Service(
                name="MLX API Server (legacy)",
                service_type="http",
                endpoint="http://localhost:11435",
                port=11435,
                health_check_path="/health"
            ),
            Service(
                name="Backend",
                service_type="http",
                endpoint="http://localhost:8080",
                port=8080,
                health_check_path="/health"
            ),
            Service(
                name="Frontend",
                service_type="http",
                endpoint="http://localhost:3002",
                port=3002
            ),
            Service(
                name="PostgreSQL",
                service_type="docker",
                endpoint="knowledge_postgres",
                port=5432
            ),
            Service(
                name="Redis",
                service_type="docker",
                endpoint="redis",  # имя сервиса в compose; контейнер — knowledge_os_redis
                port=6379
            ),
        ]
    
    def add_service(self, service: Service):
        """Добавить сервис для мониторинга"""
        self.services[service.name] = service
        self.service_statuses[service.name] = ServiceStatus.UNKNOWN
        logger.info(f"➕ Сервис добавлен: {service.name} ({service.service_type})")
    
    def remove_service(self, service_name: str):
        """Удалить сервис из мониторинга"""
        if service_name in self.services:
            del self.services[service_name]
            if service_name in self.service_statuses:
                del self.service_statuses[service_name]
            logger.info(f"➖ Сервис удален: {service_name}")
    
    async def check_service(self, service: Service) -> ServiceStatus:
        """Проверить статус сервиса"""
        try:
            if service.service_type == "http":
                return await self._check_http_service(service)
            elif service.service_type == "docker":
                return await self._check_docker_service(service)
            elif service.service_type == "process":
                return await self._check_process_service(service)
            else:
                logger.warning(f"⚠️ Неизвестный тип сервиса: {service.service_type}")
                return ServiceStatus.UNKNOWN
        except Exception as e:
            logger.error(f"❌ Ошибка проверки сервиса {service.name}: {e}")
            return ServiceStatus.UNKNOWN
    
    async def _check_http_service(self, service: Service) -> ServiceStatus:
        """Проверить HTTP сервис"""
        if not service.endpoint:
            return ServiceStatus.UNKNOWN
        
        try:
            url = service.endpoint
            if service.health_check_path:
                url = f"{service.endpoint}{service.health_check_path}"
            
            async with httpx.AsyncClient(timeout=service.timeout) as client:
                response = await client.get(url)
                
                if response.status_code == 200:
                    return ServiceStatus.UP
                elif response.status_code in [503, 502]:
                    return ServiceStatus.DEGRADED
                else:
                    return ServiceStatus.DOWN
        except httpx.TimeoutException:
            logger.warning(f"⏱️ Таймаут проверки {service.name}")
            return ServiceStatus.DOWN
        except httpx.ConnectError:
            return ServiceStatus.DOWN
        except Exception as e:
            logger.error(f"❌ Ошибка проверки HTTP сервиса {service.name}: {e}")
            return ServiceStatus.UNKNOWN
    
    async def _check_docker_service(self, service: Service) -> ServiceStatus:
        """Проверить Docker контейнер"""
        if not service.endpoint:
            return ServiceStatus.UNKNOWN
        
        try:
            # Проверяем статус контейнера через docker ps
            result = subprocess.run(
                ["docker", "ps", "--filter", f"name={service.endpoint}", "--format", "{{.Status}}"],
                capture_output=True,
                text=True,
                timeout=service.timeout
            )
            
            if result.returncode == 0 and result.stdout.strip():
                status_line = result.stdout.strip()
                if "Up" in status_line:
                    return ServiceStatus.UP
                elif "Exited" in status_line or "Restarting" in status_line:
                    return ServiceStatus.DEGRADED
                else:
                    return ServiceStatus.DOWN
            else:
                return ServiceStatus.DOWN
        except subprocess.TimeoutExpired:
            logger.warning(f"⏱️ Таймаут проверки Docker контейнера {service.name}")
            return ServiceStatus.DOWN
        except FileNotFoundError:
            logger.warning("⚠️ Docker не найден в PATH")
            return ServiceStatus.UNKNOWN
        except Exception as e:
            logger.error(f"❌ Ошибка проверки Docker сервиса {service.name}: {e}")
            return ServiceStatus.UNKNOWN
    
    async def _check_process_service(self, service: Service) -> ServiceStatus:
        """Проверить процесс"""
        if not service.endpoint:
            return ServiceStatus.UNKNOWN
        
        try:
            # Проверяем наличие процесса через pgrep
            result = subprocess.run(
                ["pgrep", "-f", service.endpoint],
                capture_output=True,
                timeout=service.timeout
            )
            
            if result.returncode == 0:
                return ServiceStatus.UP
            else:
                return ServiceStatus.DOWN
        except subprocess.TimeoutExpired:
            return ServiceStatus.DOWN
        except Exception as e:
            logger.error(f"❌ Ошибка проверки процесса {service.name}: {e}")
            return ServiceStatus.UNKNOWN
    
    async def _publish_status_change(self, service: Service, old_status: ServiceStatus, new_status: ServiceStatus):
        """Опубликовать событие об изменении статуса"""
        if old_status == new_status:
            return
        
        # Определяем тип события
        if new_status == ServiceStatus.DOWN:
            event_type = EventType.SERVICE_DOWN
        elif new_status == ServiceStatus.UP and old_status == ServiceStatus.DOWN:
            event_type = EventType.SERVICE_UP
        else:
            event_type = EventType.SERVICE_HEALTH_CHECK
        
        event = Event(
            event_id=f"service_{service.name}_{new_status.value}",
            event_type=event_type,
            payload={
                "service_name": service.name,
                "service_type": service.service_type,
                "old_status": old_status.value,
                "new_status": new_status.value,
                "endpoint": service.endpoint,
                "port": service.port
            },
            source="service_monitor"
        )
        
        await self.event_bus.publish(event)
        logger.info(f"📢 Статус {service.name}: {old_status.value} → {new_status.value}")
        
        # Автоматический перезапуск для MLX API Server через Supervisor
        if service.name == "MLX API Server" and new_status == ServiceStatus.DOWN:
            await self._try_restart_mlx_server()
    
    async def _try_restart_mlx_server(self):
        """Попытка перезапуска MLX Server через Supervisor"""
        try:
            from app.mlx_server_supervisor import get_mlx_supervisor
            
            supervisor = get_mlx_supervisor()
            status = supervisor.get_status()
            
            # Если supervisor не запущен, запускаем его
            if not status["running"]:
                logger.info("🔄 [SERVICE MONITOR] Запуск MLX Server Supervisor для автоматического перезапуска...")
                await supervisor.start()
            else:
                logger.info("ℹ️ [SERVICE MONITOR] MLX Server Supervisor уже запущен, перезапуск произойдет автоматически")
                
        except ImportError:
            logger.warning("⚠️ [SERVICE MONITOR] MLX Server Supervisor не доступен, автоматический перезапуск невозможен")
        except Exception as e:
            logger.error(f"❌ [SERVICE MONITOR] Ошибка при попытке перезапуска MLX Server: {e}", exc_info=True)
    
    async def check_all_services(self):
        """Проверить все сервисы"""
        for service_name, service in self.services.items():
            old_status = self.service_statuses.get(service_name, ServiceStatus.UNKNOWN)
            new_status = await self.check_service(service)
            
            self.service_statuses[service_name] = new_status
            
            # Публикуем событие об изменении статуса
            await self._publish_status_change(service, old_status, new_status)
    
    async def _monitoring_loop(self):
        """Основной цикл мониторинга"""
        logger.info("🔄 Запуск цикла мониторинга сервисов")
        
        while self.running:
            try:
                await self.check_all_services()
                await asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.error(f"❌ Ошибка в цикле мониторинга: {e}", exc_info=True)
                await asyncio.sleep(self.check_interval)
    
    async def start(self):
        """Запустить мониторинг"""
        if self.running:
            logger.warning("⚠️ Service Monitor уже запущен")
            return
        
        self.running = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("🚀 Service Monitor запущен")
    
    async def stop(self):
        """Остановить мониторинг"""
        if not self.running:
            return
        
        self.running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        
        logger.info("🛑 Service Monitor остановлен")
    
    def get_stats(self) -> Dict[str, Any]:
        """Получить статистику мониторинга"""
        status_counts = {}
        for status in ServiceStatus:
            status_counts[status.value] = sum(
                1 for s in self.service_statuses.values() if s == status
            )
        
        return {
            "running": self.running,
            "total_services": len(self.services),
            "status_counts": status_counts,
            "check_interval": self.check_interval,
            "services": {
                name: {
                    "status": status.value,
                    "type": service.service_type,
                    "endpoint": service.endpoint
                }
                for name, (service, status) in zip(
                    self.services.keys(),
                    zip(self.services.values(), self.service_statuses.values())
                )
            }
        }


async def main():
    """Пример использования"""
    import logging
    logging.basicConfig(level=logging.INFO)
    
    # Инициализируем Event Bus
    event_bus = get_event_bus()
    await event_bus.start()
    
    # Подписываемся на события сервисов
    async def handle_service_down(event: Event):
        print(f"🔴 Сервис упал: {event.payload.get('service_name')}")
    
    async def handle_service_up(event: Event):
        print(f"🟢 Сервис запущен: {event.payload.get('service_name')}")
    
    event_bus.subscribe(EventType.SERVICE_DOWN, handle_service_down)
    event_bus.subscribe(EventType.SERVICE_UP, handle_service_up)
    
    # Создаем Service Monitor
    monitor = ServiceMonitor(check_interval=10)
    
    await monitor.start()
    
    # Ждем события
    print("⏳ Мониторинг сервисов (нажмите Ctrl+C для остановки)...")
    try:
        await asyncio.sleep(60)
    except KeyboardInterrupt:
        pass
    
    print(f"\n📊 Статистика: {monitor.get_stats()}")
    
    await monitor.stop()
    await event_bus.stop()


if __name__ == "__main__":
    asyncio.run(main())

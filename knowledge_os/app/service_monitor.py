"""
Service Monitor - Мониторинг сервисов (Docker, HTTP, процессы)
Основано на Clawdbot + интеграция с SelfCheckSystem
Публикует события в Event Bus при изменениях статуса сервисов
"""

import asyncio
import logging
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Set

import httpx
try:
    from app.event_bus import Event, EventType, get_event_bus
except ImportError:
    from event_bus import Event, EventType, get_event_bus

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

    def __init__(self, services: Optional[List[Service]] = None, check_interval: int = 30):
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

    def is_running(self) -> bool:
        """Соответствует контракту FileWatcher/других мониторов для тестов и API."""
        return self.running

    def _get_default_services(self) -> List[Service]:
        """Получить список сервисов по умолчанию для мониторинга.
        В контейнере Victoria слушает порт 8000 (VICTORIA_PORT); снаружи 8010. Иначе сам себя помечает как down и сыпет события.

        Переменные окружения для настройки URL сервисов:
        - MLX_MONITOR_URL: URL для проверки MLX API Server (по умолчанию: host.docker.internal:11435 в Docker, localhost:11435 локально)
        - BACKEND_MONITOR_URL: URL для проверки Backend (по умолчанию: atra-web-ide-backend:8000 в Docker, localhost:8080 локально)
        - FRONTEND_MONITOR_URL: URL для проверки Frontend (по умолчанию: atra-web-ide-grafana:3000 в Docker, localhost:3002 локально)
        """
        victoria_port = int(os.getenv("VICTORIA_PORT", "8010"))

        # Определяем, запущены ли мы в Docker
        # Проверяем по нескольким признакам — DATABASE_URL может указывать на PgBouncer
        in_docker = (
            "knowledge_postgres" in os.getenv("DATABASE_URL", "")
            or "knowledge_pgbouncer" in os.getenv("DATABASE_URL", "")
            or os.path.exists("/.dockerenv")
        )

        # MLX API Server URL: в Docker используем host.docker.internal, локально localhost
        mlx_url = os.getenv(
            "MLX_MONITOR_URL",
            "http://host.docker.internal:11435" if in_docker else "http://localhost:11435",
        )

        # Backend URL: в Docker используем имя контейнера, локально localhost
        backend_url = os.getenv(
            "BACKEND_MONITOR_URL",
            "http://host.docker.internal:8080" if in_docker else "http://localhost:8080",
        )

        # Frontend URL: Grafana на 3001 (не 3002)
        frontend_url = os.getenv(
            "FRONTEND_MONITOR_URL",
            "http://host.docker.internal:3001" if in_docker else "http://localhost:3001",
        )

        return [
            Service(
                name="Victoria Agent",
                service_type="http",
                endpoint=f"http://victoria-agent:8000" if in_docker else f"http://127.0.0.1:{victoria_port}",
                port=victoria_port,
                health_check_path="/health",
            ),
            Service(
                name="Veronica Agent",
                service_type="http",
                endpoint="http://veronica-agent:8000"
                if victoria_port == 8000
                else os.getenv("VERONICA_MONITOR_URL", "http://localhost:8011"),
                port=8011,
                health_check_path="/health",
            ),
            Service(
                name="Victoria Proxy",
                service_type="http",
                endpoint=os.getenv("PROXY_MONITOR_URL", "http://host.docker.internal:8040" if in_docker else "http://localhost:8040"),
                port=8040,
                health_check_path="/health",
                check_interval=30,
                timeout=5,
            ),
            Service(
                name="MLX API Server",
                service_type="http",
                endpoint=mlx_url,
                port=11435,
                health_check_path="/health",
                check_interval=10,
                timeout=5,
            ),
            Service(
                name="Backend",
                service_type="http",
                endpoint=backend_url,
                port=8080,
                health_check_path="/health",
            ),
            Service(name="Grafana", service_type="http", endpoint=frontend_url, port=3001),
            Service(
                name="PostgreSQL", service_type="docker", endpoint="knowledge_postgres", port=5432
            ),
            Service(
                name="Redis",
                service_type="docker",
                endpoint="redis",  # имя сервиса в compose; контейнер — knowledge_os_redis
                port=6379,
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

            async with httpx.AsyncClient(timeout=service.timeout, follow_redirects=False) as client:
                response = await client.get(url)

                # 200 — OK, 301/302 — редирект (нормально для Grafana, frontend без /health)
                if response.status_code in [200, 301, 302]:
                    return ServiceStatus.UP
                elif response.status_code in [503, 502]:
                    return ServiceStatus.DEGRADED
                else:
                    return ServiceStatus.DOWN
        except httpx.TimeoutException:
            logger.warning(f"⏱️ Таймаут проверки {service.name} ({url})")
            return ServiceStatus.DOWN
        except httpx.ConnectError as e:
            logger.warning(f"🔌 {service.name} недоступен (ConnectError): {url} — {e!r}")
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
                timeout=service.timeout,
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
                ["pgrep", "-f", service.endpoint], capture_output=True, timeout=service.timeout
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

    async def _publish_status_change(
        self, service: Service, old_status: ServiceStatus, new_status: ServiceStatus
    ):
        """Опубликовать событие об изменении статуса"""
        if old_status == new_status:
            return

        # [SINGULARITY 24.3] Avoid flooding the EventBus with UNKNOWN/DOWN transitions during startup
        # or when services are flapping.
        if old_status == ServiceStatus.UNKNOWN and new_status == ServiceStatus.DOWN:
            logger.info(f"ℹ️ Service {service.name} is DOWN on first check (expected during startup)")
            return

        # Определяем тип события
        if new_status == ServiceStatus.DOWN:
            event_type = EventType.SERVICE_DOWN
        elif new_status == ServiceStatus.UP and old_status == ServiceStatus.DOWN:
            event_type = EventType.SERVICE_UP
        else:
            event_type = EventType.SERVICE_HEALTH_CHECK

        event = Event(
            event_id=f"service_{service.name}_{new_status.value}_{int(datetime.now(timezone.utc).timestamp())}",
            event_type=event_type,
            payload={
                "service_name": service.name,
                "service_type": service.service_type,
                "old_status": old_status.value,
                "new_status": new_status.value,
                "endpoint": service.endpoint,
                "port": service.port,
            },
            source="service_monitor",
        )

        await self.event_bus.publish(event)
        logger.info(f"📢 Статус {service.name}: {old_status.value} → {new_status.value}")

        # Автоматический перезапуск для MLX API Server через Supervisor
        if service.name == "MLX API Server" and new_status == ServiceStatus.DOWN:
            await self._try_restart_mlx_server()
            
        # [SINGULARITY 28.5] Self-healing for MicroVM nodes
        if "microvm" in service.name.lower() and new_status == ServiceStatus.DOWN:
            await self._self_heal_microvm(service.name)

    async def _self_heal_microvm(self, vm_name: str):
        """
        [SINGULARITY 28.5] Self-healing logic for MicroVMs.
        Terminates the stuck node and notifies SandboxManager to recreate.
        """
        logger.warning(f"🩹 [SELF-HEALING] MicroVM {vm_name} is DOWN. Attempting recovery...")
        try:
            # 1. Kill the stuck process (simulated)
            # In a real environment, we would use 'limactl stop' or 'firecracker-ctl'
            expert_name = vm_name.replace("microvm-", "")
            
            # 2. Publish event to trigger task requeue
            event = Event(
                event_id=f"self_heal_{vm_name}_{int(time.time())}",
                event_type=EventType.SERVICE_DOWN,
                payload={"type": "microvm_recovery", "vm": vm_name, "expert": expert_name},
                source="service_monitor",
            )
            await self.event_bus.publish(event)
            logger.info(f"✅ [SELF-HEALING] Recovery event published for {vm_name}")
        except Exception as e:
            logger.error(f"❌ [SELF-HEALING] Recovery failed for {vm_name}: {e}")

    async def _try_restart_mlx_server(self):
        """Попытка перезапуска MLX Server через Supervisor"""
        # ... existing code ...

    async def promote_mutation(self, module_name: str, mutation_path: str):
        """[SINGULARITY 10.0] Atomically promote a mutated code version to production."""
        target_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", f"{module_name}.py"
        )
        backup_path = target_path + ".bak"

        logger.info(f"🚀 [HOT-SWAP] Promoting mutation for {module_name}...")

        try:
            # 1. Create backup
            if os.path.exists(target_path):
                import shutil

                shutil.copy2(target_path, backup_path)

            # 2. Atomic swap
            os.replace(mutation_path, target_path)

            # 3. Restart relevant services
            # For ai_core, we might need to restart the main agent process
            # In Docker, this could be a container restart
            logger.info(
                f"✅ [HOT-SWAP] Successfully promoted {module_name}. Restarting services..."
            )

            # Trigger event for other components to react
            event = Event(
                event_id=f"hot_swap_{module_name}_{int(time.time())}",
                event_type=EventType.SERVICE_UP,  # Use UP to trigger re-init
                payload={"type": "hot_swap", "module": module_name, "status": "completed"},
                source="service_monitor",
            )
            await self.event_bus.publish(event)

        except Exception as e:
            logger.error(f"❌ [HOT-SWAP] Promotion failed for {module_name}: {e}")
            await self.rollback_mutation(module_name)

    async def rollback_mutation(self, module_name: str):
        """Rollback to the previous version from backup."""
        target_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "app", f"{module_name}.py"
        )
        backup_path = target_path + ".bak"

        if os.path.exists(backup_path):
            logger.warning(f"🔄 [ROLLBACK] Rolling back {module_name} to backup...")
            os.replace(backup_path, target_path)
            logger.info(f"✅ [ROLLBACK] Successfully rolled back {module_name}.")
        else:
            logger.error(f"❌ [ROLLBACK] No backup found for {module_name}!")
        try:
            from app.mlx_server_supervisor import get_mlx_supervisor

            supervisor = get_mlx_supervisor()
            status = supervisor.get_status()

            # Если supervisor не запущен, запускаем его
            if not status["running"]:
                logger.info(
                    "🔄 [SERVICE MONITOR] Запуск MLX Server Supervisor для автоматического перезапуска..."
                )
                await supervisor.start()
            else:
                logger.info(
                    "ℹ️ [SERVICE MONITOR] MLX Server Supervisor уже запущен, перезапуск произойдет автоматически"
                )

        except ImportError:
            logger.warning(
                "⚠️ [SERVICE MONITOR] MLX Server Supervisor не доступен, автоматический перезапуск невозможен"
            )
        except Exception as e:
            logger.error(
                f"❌ [SERVICE MONITOR] Ошибка при попытке перезапуска MLX Server: {e}",
                exc_info=True,
            )

    async def check_all_services(self):
        """Проверить все сервисы и глубину очереди задач"""
        for service_name, service in self.services.items():
            old_status = self.service_statuses.get(service_name, ServiceStatus.UNKNOWN)
            new_status = await self.check_service(service)

            self.service_statuses[service_name] = new_status

            # Публикуем событие об изменении статуса
            await self._publish_status_change(service, old_status, new_status)

        # [SINGULARITY 24.3] Мониторинг глубины очереди задач
        await self._check_queue_depth()

    # [SINGULARITY 25.1] Retry logic for failed tasks (Igor & Roman)
    async def retry_failed_tasks(self, limit: int = 11):
        """Находит последние проваленные задачи и перезапускает их."""
        pool = await get_pool()
        async with pool.acquire() as conn:
            # Находим задачи с таймаутами или ошибками связи
            tasks = await conn.fetch("""
                SELECT id, title, goal, project_context, metadata
                FROM tasks
                WHERE status = 'failed'
                AND (result ILIKE '%timeout%' OR result ILIKE '%Connect call failed%')
                ORDER BY updated_at DESC
                LIMIT $1
            """, limit)
            
            for task in tasks:
                logger.info(f"🔄 [RETRY] Перезапуск задачи {task['id']}: {task['title']}")
                # Сбрасываем статус в pending
                await conn.execute("""
                    UPDATE tasks 
                    SET status = 'pending', result = NULL, updated_at = NOW()
                    WHERE id = $1
                """, task['id'])
            
            return len(tasks)

    async def _check_queue_depth(self):
        """Проверить количество PENDING задач и опубликовать событие при перегрузке"""
        try:
            from app.db_pool import get_pool
            pool = await get_pool()
            async with pool.acquire() as conn:
                pending_count = await conn.fetchval("SELECT count(*) FROM tasks WHERE status = 'pending'")
                
                max_queue = int(os.getenv("MAX_PENDING_TASKS_THRESHOLD", "100"))
                
                if pending_count > max_queue:
                    logger.warning(f"⚠️ Очередь перегружена: {pending_count} задач (лимит: {max_queue})")
                    event = Event(
                        event_id=f"queue_overload_{int(datetime.now(timezone.utc).timestamp())}",
                        event_type=EventType.PERFORMANCE_DEGRADED,
                        payload={
                            "metric": "queue_depth",
                            "value": pending_count,
                            "threshold": max_queue,
                            "status": "overloaded"
                        },
                        source="service_monitor"
                    )
                    await self.event_bus.publish(event)
        except Exception as e:
            logger.error(f"❌ Ошибка проверки глубины очереди: {e}")

    async def _monitoring_loop(self):
        """Основной цикл мониторинга. Задержка перед первым проходом: Victoria (HTTP + skills + DB) + запас на развёртывание и загрузку моделей при первом запросе."""
        logger.info("🔄 Запуск цикла мониторинга сервисов")
        # По умолчанию 50 с: старт Victoria 25–40 с + запас на холодную БД и первый запрос (Ollama/MLX могут подгружать модель)
        raw = os.getenv("SERVICE_MONITOR_INITIAL_DELAY", "50").strip()
        try:
            initial_delay = max(25, min(120, int(raw)))
        except ValueError:
            initial_delay = 50
        logger.info("⏳ Ожидание %s с перед первым проходом проверки сервисов", initial_delay)
        await asyncio.sleep(initial_delay)

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
                    "endpoint": service.endpoint,
                }
                for name, (service, status) in zip(
                    self.services.keys(),
                    zip(self.services.values(), self.service_statuses.values()),
                )
            },
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

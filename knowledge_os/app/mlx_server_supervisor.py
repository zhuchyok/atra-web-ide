"""
MLX Server Supervisor - автоматический перезапуск и мониторинг
Основано на мировых практиках: Elixir Supervision Trees, Circuit Breaker Pattern, Exponential Backoff
"""

import asyncio
import logging
import os
import signal
import subprocess
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

# Импортируем Circuit Breaker если доступен
try:
    from app.circuit_breaker import CircuitBreaker, CircuitState

    CIRCUIT_BREAKER_AVAILABLE = True
except ImportError:
    CIRCUIT_BREAKER_AVAILABLE = False
    logger.warning("⚠️ Circuit Breaker не доступен")


class ServerState(Enum):
    """Состояния сервера"""

    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    CRASHED = "crashed"
    RESTARTING = "restarting"


@dataclass
class SupervisorConfig:
    """Конфигурация supervisor"""

    max_restarts: int = 5  # Максимум перезапусков в окне
    restart_window: int = 300  # Окно времени для подсчета перезапусков (5 минут)
    restart_delay: float = 2.0  # Начальная задержка перед перезапуском (секунды)
    max_restart_delay: float = 60.0  # Максимальная задержка (exponential backoff)
    health_check_interval: int = 10  # Интервал проверки здоровья (секунды)
    health_check_timeout: float = 5.0  # Таймаут health check
    server_url: str = "http://localhost:11435"
    server_script: str = "knowledge_os/app/mlx_api_server.py"
    server_port: int = 11435


class MLXServerSupervisor:
    """
    Supervisor для MLX API Server

    Реализует паттерны:
    1. Supervision Tree (Elixir-style) - автоматический перезапуск при падении
    2. Circuit Breaker - защита от каскадных сбоев
    3. Exponential Backoff - постепенное увеличение задержки между перезапусками
    4. Health Monitoring - постоянная проверка здоровья сервера
    5. Graceful Shutdown - корректное завершение процесса
    """

    def __init__(self, config: Optional[SupervisorConfig] = None):
        self.config = config or SupervisorConfig()
        self.state = ServerState.STOPPED
        self.process: Optional[subprocess.Popen] = None
        self.restart_times: list = []  # Времена перезапусков для rate limiting
        self.current_restart_delay = self.config.restart_delay
        self.last_health_check: Optional[datetime] = None
        self.health_check_failures = 0
        self.max_health_failures = 3  # После 3 неудачных проверок считаем сервер упавшим
        self.running = False
        self._monitoring_task: Optional[asyncio.Task] = None

        # Circuit Breaker для защиты от каскадных сбоев
        if CIRCUIT_BREAKER_AVAILABLE:
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=5, recovery_timeout=60, name="mlx_server"
            )
        else:
            self.circuit_breaker = None

        logger.info(f"✅ MLX Server Supervisor инициализирован (URL: {self.config.server_url})")

    def _should_restart(self) -> bool:
        """Проверяет, можно ли перезапустить сервер (rate limiting)"""
        now = datetime.now()

        # Удаляем старые перезапуски (старше окна)
        cutoff = now - timedelta(seconds=self.config.restart_window)
        self.restart_times = [t for t in self.restart_times if t > cutoff]

        # Проверяем лимит
        if len(self.restart_times) >= self.config.max_restarts:
            logger.warning(
                f"⚠️ [SUPERVISOR] Достигнут лимит перезапусков ({self.config.max_restarts}) "
                f"за {self.config.restart_window}с. Ожидание..."
            )
            return False

        return True

    def _calculate_backoff_delay(self) -> float:
        """Вычисляет задержку с exponential backoff"""
        # Увеличиваем задержку экспоненциально
        delay = min(
            self.config.restart_delay * (2 ** len(self.restart_times)),
            self.config.max_restart_delay,
        )
        return delay

    async def _check_health(self) -> bool:
        """Проверка здоровья сервера"""
        try:
            async with httpx.AsyncClient(timeout=self.config.health_check_timeout) as client:
                response = await client.get(f"{self.config.server_url}/health")
                if response.status_code == 200:
                    data = response.json()
                    # Проверяем статус
                    status = data.get("status", "unknown")
                    is_healthy = status in ("healthy", "ok", "online")

                    if is_healthy:
                        self.health_check_failures = 0
                        self.last_health_check = datetime.now()
                        return True
                    else:
                        logger.warning(f"⚠️ [SUPERVISOR] Сервер отвечает, но статус: {status}")
                        return False
                else:
                    logger.warning(f"⚠️ [SUPERVISOR] Health check вернул код {response.status_code}")
                    return False
        except Exception as e:
            logger.debug(f"⚠️ [SUPERVISOR] Health check failed: {e}")
            return False

    def _is_mlx_disabled(self) -> bool:
        """True, если MLX отключён (MLX_API_URL=disabled/empty) — не запускаем сервер в контейнере."""
        url = os.getenv("MLX_API_URL", "").strip().lower()
        return url in ("", "disabled", "false", "0")

    async def _start_server(self) -> bool:
        """Запуск сервера"""
        if self._is_mlx_disabled():
            logger.debug("⚠️ [SUPERVISOR] MLX отключён (MLX_API_URL), пропуск запуска")
            return False
        if not self._should_restart():
            return False

        if self.state == ServerState.STARTING or self.state == ServerState.RESTARTING:
            logger.debug("⚠️ [SUPERVISOR] Сервер уже запускается")
            return False

        self.state = ServerState.STARTING
        logger.info("🚀 [SUPERVISOR] Запуск MLX API Server...")

        try:
            # Вычисляем задержку перед запуском (exponential backoff)
            delay = self._calculate_backoff_delay()
            if delay > self.config.restart_delay:
                logger.info(
                    f"⏳ [SUPERVISOR] Ожидание {delay:.1f}с перед перезапуском (exponential backoff)"
                )
                await asyncio.sleep(delay)

            # Запускаем сервер
            script_path = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                self.config.server_script,
            )

            if not os.path.exists(script_path):
                logger.error(f"❌ [SUPERVISOR] Скрипт не найден: {script_path}")
                self.state = ServerState.CRASHED
                return False

            # Настраиваем логирование для процесса
            log_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "logs"
            )
            os.makedirs(log_dir, exist_ok=True)
            stdout_log = os.path.join(log_dir, "mlx_server_stdout.log")
            stderr_log = os.path.join(log_dir, "mlx_server_stderr.log")

            # Открываем файлы для логирования
            stdout_file = open(stdout_log, "a", encoding="utf-8")
            stderr_file = open(stderr_log, "a", encoding="utf-8")

            logger.info(f"📝 Логи MLX Server: stdout={stdout_log}, stderr={stderr_log}")

            # Запускаем процесс с логированием
            self.process = subprocess.Popen(
                ["python3", script_path],
                stdout=stdout_file,
                stderr=stderr_file,
                cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            )

            # Ждем немного для инициализации
            await asyncio.sleep(3)

            # Проверяем, что процесс запущен
            if self.process.poll() is not None:
                # Процесс уже завершился
                stderr = self.process.stderr.read().decode() if self.process.stderr else ""
                logger.error(f"❌ [SUPERVISOR] Сервер упал сразу после запуска: {stderr}")
                self.state = ServerState.CRASHED
                return False

            # Проверяем здоровье
            for attempt in range(5):  # 5 попыток проверки
                await asyncio.sleep(2)
                if await self._check_health():
                    self.state = ServerState.RUNNING
                    self.current_restart_delay = self.config.restart_delay  # Сбрасываем задержку
                    logger.info(
                        f"✅ [SUPERVISOR] MLX API Server запущен и здоров (PID: {self.process.pid})"
                    )
                    return True

            # Сервер запустился, но не отвечает на health check
            logger.warning("⚠️ [SUPERVISOR] Сервер запущен, но не отвечает на health check")
            self.state = ServerState.RUNNING  # Все равно считаем запущенным
            return True

        except Exception as e:
            logger.error(f"❌ [SUPERVISOR] Ошибка запуска сервера: {e}", exc_info=True)
            self.state = ServerState.CRASHED
            return False

    async def _stop_server(self, graceful: bool = True) -> bool:
        """Остановка сервера"""
        if self.process is None:
            return True

        logger.info(f"🛑 [SUPERVISOR] Остановка MLX API Server (graceful={graceful})...")

        try:
            if graceful:
                # Отправляем SIGTERM для graceful shutdown
                self.process.terminate()

                # Ждем завершения (до 10 секунд)
                try:
                    self.process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    # Если не завершился, принудительно убиваем
                    logger.warning("⚠️ [SUPERVISOR] Сервер не завершился, принудительная остановка")
                    self.process.kill()
                    self.process.wait()
            else:
                # Принудительная остановка
                self.process.kill()
                self.process.wait()

            self.process = None
            self.state = ServerState.STOPPED
            logger.info("✅ [SUPERVISOR] Сервер остановлен")
            return True

        except Exception as e:
            logger.error(f"❌ [SUPERVISOR] Ошибка остановки сервера: {e}")
            return False

    async def _monitoring_loop(self):
        """Основной цикл мониторинга"""
        logger.info("🔍 [SUPERVISOR] Запущен цикл мониторинга")

        while self.running:
            try:
                # Проверяем состояние процесса
                if self.process is not None:
                    return_code = self.process.poll()
                    if return_code is not None:
                        # Процесс завершился
                        logger.error(f"❌ [SUPERVISOR] Сервер упал (код: {return_code})")
                        self.state = ServerState.CRASHED
                        self.process = None

                # Проверяем здоровье если сервер должен быть запущен
                if self.state == ServerState.RUNNING:
                    is_healthy = await self._check_health()

                    if not is_healthy:
                        self.health_check_failures += 1
                        logger.warning(
                            f"⚠️ [SUPERVISOR] Health check failed "
                            f"({self.health_check_failures}/{self.max_health_failures})"
                        )

                        if self.health_check_failures >= self.max_health_failures:
                            logger.error("❌ [SUPERVISOR] Сервер не отвечает, считаем упавшим")
                            self.state = ServerState.CRASHED
                    else:
                        self.health_check_failures = 0

                # Если сервер упал, перезапускаем
                if self.state == ServerState.CRASHED:
                    logger.info("🔄 [SUPERVISOR] Попытка перезапуска сервера...")
                    self.state = ServerState.RESTARTING
                    self.restart_times.append(datetime.now())

                    # Используем Circuit Breaker если доступен
                    if self.circuit_breaker:
                        if self.circuit_breaker.state == CircuitState.OPEN:
                            logger.warning(
                                "⚠️ [SUPERVISOR] Circuit Breaker OPEN, пропускаем перезапуск"
                            )
                            await asyncio.sleep(self.config.health_check_interval)
                            continue

                    success = await self._start_server()

                    if not success:
                        logger.error("❌ [SUPERVISOR] Не удалось перезапустить сервер")
                        # Обновляем Circuit Breaker
                        if self.circuit_breaker:
                            self.circuit_breaker._on_failure("Server restart failed")

                await asyncio.sleep(self.config.health_check_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ [SUPERVISOR] Ошибка в цикле мониторинга: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def ensure_server_running(self) -> bool:
        """
        Проверить доступность MLX API Server; если недоступен — запустить.
        Вызывать при получении задачи. При MLX_API_URL=disabled сразу True (не пытаемся запустить).
        """
        if self._is_mlx_disabled():
            logger.debug("⚠️ [SUPERVISOR] MLX отключён, не запускаем")
            return True
        if await self._check_health():
            logger.debug("✅ [SUPERVISOR] MLX API Server уже доступен")
            return True
        logger.info("🔄 [SUPERVISOR] MLX API Server недоступен, запускаю...")
        return await self._start_server()

    async def start(self) -> bool:
        """Запуск supervisor и сервера"""
        if self.running:
            logger.warning("⚠️ [SUPERVISOR] Supervisor уже запущен")
            return False

        self.running = True

        # Запускаем сервер
        success = await self._start_server()

        if success:
            # Запускаем мониторинг
            self._monitoring_task = asyncio.create_task(self._monitoring_loop())
            logger.info("✅ [SUPERVISOR] Supervisor запущен")

        return success

    async def stop(self):
        """Остановка supervisor и сервера"""
        logger.info("🛑 [SUPERVISOR] Остановка supervisor...")

        self.running = False

        # Останавливаем мониторинг
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass

        # Останавливаем сервер
        await self._stop_server(graceful=True)

        logger.info("✅ [SUPERVISOR] Supervisor остановлен")

    def get_status(self) -> Dict[str, Any]:
        """Получить статус supervisor"""
        return {
            "state": self.state.value,
            "running": self.running,
            "process_pid": self.process.pid if self.process else None,
            "restart_count": len(self.restart_times),
            "health_check_failures": self.health_check_failures,
            "last_health_check": self.last_health_check.isoformat()
            if self.last_health_check
            else None,
            "circuit_breaker_state": self.circuit_breaker.state.value
            if self.circuit_breaker
            else None,
        }


# Глобальный экземпляр
_supervisor: Optional[MLXServerSupervisor] = None


def get_mlx_supervisor() -> MLXServerSupervisor:
    """Получить глобальный экземпляр supervisor"""
    global _supervisor
    if _supervisor is None:
        _supervisor = MLXServerSupervisor()
    return _supervisor

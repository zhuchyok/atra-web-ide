"""
Health Checks - Проверка здоровья системы и компонентов

Принцип: Self-Validating Code - Health Checks & System Monitoring
Цель: Автоматическая проверка состояния системы и её компонентов
"""

import asyncio
import functools
import inspect
import logging
import time
from typing import Callable, Any, Optional, Dict, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Статус здоровья компонента"""
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"


@dataclass
class HealthCheckResult:
    """Результат проверки здоровья"""
    name: str
    status: HealthStatus
    message: str = ""
    response_time_ms: float = 0.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: Optional[Dict[str, Any]] = None
    critical: bool = False
    
    def is_healthy(self) -> bool:
        """Проверка, здоров ли компонент"""
        return self.status == HealthStatus.HEALTHY
    
    def is_critical_failure(self) -> bool:
        """Проверка, является ли это критичной ошибкой"""
        return self.critical and self.status != HealthStatus.HEALTHY


@dataclass
class SystemHealthStatus:
    """Общий статус здоровья системы"""
    overall_status: HealthStatus
    checks: List[HealthCheckResult]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    def is_healthy(self) -> bool:
        """Проверка, здорова ли система"""
        return self.overall_status == HealthStatus.HEALTHY
    
    def get_critical_failures(self) -> List[HealthCheckResult]:
        """Получить список критичных ошибок"""
        return [check for check in self.checks if check.is_critical_failure()]
    
    def get_unhealthy_checks(self) -> List[HealthCheckResult]:
        """Получить список нездоровых компонентов"""
        return [check for check in self.checks if not check.is_healthy()]


class HealthCheckManager:
    """
    Менеджер для управления проверками здоровья системы
    
    Обеспечивает:
    - Регистрацию health checks для компонентов
    - Автоматическое выполнение проверок
    - Агрегацию результатов
    - Определение общего статуса системы
    """
    
    def __init__(self):
        """Инициализация менеджера health checks"""
        self._checks: Dict[str, Callable] = {}
        self._check_metadata: Dict[str, Dict[str, Any]] = {}
        self._last_results: Dict[str, HealthCheckResult] = {}
        self._check_timeout: float = 5.0  # Таймаут для проверки (секунды)
    
    def register_check(
        self,
        name: str,
        check_func: Callable,
        critical: bool = False,
        timeout: Optional[float] = None
    ) -> None:
        """
        Регистрация health check
        
        Args:
            name: Имя проверки
            check_func: Функция проверки (может быть sync или async)
            critical: Является ли проверка критичной
            timeout: Таймаут для проверки (если None, используется дефолтный)
        """
        self._checks[name] = check_func
        self._check_metadata[name] = {
            "critical": critical,
            "timeout": timeout or self._check_timeout
        }
        logger.debug(f"Health check registered: {name} (critical={critical})")
    
    async def check(self, name: str) -> HealthCheckResult:
        """
        Выполнить проверку здоровья компонента
        
        Args:
            name: Имя проверки
            
        Returns:
            Результат проверки здоровья
        """
        if name not in self._checks:
            return HealthCheckResult(
                name=name,
                status=HealthStatus.UNKNOWN,
                message=f"Health check '{name}' not registered",
                critical=False
            )
        
        check_func = self._checks[name]
        metadata = self._check_metadata[name]
        critical = metadata.get("critical", False)
        timeout = metadata.get("timeout", self._check_timeout)
        
        start_time = time.time()
        
        try:
            # Выполняем проверку с таймаутом
            if asyncio.iscoroutinefunction(check_func):
                result = await asyncio.wait_for(check_func(), timeout=timeout)
            else:
                # Для sync функций используем run_in_executor
                loop = asyncio.get_event_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, check_func),
                    timeout=timeout
                )
            
            response_time_ms = (time.time() - start_time) * 1000
            
            # Интерпретируем результат
            if isinstance(result, bool):
                status = HealthStatus.HEALTHY if result else HealthStatus.UNHEALTHY
                message = "Component is healthy" if result else "Component is unhealthy"
            elif isinstance(result, HealthCheckResult):
                status = result.status
                message = result.message
                response_time_ms = result.response_time_ms
            else:
                status = HealthStatus.HEALTHY
                message = "Check completed successfully"
            
            health_result = HealthCheckResult(
                name=name,
                status=status,
                message=message,
                response_time_ms=response_time_ms,
                critical=critical,
                details={"result": str(result)[:100]} if result else None
            )
            
            self._last_results[name] = health_result
            return health_result
            
        except asyncio.TimeoutError:
            response_time_ms = (time.time() - start_time) * 1000
            result = HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check timed out after {timeout}s",
                response_time_ms=response_time_ms,
                critical=critical
            )
            self._last_results[name] = result
            logger.warning(f"Health check '{name}' timed out")
            return result
            
        except Exception as e:
            response_time_ms = (time.time() - start_time) * 1000
            result = HealthCheckResult(
                name=name,
                status=HealthStatus.UNHEALTHY,
                message=f"Health check failed: {str(e)}",
                response_time_ms=response_time_ms,
                critical=critical,
                details={"error": str(e)[:200]}
            )
            self._last_results[name] = result
            logger.error(f"Health check '{name}' failed: {e}")
            return result
    
    async def check_all(self) -> SystemHealthStatus:
        """
        Выполнить все зарегистрированные проверки
        
        Returns:
            Общий статус здоровья системы
        """
        checks = []
        
        # Выполняем все проверки параллельно
        tasks = [self.check(name) for name in self._checks.keys()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                checks.append(HealthCheckResult(
                    name="unknown",
                    status=HealthStatus.UNKNOWN,
                    message=f"Check failed with exception: {str(result)}",
                    critical=False
                ))
            else:
                checks.append(result)
        
        # Определяем общий статус
        critical_failures = [c for c in checks if c.is_critical_failure()]
        unhealthy_checks = [c for c in checks if not c.is_healthy()]
        
        if critical_failures:
            overall_status = HealthStatus.UNHEALTHY
        elif unhealthy_checks:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.HEALTHY
        
        system_status = SystemHealthStatus(
            overall_status=overall_status,
            checks=checks
        )
        
        return system_status
    
    def get_last_result(self, name: str) -> Optional[HealthCheckResult]:
        """Получить последний результат проверки"""
        return self._last_results.get(name)
    
    def get_all_last_results(self) -> Dict[str, HealthCheckResult]:
        """Получить все последние результаты"""
        return self._last_results.copy()
    
    def clear_results(self) -> None:
        """Очистить результаты проверок"""
        self._last_results.clear()


# Глобальный экземпляр для удобства использования
_global_health_manager: Optional[HealthCheckManager] = None


def get_health_manager() -> HealthCheckManager:
    """
    Получить глобальный экземпляр HealthCheckManager
    
    Returns:
        Глобальный экземпляр менеджера
    """
    global _global_health_manager
    if _global_health_manager is None:
        _global_health_manager = HealthCheckManager()
    return _global_health_manager


def health_check(name: str, critical: bool = False, timeout: Optional[float] = None):
    """
    Декоратор для регистрации health check
    
    Args:
        name: Имя проверки
        critical: Является ли проверка критичной
        timeout: Таймаут для проверки
        
    Example:
        @health_check(name="database", critical=True)
        def check_database():
            return db.ping()
    """
    def decorator(func: Callable) -> Callable:
        manager = get_health_manager()
        manager.register_check(name, func, critical=critical, timeout=timeout)
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            return await func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return wrapper
    return decorator


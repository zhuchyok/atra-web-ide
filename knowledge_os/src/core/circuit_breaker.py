#!/usr/bin/env python3
"""
🔌 Circuit Breaker Pattern для защиты от каскадных сбоев

Предотвращает каскадные сбои через:
1. Отслеживание failures
2. Автоматическое отключение при превышении порога
3. Автоматическое восстановление после таймаута

Автор: Игорь (Backend Developer) - Learning Session #4
Основано на: "Release It!" (Michael Nygard)
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from threading import Lock
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Состояния circuit breaker"""

    CLOSED = "CLOSED"  # Нормальная работа
    OPEN = "OPEN"  # Отключен (слишком много ошибок)
    HALF_OPEN = "HALF_OPEN"  # Тестирование восстановления


@dataclass
class CircuitBreakerConfig:
    """Конфигурация circuit breaker"""

    failure_threshold: int = 5  # Порог ошибок для открытия
    success_threshold: int = 2  # Порог успехов для закрытия (из HALF_OPEN)
    timeout: float = 60.0  # Таймаут перед попыткой восстановления (секунды)
    expected_exception: type = Exception  # Тип исключения для отслеживания


class CircuitBreaker:
    """
    Circuit Breaker для защиты от каскадных сбоев

    Использование:
        breaker = CircuitBreaker(failure_threshold=5, timeout=60)

        try:
            result = breaker.call(risky_function, arg1, arg2)
        except CircuitBreakerOpenError:
            # Circuit breaker открыт, функция не вызывается
            pass
    """

    def __init__(
        self,
        name: str = "default",
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: float = 60.0,
        expected_exception: type = Exception,
    ):
        """
        Args:
            name: Имя circuit breaker (для логирования)
            failure_threshold: Количество ошибок для открытия
            success_threshold: Количество успехов для закрытия (из HALF_OPEN)
            timeout: Таймаут перед попыткой восстановления (секунды)
            expected_exception: Тип исключения для отслеживания
        """
        self.name = name
        self.config = CircuitBreakerConfig(
            failure_threshold=failure_threshold,
            success_threshold=success_threshold,
            timeout=timeout,
            expected_exception=expected_exception,
        )

        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.last_success_time: Optional[float] = None
        self._lock = Lock()

    def can_execute(self) -> bool:
        """
        Проверяет, можно ли выполнить вызов (не открыт ли circuit breaker)
        """
        with self._lock:
            if self.state == CircuitState.CLOSED:
                return True
            if self.state == CircuitState.HALF_OPEN:
                return True
            if self.state == CircuitState.OPEN:
                # Если таймаут истёк, можно переходить в HALF_OPEN
                if self.last_failure_time and (
                    time.time() - self.last_failure_time >= self.config.timeout
                ):
                    return True
            return False

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Вызывает функцию через circuit breaker

        Args:
            func: Функция для вызова
            *args, **kwargs: Аргументы функции

        Returns:
            Результат функции

        Raises:
            CircuitBreakerOpenError: Если circuit breaker открыт
        """
        with self._lock:
            # Проверяем состояние
            if self.state == CircuitState.OPEN:
                # Проверяем таймаут
                if time.time() - self.last_failure_time >= self.config.timeout:
                    # Переходим в HALF_OPEN для тестирования
                    logger.info(
                        f"🔌 Circuit Breaker '{self.name}': OPEN → HALF_OPEN (таймаут истёк)"
                    )
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    # Circuit breaker всё ещё открыт
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Wait {self.config.timeout - (time.time() - self.last_failure_time):.1f}s"
                    )

        # Вызываем функцию
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result

        except self.config.expected_exception as e:
            self._on_failure()
            raise

    def on_success(self):
        """Публичный метод обработки успеха"""
        self._on_success()

    def _on_success(self):
        """Обработка успешного вызова"""
        with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                logger.debug(
                    f"🔌 Circuit Breaker '{self.name}': успех в HALF_OPEN ({self.success_count}/{self.config.success_threshold})"
                )

                if self.success_count >= self.config.success_threshold:
                    # Восстановились - закрываем circuit breaker
                    logger.info(
                        f"✅ Circuit Breaker '{self.name}': HALF_OPEN → CLOSED (восстановлен)"
                    )
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0

            elif self.state == CircuitState.CLOSED:
                # Сбрасываем счётчик ошибок при успехе
                if self.failure_count > 0:
                    self.failure_count = max(0, self.failure_count - 1)

            self.last_success_time = time.time()

    def on_failure(self):
        """Публичный метод обработки ошибки"""
        self._on_failure()

    def _on_failure(self):
        """Обработка ошибки"""
        with self._lock:
            self.failure_count += 1
            self.last_failure_time = time.time()

            if self.state == CircuitState.HALF_OPEN:
                # Ошибка в HALF_OPEN - снова открываем
                logger.warning(
                    f"⚠️ Circuit Breaker '{self.name}': HALF_OPEN → OPEN (ошибка при восстановлении)"
                )
                self.state = CircuitState.OPEN
                self.success_count = 0

            elif self.state == CircuitState.CLOSED:
                if self.failure_count >= self.config.failure_threshold:
                    # Превышен порог - открываем circuit breaker
                    logger.warning(
                        f"🔴 Circuit Breaker '{self.name}': CLOSED → OPEN "
                        f"({self.failure_count} ошибок >= {self.config.failure_threshold})"
                    )
                    self.state = CircuitState.OPEN

    def reset(self):
        """Сбрасывает circuit breaker в начальное состояние"""
        with self._lock:
            logger.info(f"🔄 Circuit Breaker '{self.name}': сброс")
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            self.last_failure_time = None
            self.last_success_time = None

    def get_state(self) -> Dict[str, Any]:
        """Возвращает текущее состояние"""
        with self._lock:
            return {
                "name": self.name,
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "last_failure_time": self.last_failure_time,
                "last_success_time": self.last_success_time,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "success_threshold": self.config.success_threshold,
                    "timeout": self.config.timeout,
                },
            }


class CircuitBreakerOpenError(Exception):
    """Исключение когда circuit breaker открыт"""

    pass


# Глобальные circuit breakers для разных сервисов
_api_breaker = None
_db_breaker = None


def get_api_circuit_breaker() -> CircuitBreaker:
    """Получить circuit breaker для API запросов"""
    global _api_breaker
    if _api_breaker is None:
        _api_breaker = CircuitBreaker(
            name="API",
            failure_threshold=5,
            timeout=60.0,
            expected_exception=(ConnectionError, TimeoutError, Exception),
        )
    return _api_breaker


def get_db_circuit_breaker() -> CircuitBreaker:
    """Получить circuit breaker для DB операций"""
    global _db_breaker
    if _db_breaker is None:
        _db_breaker = CircuitBreaker(
            name="Database", failure_threshold=3, timeout=30.0, expected_exception=(Exception,)
        )
    return _db_breaker


if __name__ == "__main__":
    # Пример использования
    logging.basicConfig(level=logging.INFO)

    breaker = CircuitBreaker(name="test", failure_threshold=3, timeout=10.0)

    def risky_function(x):
        if x < 5:
            raise ValueError("Error!")
        return x * 2

    # Тестируем
    for i in range(10):
        try:
            result = breaker.call(risky_function, i)
            print(f"✅ {i} -> {result}")
        except CircuitBreakerOpenError as e:
            print(f"🔴 Circuit breaker открыт: {e}")
            time.sleep(1)
        except Exception as e:
            print(f"❌ Ошибка: {e}")

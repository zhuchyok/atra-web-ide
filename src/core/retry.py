"""
RetryManager - Централизованная retry логика с exponential backoff

Принцип: Self-Validating Code - Обработка ошибок
Цель: Обеспечить надёжную обработку временных ошибок с автоматическими повторами
"""

import asyncio
import logging
import time
from typing import Optional, Callable, Tuple, Type, Union, Any
from dataclasses import dataclass
from functools import wraps
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Конфигурация retry логики"""
    max_retries: int = 3
    initial_delay: float = 1.0
    max_delay: float = 10.0
    exponential_base: float = 2.0
    retry_on: Tuple[Type[Exception], ...] = (Exception,)
    retry_on_not: Tuple[Type[Exception], ...] = ()
    jitter: bool = True
    log_retries: bool = True


class RetryManager:
    """
    Менеджер для управления retry логикой
    
    Обеспечивает:
    - Автоматические повторы с exponential backoff
    - Настраиваемые типы ошибок для retry
    - Логирование попыток
    - Jitter для распределения нагрузки
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Инициализация менеджера retry
        
        Args:
            config: Конфигурация retry. Если None, используется дефолтная
        """
        self.config = config or RetryConfig()
    
    def _should_retry(self, exception: Exception) -> bool:
        """
        Проверка, нужно ли повторять операцию при данной ошибке
        
        Args:
            exception: Исключение
            
        Returns:
            True если нужно повторить, False иначе
        """
        # Проверяем, не входит ли ошибка в список "не повторять"
        if self.config.retry_on_not:
            if isinstance(exception, self.config.retry_on_not):
                return False
        
        # Проверяем, входит ли ошибка в список "повторять"
        if self.config.retry_on:
            return isinstance(exception, self.config.retry_on)
        
        return False
    
    def _calculate_delay(self, attempt: int) -> float:
        """
        Расчёт задержки для попытки
        
        Args:
            attempt: Номер попытки (начиная с 0)
            
        Returns:
            Задержка в секундах
        """
        # Экспоненциальная задержка
        delay = self.config.initial_delay * (self.config.exponential_base ** attempt)
        
        # Ограничение максимальной задержки
        delay = min(delay, self.config.max_delay)
        
        # Jitter для распределения нагрузки
        if self.config.jitter:
            import random
            jitter = random.uniform(0, delay * 0.1)  # 10% jitter
            delay += jitter
        
        return delay
    
    def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Выполнение функции с retry логикой
        
        Args:
            func: Функция для выполнения
            *args: Аргументы функции
            **kwargs: Ключевые аргументы функции
            
        Returns:
            Результат выполнения функции
            
        Raises:
            Последнее исключение если все попытки исчерпаны
        """
        last_exception = None
        
        for attempt in range(self.config.max_retries):
            try:
                result = func(*args, **kwargs)
                
                if attempt > 0 and self.config.log_retries:
                    logger.info(f"✅ Operation succeeded after {attempt + 1} attempts")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Проверяем, нужно ли повторять
                if not self._should_retry(e):
                    if self.config.log_retries:
                        logger.debug(f"❌ Error not retryable: {type(e).__name__}: {e}")
                    raise
                
                # Проверяем, не исчерпаны ли попытки
                if attempt >= self.config.max_retries - 1:
                    if self.config.log_retries:
                        logger.error(f"❌ All {self.config.max_retries} retry attempts exhausted")
                    raise
                
                # Рассчитываем задержку
                delay = self._calculate_delay(attempt)
                
                if self.config.log_retries:
                    logger.warning(
                        f"⚠️ Attempt {attempt + 1}/{self.config.max_retries} failed: "
                        f"{type(e).__name__}: {e}. Retrying in {delay:.2f}s..."
                    )
                
                # Ждём перед следующей попыткой
                time.sleep(delay)
        
        # Не должно доходить сюда, но на всякий случай
        if last_exception:
            raise last_exception
    
    async def execute_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Асинхронное выполнение функции с retry логикой
        
        Args:
            func: Асинхронная функция для выполнения
            *args: Аргументы функции
            **kwargs: Ключевые аргументы функции
            
        Returns:
            Результат выполнения функции
            
        Raises:
            Последнее исключение если все попытки исчерпаны
        """
        last_exception = None
        
        for attempt in range(self.config.max_retries):
            try:
                result = await func(*args, **kwargs)
                
                if attempt > 0 and self.config.log_retries:
                    logger.info(f"✅ Operation succeeded after {attempt + 1} attempts")
                
                return result
                
            except Exception as e:
                last_exception = e
                
                # Проверяем, нужно ли повторять
                if not self._should_retry(e):
                    if self.config.log_retries:
                        logger.debug(f"❌ Error not retryable: {type(e).__name__}: {e}")
                    raise
                
                # Проверяем, не исчерпаны ли попытки
                if attempt >= self.config.max_retries - 1:
                    if self.config.log_retries:
                        logger.error(f"❌ All {self.config.max_retries} retry attempts exhausted")
                    raise
                
                # Рассчитываем задержку
                delay = self._calculate_delay(attempt)
                
                if self.config.log_retries:
                    logger.warning(
                        f"⚠️ Attempt {attempt + 1}/{self.config.max_retries} failed: "
                        f"{type(e).__name__}: {e}. Retrying in {delay:.2f}s..."
                    )
                
                # Ждём перед следующей попыткой
                await asyncio.sleep(delay)
        
        # Не должно доходить сюда, но на всякий случай
        if last_exception:
            raise last_exception


def retry_with_backoff(config: Optional[RetryConfig] = None):
    """
    Декоратор для retry логики с exponential backoff
    
    Args:
        config: Конфигурация retry. Если None, используется дефолтная
        
    Example:
        @retry_with_backoff(
            RetryConfig(
                max_retries=3,
                initial_delay=1.0,
                retry_on=(ConnectionError, TimeoutError)
            )
        )
        def get_price():
            return api.get_price()
    """
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                manager = RetryManager(config)
                return await manager.execute_async(func, *args, **kwargs)
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                manager = RetryManager(config)
                return manager.execute(func, *args, **kwargs)
            return sync_wrapper
    return decorator


def graceful_degradation(default_value: Any = None):
    """
    Декоратор для graceful degradation
    
    При ошибке возвращает дефолтное значение вместо исключения
    
    Args:
        default_value: Значение по умолчанию при ошибке
        
    Example:
        @graceful_degradation(default_value=None)
        @retry_with_backoff(max_retries=2)
        def get_optional_data():
            return api.get_optional_data()
    """
    def decorator(func: Callable) -> Callable:
        if asyncio.iscoroutinefunction(func):
            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Graceful degradation for {func.__name__}: {e}")
                    return default_value
            return async_wrapper
        else:
            @wraps(func)
            def sync_wrapper(*args, **kwargs):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    logger.warning(f"Graceful degradation for {func.__name__}: {e}")
                    return default_value
            return sync_wrapper
    return decorator


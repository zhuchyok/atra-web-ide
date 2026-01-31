"""
Декораторы для автоматического сбора метрик
"""

import time
import logging
from functools import wraps
from typing import Callable, Any, Optional
from src.metrics.filter_metrics import FilterType, record_filter_metrics

logger = logging.getLogger(__name__)


def track_filter_metrics(filter_type: FilterType, 
                        rejection_reason_key: str = 'rejection_reason'):
    """
    Декоратор для автоматического сбора метрик фильтра
    
    Args:
        filter_type: Тип фильтра
        rejection_reason_key: Ключ для получения причины отклонения из kwargs
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            rejection_reason = None
            
            try:
                # Выполнение функции
                result = func(*args, **kwargs)
                
                # Определение успешности
                if isinstance(result, bool):
                    passed = result
                elif isinstance(result, tuple) and len(result) >= 2:
                    # Предполагаем, что первый элемент - это успешность
                    passed = result[0]
                elif hasattr(result, 'passed'):
                    passed = result.passed
                else:
                    # По умолчанию считаем успешным, если не исключение
                    passed = True
                
                # Получение причины отклонения
                if not passed and rejection_reason_key in kwargs:
                    rejection_reason = kwargs[rejection_reason_key]
                
                return result
                
            except Exception as e:
                # В случае исключения считаем неуспешным
                passed = False
                rejection_reason = f"Exception: {str(e)}"
                logger.error(f"Ошибка в фильтре {filter_type.value}: {e}")
                raise
                
            finally:
                # Запись метрик
                processing_time = time.time() - start_time
                record_filter_metrics(
                    filter_type=filter_type,
                    passed=passed,
                    processing_time=processing_time,
                    rejection_reason=rejection_reason
                )
                
                logger.debug(f"Метрики фильтра {filter_type.value}: "
                           f"passed={passed}, time={processing_time:.4f}s")
        
        return wrapper
    return decorator


def track_performance(metric_name: str):
    """
    Декоратор для отслеживания производительности функции
    
    Args:
        metric_name: Название метрики
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                return result
                
            finally:
                processing_time = time.time() - start_time
                logger.debug(f"Функция {func.__name__} ({metric_name}): "
                           f"время выполнения {processing_time:.4f}s")
        
        return wrapper
    return decorator


def track_signal_metrics(signal_type: str = 'unknown'):
    """
    Декоратор для отслеживания метрик сигналов
    
    Args:
        signal_type: Тип сигнала
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                # Логирование метрик сигнала
                processing_time = time.time() - start_time
                logger.info(f"Сигнал {signal_type}: "
                           f"время обработки {processing_time:.4f}s")
                
                return result
                
            except Exception as e:
                processing_time = time.time() - start_time
                logger.error(f"Ошибка в сигнале {signal_type}: "
                           f"время до ошибки {processing_time:.4f}s, ошибка: {e}")
                raise
        
        return wrapper
    return decorator


def track_api_calls(api_name: str):
    """
    Декоратор для отслеживания вызовов API
    
    Args:
        api_name: Название API
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                # Логирование метрик API
                processing_time = time.time() - start_time
                logger.debug(f"API {api_name}: "
                           f"время ответа {processing_time:.4f}s")
                
                return result
                
            except Exception as e:
                processing_time = time.time() - start_time
                logger.error(f"Ошибка API {api_name}: "
                           f"время до ошибки {processing_time:.4f}s, ошибка: {e}")
                raise
        
        return wrapper
    return decorator


def track_database_operations(operation_type: str):
    """
    Декоратор для отслеживания операций с базой данных
    
    Args:
        operation_type: Тип операции (SELECT, INSERT, UPDATE, DELETE)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                
                # Логирование метрик БД
                processing_time = time.time() - start_time
                logger.debug(f"БД {operation_type}: "
                           f"время выполнения {processing_time:.4f}s")
                
                return result
                
            except Exception as e:
                processing_time = time.time() - start_time
                logger.error(f"Ошибка БД {operation_type}: "
                           f"время до ошибки {processing_time:.4f}s, ошибка: {e}")
                raise
        
        return wrapper
    return decorator


class MetricsContext:
    """Контекстный менеджер для сбора метрик"""
    
    def __init__(self, metric_name: str, filter_type: Optional[FilterType] = None):
        self.metric_name = metric_name
        self.filter_type = filter_type
        self.start_time = None
        self.passed = None
        self.rejection_reason = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time:
            processing_time = time.time() - self.start_time
            
            if exc_type:
                # В случае исключения считаем неуспешным
                self.passed = False
                self.rejection_reason = f"Exception: {str(exc_val)}"
            elif self.passed is None:
                # Если не установлено, считаем успешным
                self.passed = True
            
            # Запись метрик, если указан тип фильтра
            if self.filter_type:
                record_filter_metrics(
                    filter_type=self.filter_type,
                    passed=self.passed,
                    processing_time=processing_time,
                    rejection_reason=self.rejection_reason
                )
            
            logger.debug(f"Метрики {self.metric_name}: "
                       f"passed={self.passed}, time={processing_time:.4f}s")
    
    def set_result(self, passed: bool, rejection_reason: Optional[str] = None):
        """Установка результата"""
        self.passed = passed
        self.rejection_reason = rejection_reason


def metrics_context(metric_name: str, filter_type: Optional[FilterType] = None):
    """
    Фабрика для создания контекстного менеджера метрик
    
    Args:
        metric_name: Название метрики
        filter_type: Тип фильтра (опционально)
    
    Returns:
        MetricsContext: Контекстный менеджер
    """
    return MetricsContext(metric_name, filter_type)

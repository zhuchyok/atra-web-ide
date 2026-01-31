"""
Performance Profiling - Профилирование критичных путей

Принцип: Self-Validating Code - Performance Profiling
Цель: Обеспечить профилирование критичных функций и автоматическое обнаружение узких мест
"""

import cProfile
import pstats
import io
import functools
import logging
import time
import asyncio
from typing import Callable, Any, Optional, Dict, List
from dataclasses import dataclass, field
from datetime import datetime, timezone
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@dataclass
class ProfileResult:
    """Результат профилирования"""
    function_name: str
    total_time: float
    cumulative_time: float
    calls: int
    per_call_time: float
    file_path: str
    line_number: int
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class LatencyMetric:
    """Метрика latency"""
    function_name: str
    duration_ms: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    success: bool = True
    error: Optional[str] = None


class PerformanceProfiler:
    """
    Профилировщик производительности

    Обеспечивает:
    - Профилирование функций через cProfile
    - Метрики latency для API вызовов
    - Автоматическое обнаружение узких мест
    """

    def __init__(self, enable_profiling: bool = True, enable_latency: bool = True):
        """
        Инициализация профилировщика

        Args:
            enable_profiling: Включить профилирование через cProfile
            enable_latency: Включить сбор метрик latency
        """
        self.enable_profiling = enable_profiling
        self.enable_latency = enable_latency
        self._profiler: Optional[cProfile.Profile] = None
        self._latency_metrics: List[LatencyMetric] = []
        self._profile_results: List[ProfileResult] = []
        self._threshold_ms: float = 100.0  # Порог для обнаружения узких мест
        self._nesting_level = 0  # Счетчик вложенности для предотвращения конфликтов

    def start_profiling(self) -> None:
        """Начать профилирование с учетом вложенности"""
        if self.enable_profiling:
            if self._nesting_level == 0:
                if self._profiler is None:
                    self._profiler = cProfile.Profile()
                try:
                    self._profiler.enable()
                    logger.debug("Profiling started (root)")
                except Exception as e:
                    logger.debug("Could not start profiling: %s", e)
            self._nesting_level += 1

    def stop_profiling(self) -> Optional[pstats.Stats]:
        """
        Остановить профилирование и получить статистику (только на верхнем уровне)

        Returns:
            Статистика профилирования или None
        """
        if self._profiler and self._nesting_level > 0:
            self._nesting_level -= 1
            if self._nesting_level == 0:
                try:
                    self._profiler.disable()
                    stats = pstats.Stats(self._profiler)
                    logger.debug("Profiling stopped (root)")
                    return stats
                except Exception as e:
                    logger.debug("Could not stop profiling: %s", e)
        return None

    def get_top_functions(self, limit: int = 10) -> List[ProfileResult]:
        """
        Получить топ функций по времени выполнения

        Args:
            limit: Количество функций для возврата

        Returns:
            Список результатов профилирования
        """
        stats = self.stop_profiling()
        if not stats or not self._profiler:
            return []

        results = []
        stream = io.StringIO()
        # Передаем поток в конструктор Stats для исправления E1123
        stats_with_stream = pstats.Stats(self._profiler, stream=stream)
        stats_with_stream.print_stats(limit)
        stats_output = stream.getvalue()

        # Парсим вывод stats (упрощённая версия)
        lines = stats_output.split('\n')
        for line in lines[5:5+limit]:  # Пропускаем заголовки
            if not line.strip():
                continue

            parts = line.split()
            if len(parts) >= 5:
                try:
                    total_time = float(parts[0])
                    cumulative_time = float(parts[1])
                    calls = int(parts[2])
                    per_call = total_time / calls if calls > 0 else 0

                    # Извлекаем имя функции и путь
                    func_info = ' '.join(parts[5:]) if len(parts) > 5 else "unknown"
                    file_path = func_info.split(':', maxsplit=1)[0] if ':' in func_info else "unknown"

                    # Исправляем длинную строку (C0301) и используем maxsplit (C0207)
                    info_parts = func_info.split(':')
                    line_number = int(info_parts[1]) if len(info_parts) > 1 else 0
                    function_name = func_info.split('(', maxsplit=1)[0] if '(' in func_info else func_info

                    results.append(ProfileResult(
                        function_name=function_name,
                        total_time=total_time,
                        cumulative_time=cumulative_time,
                        calls=calls,
                        per_call_time=per_call,
                        file_path=file_path,
                        line_number=line_number
                    ))
                except (ValueError, IndexError):
                    continue

        self._profile_results.extend(results)
        return results

    def record_latency(
        self,
        function_name: str,
        duration_ms: float,
        success: bool = True,
        error: Optional[str] = None
    ) -> None:
        """
        Записать метрику latency

        Args:
            function_name: Имя функции
            duration_ms: Длительность в миллисекундах
            success: Успешность выполнения
            error: Сообщение об ошибке (если есть)
        """
        if self.enable_latency:
            metric = LatencyMetric(
                function_name=function_name,
                duration_ms=duration_ms,
                success=success,
                error=error
            )
            self._latency_metrics.append(metric)

            # Проверяем порог для обнаружения узких мест
            if duration_ms > self._threshold_ms:
                # Используем ленивое форматирование для логов (W1203)
                logger.warning(
                    "Performance bottleneck detected: %s took %.2fms (threshold: %.2fms)",
                    function_name,
                    duration_ms,
                    self._threshold_ms
                )

    def get_latency_stats(self, function_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Получить статистику latency

        Args:
            function_name: Имя функции для фильтрации (если None, все функции)

        Returns:
            Словарь со статистикой
        """
        metrics = self._latency_metrics
        if function_name:
            metrics = [m for m in metrics if m.function_name == function_name]

        if not metrics:
            return {
                "function_name": function_name or "all",
                "count": 0,
                "avg_ms": 0.0,
                "min_ms": 0.0,
                "max_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
                "success_rate": 0.0
            }

        durations = [m.duration_ms for m in metrics]
        durations_sorted = sorted(durations)

        success_count = sum(1 for m in metrics if m.success)

        return {
            "function_name": function_name or "all",
            "count": len(metrics),
            "avg_ms": sum(durations) / len(durations),
            "min_ms": min(durations),
            "max_ms": max(durations),
            "p95_ms": durations_sorted[int(len(durations_sorted) * 0.95)] if durations_sorted else 0.0,
            "p99_ms": durations_sorted[int(len(durations_sorted) * 0.99)] if durations_sorted else 0.0,
            "success_rate": success_count / len(metrics) if metrics else 0.0
        }

    def detect_bottlenecks(self, threshold_ms: Optional[float] = None) -> List[LatencyMetric]:
        """
        Обнаружить узкие места (функции, превышающие порог)

        Args:
            threshold_ms: Порог в миллисекундах (если None, используется дефолтный)

        Returns:
            Список метрик узких мест
        """
        threshold = threshold_ms if threshold_ms is not None else self._threshold_ms
        return [m for m in self._latency_metrics if m.duration_ms > threshold]

    def clear_metrics(self) -> None:
        """Очистить все метрики"""
        self._latency_metrics.clear()
        self._profile_results.clear()
        logger.debug("Performance metrics cleared")


# Глобальный экземпляр для удобства использования
_global_profiler: Optional[PerformanceProfiler] = None


def get_profiler() -> PerformanceProfiler:
    """
    Получить глобальный экземпляр PerformanceProfiler

    Returns:
        Глобальный экземпляр профилировщика
    """
    global _global_profiler
    if _global_profiler is None:
        _global_profiler = PerformanceProfiler()
    return _global_profiler


def profile(func: Optional[Callable] = None, *, threshold_ms: float = 100.0):
    """
    Декоратор для автоматического профилирования функции

    Args:
        func: Функция для профилирования (если None, возвращает декоратор)
        threshold_ms: Порог latency в миллисекундах

    Example:
        @profile(threshold_ms=50.0)
        def expensive_operation():
            # ...
            pass
    """
    def decorator(f: Callable) -> Callable:
        profiler = get_profiler()

        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            profiler.start_profiling()

            try:
                result = f(*args, **kwargs)
                success = True
                error = None
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                profiler.stop_profiling()
                duration_ms = (time.time() - start_time) * 1000
                profiler.record_latency(f.__name__, duration_ms, success, error)

            return result

        @functools.wraps(f)
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            profiler.start_profiling()

            try:
                result = await f(*args, **kwargs)
                success = True
                error = None
            except Exception as e:
                success = False
                error = str(e)
                raise
            finally:
                profiler.stop_profiling()
                duration_ms = (time.time() - start_time) * 1000
                profiler.record_latency(f.__name__, duration_ms, success, error)

            return result

        if asyncio.iscoroutinefunction(f):
            return async_wrapper
        return wrapper

    if func is None:
        return decorator
    return decorator(func)


@contextmanager
def profile_context(name: str = "operation"):
    """
    Context manager для профилирования блока кода

    Args:
        name: Имя операции для профилирования

    Example:
        with profile_context("data_processing"):
            # код для профилирования
            pass
    """
    profiler = get_profiler()
    start_time = time.time()
    profiler.start_profiling()

    try:
        yield
        success = True
        error = None
    except Exception as e:
        success = False
        error = str(e)
        raise
    finally:
        profiler.stop_profiling()
        duration_ms = (time.time() - start_time) * 1000
        profiler.record_latency(name, duration_ms, success, error)

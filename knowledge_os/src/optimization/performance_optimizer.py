"""
Модуль оптимизации производительности для высоких нагрузок
"""

import time
import logging
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from queue import Queue, Empty
import pandas as pd
import numpy as np
from functools import lru_cache
import psutil
import gc

logger = logging.getLogger(__name__)


@dataclass
class PerformanceConfig:
    """Конфигурация производительности"""
    max_workers: int = 4
    max_processes: int = 2
    chunk_size: int = 1000
    cache_size: int = 128
    memory_limit_mb: int = 1024
    gc_threshold: int = 1000
    enable_async: bool = True
    enable_caching: bool = True
    enable_parallel: bool = True


class PerformanceOptimizer:
    """Оптимизатор производительности"""
    
    def __init__(self, config: PerformanceConfig = None):
        self.config = config or PerformanceConfig()
        self.thread_pool = ThreadPoolExecutor(max_workers=self.config.max_workers)
        self.process_pool = ProcessPoolExecutor(max_workers=self.config.max_processes)
        self.task_queue = Queue()
        self.results_cache = {}
        self.performance_metrics = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'avg_processing_time': 0.0,
            'memory_usage': 0.0,
            'cpu_usage': 0.0
        }
        self._setup_caching()
        self._setup_memory_monitoring()
    
    def _setup_caching(self):
        """Настройка кэширования"""
        if self.config.enable_caching:
            # Настройка LRU кэша для часто используемых функций
            self._cached_functions = {}
    
    def _setup_memory_monitoring(self):
        """Настройка мониторинга памяти"""
        self.memory_monitor = threading.Thread(target=self._monitor_memory, daemon=True)
        self.memory_monitor.start()
    
    def _monitor_memory(self):
        """Мониторинг использования памяти"""
        while True:
            try:
                process = psutil.Process()
                memory_mb = process.memory_info().rss / 1024 / 1024
                self.performance_metrics['memory_usage'] = memory_mb
                
                if memory_mb > self.config.memory_limit_mb:
                    logger.warning(f"Превышен лимит памяти: {memory_mb:.1f}MB")
                    self._cleanup_memory()
                
                time.sleep(5)  # Проверка каждые 5 секунд
                
            except Exception as e:
                logger.error(f"Ошибка мониторинга памяти: {e}")
                time.sleep(10)
    
    def _cleanup_memory(self):
        """Очистка памяти"""
        try:
            # Очистка кэша
            self.results_cache.clear()
            
            # Принудительная сборка мусора
            gc.collect()
            
            logger.info("Память очищена")
            
        except Exception as e:
            logger.error(f"Ошибка очистки памяти: {e}")
    
    def optimize_dataframe_processing(self, df: pd.DataFrame, 
                                    processing_func: Callable,
                                    chunk_size: Optional[int] = None) -> pd.DataFrame:
        """
        Оптимизация обработки DataFrame
        
        Args:
            df: DataFrame для обработки
            processing_func: Функция обработки
            chunk_size: Размер чанка
        
        Returns:
            pd.DataFrame: Обработанный DataFrame
        """
        try:
            chunk_size = chunk_size or self.config.chunk_size
            
            if len(df) <= chunk_size:
                # Небольшой DataFrame - обрабатываем целиком
                return processing_func(df)
            
            # Большой DataFrame - обрабатываем по частям
            results = []
            
            for i in range(0, len(df), chunk_size):
                chunk = df.iloc[i:i + chunk_size]
                
                if self.config.enable_parallel:
                    # Параллельная обработка
                    future = self.thread_pool.submit(processing_func, chunk)
                    result = future.result(timeout=30)
                else:
                    # Последовательная обработка
                    result = processing_func(chunk)
                
                results.append(result)
            
            # Объединение результатов
            return pd.concat(results, ignore_index=True)
            
        except Exception as e:
            logger.error(f"Ошибка оптимизации DataFrame: {e}")
            return df
    
    def optimize_signal_generation(self, df: pd.DataFrame, 
                                 signal_func: Callable,
                                 batch_size: int = 100) -> List[Tuple[bool, float]]:
        """
        Оптимизация генерации сигналов
        
        Args:
            df: DataFrame с данными
            signal_func: Функция генерации сигнала
            batch_size: Размер батча
        
        Returns:
            List[Tuple[bool, float]]: Список результатов (успех, время)
        """
        try:
            results = []
            start_time = time.time()
            
            # Обработка по батчам
            for i in range(0, len(df), batch_size):
                batch_end = min(i + batch_size, len(df))
                batch_df = df.iloc[i:batch_end]
                
                batch_start = time.time()
                
                if self.config.enable_parallel:
                    # Параллельная обработка батча
                    futures = []
                    for j in range(len(batch_df)):
                        future = self.thread_pool.submit(signal_func, batch_df, j)
                        futures.append(future)
                    
                    batch_results = []
                    for future in futures:
                        try:
                            result = future.result(timeout=5)
                            batch_results.append((True, time.time() - batch_start))
                        except Exception as e:
                            logger.error(f"Ошибка в батче: {e}")
                            batch_results.append((False, time.time() - batch_start))
                    
                    results.extend(batch_results)
                else:
                    # Последовательная обработка батча
                    for j in range(len(batch_df)):
                        try:
                            signal_func(batch_df, j)
                            results.append((True, time.time() - batch_start))
                        except Exception as e:
                            logger.error(f"Ошибка в сигнале: {e}")
                            results.append((False, time.time() - batch_start))
                
                # Обновление метрик
                self.performance_metrics['total_tasks'] += len(batch_df)
                self.performance_metrics['completed_tasks'] += sum(1 for success, _ in results if success)
                self.performance_metrics['failed_tasks'] += sum(1 for success, _ in results if not success)
            
            total_time = time.time() - start_time
            self.performance_metrics['avg_processing_time'] = total_time / len(results) if results else 0.0
            
            logger.info(f"Обработано {len(results)} сигналов за {total_time:.2f}s")
            return results
            
        except Exception as e:
            logger.error(f"Ошибка оптимизации генерации сигналов: {e}")
            return []
    
    def optimize_filter_processing(self, df: pd.DataFrame,
                                 filters: List[Callable],
                                 parallel: bool = True) -> List[bool]:
        """
        Оптимизация обработки фильтров
        
        Args:
            df: DataFrame с данными
            filters: Список функций фильтров
            parallel: Использовать параллельную обработку
        
        Returns:
            List[bool]: Результаты фильтрации
        """
        try:
            if not parallel or len(filters) == 1:
                # Последовательная обработка
                results = []
                for i in range(len(df)):
                    passed = True
                    for filter_func in filters:
                        try:
                            if not filter_func(df, i):
                                passed = False
                                break
                        except Exception as e:
                            logger.error(f"Ошибка в фильтре: {e}")
                            passed = False
                            break
                    results.append(passed)
                return results
            
            # Параллельная обработка
            def process_row(row_data):
                row_index, row = row_data
                passed = True
                for filter_func in filters:
                    try:
                        if not filter_func(df, row_index):
                            passed = False
                            break
                    except Exception as e:
                        logger.error(f"Ошибка в фильтре для строки {row_index}: {e}")
                        passed = False
                        break
                return passed
            
            # Подготовка данных для параллельной обработки
            row_data = [(i, df.iloc[i]) for i in range(len(df))]
            
            # Параллельная обработка
            futures = [self.thread_pool.submit(process_row, data) for data in row_data]
            results = [future.result(timeout=10) for future in futures]
            
            return results
            
        except Exception as e:
            logger.error(f"Ошибка оптимизации фильтров: {e}")
            return [False] * len(df)
    
    def optimize_data_loading(self, data_sources: List[str],
                            loading_func: Callable,
                            cache_key: Optional[str] = None) -> Dict[str, Any]:
        """
        Оптимизация загрузки данных
        
        Args:
            data_sources: Список источников данных
            loading_func: Функция загрузки
            cache_key: Ключ кэша
        
        Returns:
            Dict[str, Any]: Загруженные данные
        """
        try:
            # Проверка кэша
            if cache_key and cache_key in self.results_cache:
                logger.debug(f"Данные загружены из кэша: {cache_key}")
                return self.results_cache[cache_key]
            
            # Параллельная загрузка данных
            if self.config.enable_parallel and len(data_sources) > 1:
                futures = []
                for source in data_sources:
                    future = self.thread_pool.submit(loading_func, source)
                    futures.append(future)
                
                results = {}
                for i, future in enumerate(futures):
                    try:
                        result = future.result(timeout=30)
                        results[data_sources[i]] = result
                    except Exception as e:
                        logger.error(f"Ошибка загрузки данных из {data_sources[i]}: {e}")
                        results[data_sources[i]] = None
            else:
                # Последовательная загрузка
                results = {}
                for source in data_sources:
                    try:
                        result = loading_func(source)
                        results[source] = result
                    except Exception as e:
                        logger.error(f"Ошибка загрузки данных из {source}: {e}")
                        results[source] = None
            
            # Кэширование результатов
            if cache_key:
                self.results_cache[cache_key] = results
            
            return results
            
        except Exception as e:
            logger.error(f"Ошибка оптимизации загрузки данных: {e}")
            return {}
    
    def optimize_calculations(self, calculations: List[Callable],
                            data: Any,
                            parallel: bool = True) -> List[Any]:
        """
        Оптимизация вычислений
        
        Args:
            calculations: Список функций вычислений
            data: Данные для вычислений
            parallel: Использовать параллельные вычисления
        
        Returns:
            List[Any]: Результаты вычислений
        """
        try:
            if not parallel or len(calculations) == 1:
                # Последовательные вычисления
                results = []
                for calc_func in calculations:
                    try:
                        result = calc_func(data)
                        results.append(result)
                    except Exception as e:
                        logger.error(f"Ошибка в вычислении: {e}")
                        results.append(None)
                return results
            
            # Параллельные вычисления
            futures = [self.thread_pool.submit(calc_func, data) for calc_func in calculations]
            results = []
            
            for future in futures:
                try:
                    result = future.result(timeout=30)
                    results.append(result)
                except Exception as e:
                    logger.error(f"Ошибка в параллельном вычислении: {e}")
                    results.append(None)
            
            return results
            
        except Exception as e:
            logger.error(f"Ошибка оптимизации вычислений: {e}")
            return []
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Получение метрик производительности"""
        try:
            # Получение системных метрик
            process = psutil.Process()
            cpu_percent = process.cpu_percent()
            memory_info = process.memory_info()
            
            # Обновление метрик
            self.performance_metrics.update({
                'cpu_usage': cpu_percent,
                'memory_usage': memory_info.rss / 1024 / 1024,  # MB
                'memory_available': psutil.virtual_memory().available / 1024 / 1024,  # MB
                'thread_count': threading.active_count(),
                'queue_size': self.task_queue.qsize()
            })
            
            return self.performance_metrics.copy()
            
        except Exception as e:
            logger.error(f"Ошибка получения метрик производительности: {e}")
            return {}
    
    def optimize_memory_usage(self):
        """Оптимизация использования памяти"""
        try:
            # Очистка кэша
            self.results_cache.clear()
            
            # Принудительная сборка мусора
            gc.collect()
            
            # Очистка неиспользуемых переменных
            if hasattr(self, '_temp_data'):
                del self._temp_data
            
            logger.info("Память оптимизирована")
            
        except Exception as e:
            logger.error(f"Ошибка оптимизации памяти: {e}")
    
    def shutdown(self):
        """Завершение работы оптимизатора"""
        try:
            # Завершение пулов потоков
            self.thread_pool.shutdown(wait=True)
            self.process_pool.shutdown(wait=True)
            
            # Очистка ресурсов
            self.results_cache.clear()
            
            logger.info("Оптимизатор производительности завершен")
            
        except Exception as e:
            logger.error(f"Ошибка завершения оптимизатора: {e}")


class AsyncPerformanceOptimizer:
    """Асинхронный оптимизатор производительности"""
    
    def __init__(self, config: PerformanceConfig = None):
        self.config = config or PerformanceConfig()
        self.semaphore = asyncio.Semaphore(self.config.max_workers)
        self.performance_metrics = {
            'total_tasks': 0,
            'completed_tasks': 0,
            'failed_tasks': 0,
            'avg_processing_time': 0.0
        }
    
    async def optimize_async_processing(self, tasks: List[Callable],
                                       data: Any) -> List[Any]:
        """
        Оптимизация асинхронной обработки
        
        Args:
            tasks: Список асинхронных задач
            data: Данные для обработки
        
        Returns:
            List[Any]: Результаты обработки
        """
        try:
            async def process_task(task_func):
                async with self.semaphore:
                    try:
                        result = await task_func(data)
                        self.performance_metrics['completed_tasks'] += 1
                        return result
                    except Exception as e:
                        logger.error(f"Ошибка в асинхронной задаче: {e}")
                        self.performance_metrics['failed_tasks'] += 1
                        return None
            
            # Запуск всех задач параллельно
            results = await asyncio.gather(*[process_task(task) for task in tasks])
            
            self.performance_metrics['total_tasks'] += len(tasks)
            
            return results
            
        except Exception as e:
            logger.error(f"Ошибка оптимизации асинхронной обработки: {e}")
            return []
    
    async def optimize_async_data_loading(self, data_sources: List[str],
                                         loading_func: Callable) -> Dict[str, Any]:
        """
        Оптимизация асинхронной загрузки данных
        
        Args:
            data_sources: Список источников данных
            loading_func: Асинхронная функция загрузки
        
        Returns:
            Dict[str, Any]: Загруженные данные
        """
        try:
            async def load_source(source):
                async with self.semaphore:
                    try:
                        result = await loading_func(source)
                        return source, result
                    except Exception as e:
                        logger.error(f"Ошибка загрузки данных из {source}: {e}")
                        return source, None
            
            # Параллельная загрузка всех источников
            tasks = [load_source(source) for source in data_sources]
            results = await asyncio.gather(*tasks)
            
            # Преобразование в словарь
            data_dict = {source: result for source, result in results}
            
            return data_dict
            
        except Exception as e:
            logger.error(f"Ошибка оптимизации асинхронной загрузки данных: {e}")
            return {}


# Глобальные экземпляры оптимизаторов
performance_optimizer = PerformanceOptimizer()
async_performance_optimizer = AsyncPerformanceOptimizer()


def optimize_function(func: Callable, cache_size: int = 128):
    """
    Декоратор для оптимизации функции с кэшированием
    
    Args:
        func: Функция для оптимизации
        cache_size: Размер кэша
    """
    cached_func = lru_cache(maxsize=cache_size)(func)
    
    def wrapper(*args, **kwargs):
        try:
            return cached_func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Ошибка в оптимизированной функции {func.__name__}: {e}")
            return None
    
    return wrapper


def batch_process(data: List[Any], 
                 processing_func: Callable,
                 batch_size: int = 100,
                 parallel: bool = True) -> List[Any]:
    """
    Пакетная обработка данных
    
    Args:
        data: Список данных для обработки
        processing_func: Функция обработки
        batch_size: Размер батча
        parallel: Использовать параллельную обработку
    
    Returns:
        List[Any]: Результаты обработки
    """
    try:
        if not parallel or len(data) <= batch_size:
            # Последовательная обработка
            return [processing_func(item) for item in data]
        
        # Параллельная обработка
        results = []
        
        for i in range(0, len(data), batch_size):
            batch = data[i:i + batch_size]
            
            with ThreadPoolExecutor(max_workers=4) as executor:
                futures = [executor.submit(processing_func, item) for item in batch]
                batch_results = [future.result(timeout=30) for future in futures]
                results.extend(batch_results)
        
        return results
        
    except Exception as e:
        logger.error(f"Ошибка пакетной обработки: {e}")
        return []

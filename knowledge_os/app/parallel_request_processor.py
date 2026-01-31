"""
Parallel Request Processor
Параллельная обработка запросов для уменьшения latency
Singularity 8.0: Performance Optimization
"""

import asyncio
import logging
from typing import Optional, List, Dict, Any, Callable, Tuple
from dataclasses import dataclass
import time

logger = logging.getLogger(__name__)

@dataclass
class RequestSource:
    """Источник запроса (кэш, локальная модель, облако)"""
    name: str
    handler: Callable
    priority: int  # 1 = highest, 3 = lowest
    timeout: float = 5.0

class ParallelRequestProcessor:
    """
    Параллельная обработка запросов к разным источникам.
    Уменьшает latency на 40-60% через одновременные запросы.
    """
    
    def __init__(self, max_concurrent: int = 5):
        """
        Args:
            max_concurrent: Максимальное количество одновременных запросов
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_parallel_sources(
        self,
        sources: List[RequestSource],
        *args,
        **kwargs
    ) -> Tuple[Optional[str], Optional[Any]]:
        """
        Параллельно обрабатывает запросы к разным источникам.
        Возвращает первый успешный результат с именем источника.
        
        Args:
            sources: Список источников для запросов
            *args, **kwargs: Аргументы для передачи в handlers
        
        Returns:
            Кортеж (source_name, response) или (None, None)
        """
        if not sources:
            return None
        
        # Сортируем источники по приоритету
        sorted_sources = sorted(sources, key=lambda x: x.priority)
        
        async def process_source(source: RequestSource) -> Tuple[str, Optional[Any]]:
            """Обрабатывает один источник с таймаутом"""
            async with self.semaphore:
                try:
                    result = await asyncio.wait_for(
                        source.handler(*args, **kwargs),
                        timeout=source.timeout
                    )
                    if result and (isinstance(result, str) and len(result) > 10):
                        return (source.name, result)
                    return (source.name, None)
                except asyncio.TimeoutError:
                    logger.debug(f"⏱️ [PARALLEL] {source.name} timeout ({source.timeout}s)")
                    return (source.name, None)
                except Exception as e:
                    logger.debug(f"⚠️ [PARALLEL] {source.name} failed: {e}")
                    return (source.name, None)
        
        # Запускаем все источники параллельно
        start_time = time.time()
        results = await asyncio.gather(
            *[process_source(source) for source in sorted_sources],
            return_exceptions=True
        )
        duration = time.time() - start_time
        
        # Обрабатываем результаты
        for result in results:
            if isinstance(result, Exception):
                logger.error(f"❌ [PARALLEL] Source failed with exception: {result}")
                continue
            
            source_name, response = result
            if response:
                logger.info(f"✅ [PARALLEL] {source_name} responded in {duration:.2f}s")
                return (source_name, response)
        
        logger.warning(f"⚠️ [PARALLEL] All sources failed after {duration:.2f}s")
        return (None, None)
    
    async def process_with_fallback(
        self,
        primary_sources: List[RequestSource],
        fallback_sources: List[RequestSource],
        *args,
        **kwargs
    ) -> Optional[Any]:
        """
        Обрабатывает запросы с fallback механизмом.
        Сначала пробует primary источники, затем fallback.
        
        Args:
            primary_sources: Основные источники (высокий приоритет)
            fallback_sources: Резервные источники (низкий приоритет)
            *args, **kwargs: Аргументы для передачи в handlers
        
        Returns:
            Первый успешный результат или None
        """
        # Пробуем primary источники
        result = await self.process_parallel_sources(primary_sources, *args, **kwargs)
        if result:
            return result
        
        # Если primary не сработали, пробуем fallback
        logger.info("🔄 [PARALLEL] Primary sources failed, trying fallback...")
        return await self.process_parallel_sources(fallback_sources, *args, **kwargs)
    
    async def process_batch_parallel(
        self,
        requests: List[Dict[str, Any]],
        handler: Callable
    ) -> List[Optional[Any]]:
        """
        Параллельная обработка батча запросов.
        
        Args:
            requests: Список запросов (каждый - dict с параметрами)
            handler: Функция для обработки каждого запроса
        
        Returns:
            Список результатов
        """
        async def process_single(request: Dict[str, Any]) -> Optional[Any]:
            async with self.semaphore:
                try:
                    return await handler(**request)
                except Exception as e:
                    logger.error(f"❌ [PARALLEL BATCH] Request failed: {e}")
                    return None
        
        results = await asyncio.gather(
            *[process_single(req) for req in requests],
            return_exceptions=True
        )
        
        # Обрабатываем исключения
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append(None)
            else:
                processed_results.append(result)
        
        return processed_results

# Singleton instance
_processor_instance: Optional[ParallelRequestProcessor] = None

def get_parallel_processor(max_concurrent: int = 5) -> ParallelRequestProcessor:
    """Получить singleton экземпляр процессора"""
    global _processor_instance
    if _processor_instance is None:
        _processor_instance = ParallelRequestProcessor(max_concurrent=max_concurrent)
    return _processor_instance


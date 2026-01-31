"""
Parallel Execution для Victoria Enhanced
Параллельное выполнение независимых задач
"""

import os
import asyncio
from typing import List, Dict, Any, Callable, Optional
import logging
from concurrent.futures import ThreadPoolExecutor
import time

logger = logging.getLogger(__name__)

class ParallelExecutor:
    """Параллельный исполнитель для независимых задач"""
    
    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
    
    async def execute_parallel(
        self,
        tasks: List[Dict[str, Any]],
        task_func: Callable,
        timeout: Optional[float] = None
    ) -> List[Any]:
        """
        Выполнить задачи параллельно
        
        Args:
            tasks: Список задач (словари с параметрами)
            task_func: Функция для выполнения задачи
            timeout: Таймаут для всех задач
        
        Returns:
            Список результатов
        """
        if not tasks:
            return []
        
        # Создаем корутины для всех задач
        coroutines = []
        for task in tasks:
            if asyncio.iscoroutinefunction(task_func):
                coro = task_func(**task)
            else:
                # Если синхронная функция, оборачиваем в executor
                coro = asyncio.get_event_loop().run_in_executor(
                    self.executor,
                    lambda t=task: task_func(**t)
                )
            coroutines.append(coro)
        
        # Выполняем параллельно
        try:
            if timeout:
                results = await asyncio.wait_for(
                    asyncio.gather(*coroutines, return_exceptions=True),
                    timeout=timeout
                )
            else:
                results = await asyncio.gather(*coroutines, return_exceptions=True)
        except asyncio.TimeoutError:
            logger.warning(f"⏱️ Timeout при параллельном выполнении {len(tasks)} задач")
            results = [None] * len(tasks)
        
        # Обрабатываем результаты и исключения
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"❌ Ошибка в задаче {i}: {result}")
                processed_results.append(None)
            else:
                processed_results.append(result)
        
        return processed_results
    
    async def execute_batch(
        self,
        items: List[Any],
        process_func: Callable,
        batch_size: int = 10,
        timeout: Optional[float] = None
    ) -> List[Any]:
        """
        Обработать элементы батчами параллельно
        
        Args:
            items: Список элементов для обработки
            process_func: Функция обработки одного элемента
            batch_size: Размер батча
            timeout: Таймаут на батч
        
        Returns:
            Список результатов
        """
        results = []
        
        # Разбиваем на батчи
        for i in range(0, len(items), batch_size):
            batch = items[i:i + batch_size]
            
            # Создаем задачи для батча
            tasks = [{"item": item} for item in batch]
            
            # Выполняем батч параллельно
            batch_results = await self.execute_parallel(
                tasks,
                lambda item: process_func(item) if not asyncio.iscoroutinefunction(process_func) else process_func(item),
                timeout=timeout
            )
            
            results.extend(batch_results)
        
        return results
    
    def shutdown(self):
        """Остановить executor"""
        self.executor.shutdown(wait=True)

# Глобальный экземпляр
_parallel_executor: Optional[ParallelExecutor] = None

def get_parallel_executor() -> ParallelExecutor:
    """Получить глобальный экземпляр ParallelExecutor"""
    global _parallel_executor
    if _parallel_executor is None:
        max_workers = int(os.getenv("PARALLEL_EXECUTOR_WORKERS", "4"))
        _parallel_executor = ParallelExecutor(max_workers=max_workers)
    return _parallel_executor

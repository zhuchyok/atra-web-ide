"""
Batch Processor
Объединяет множественные запросы в один для экономии токенов
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

@dataclass
class BatchRequest:
    """Запрос в batch"""
    prompt: str
    category: Optional[str]
    expert_name: str
    timestamp: float
    callback: Any  # Callback для возврата результата

class BatchProcessor:
    """
    Batch Processor для объединения множественных запросов.
    """
    
    def __init__(self, batch_size: int = 5, batch_timeout: float = 2.0):
        """
        Args:
            batch_size: Максимальный размер batch
            batch_timeout: Timeout для накопления batch (секунды)
        """
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.batch_queue: List[BatchRequest] = []
        self._lock = asyncio.Lock()
        self._processing = False
    
    async def add_request(
        self,
        prompt: str,
        category: Optional[str],
        expert_name: str
    ) -> str:
        """
        Добавляет запрос в batch и возвращает результат.
        
        Args:
            prompt: Промпт пользователя
            category: Категория задачи
            expert_name: Имя эксперта
        
        Returns:
            Результат обработки
        """
        # Создаем callback для получения результата
        result_future = asyncio.Future()
        
        request = BatchRequest(
            prompt=prompt,
            category=category,
            expert_name=expert_name,
            timestamp=time.time(),
            callback=result_future
        )
        
        async with self._lock:
            self.batch_queue.append(request)
            
            # Если batch заполнен, обрабатываем сразу
            if len(self.batch_queue) >= self.batch_size:
                await self._process_batch()
            else:
                # Запускаем обработку через timeout если еще не запущена
                if not self._processing:
                    self._processing = True
                    asyncio.create_task(self._process_batch_after_timeout())
        
        # Ждем результат
        return await result_future
    
    async def _process_batch_after_timeout(self):
        """Обрабатывает batch после timeout"""
        await asyncio.sleep(self.batch_timeout)
        async with self._lock:
            if self.batch_queue:
                await self._process_batch()
            self._processing = False
    
    async def _process_batch(self):
        """Обрабатывает накопленный batch"""
        if not self.batch_queue:
            return
        
        # Извлекаем запросы из очереди
        requests = self.batch_queue[:self.batch_size]
        self.batch_queue = self.batch_queue[self.batch_size:]
        
        logger.info(f"📦 [BATCH] Processing {len(requests)} requests in batch")
        
        # Объединяем похожие запросы
        combined_prompt = self._combine_requests(requests)
        
        # Обрабатываем объединенный запрос
        # (здесь должна быть логика обработки через ai_core)
        try:
            # Импортируем ai_core для обработки
            from ai_core import run_smart_agent_async
            
            # Обрабатываем объединенный запрос
            combined_result = await run_smart_agent_async(
                combined_prompt,
                expert_name=requests[0].expert_name,
                category=requests[0].category
            )
            
            # Разделяем результат обратно на отдельные ответы
            results = self._split_results(combined_result, len(requests))
            
            # Возвращаем результаты через callbacks
            for i, request in enumerate(requests):
                if i < len(results):
                    if not request.callback.done():
                        request.callback.set_result(results[i])
                else:
                    if not request.callback.done():
                        request.callback.set_result("Ошибка обработки batch")
        except Exception as e:
            logger.error(f"❌ [BATCH] Error processing batch: {e}")
            # Возвращаем ошибку всем запросам
            for request in requests:
                if not request.callback.done():
                    request.callback.set_exception(e)
    
    def _combine_requests(self, requests: List[BatchRequest]) -> str:
        """Объединяет запросы в один промпт (оптимизированная версия для экономии токенов)"""
        # Используем более компактный формат для экономии токенов
        combined = "Обработай запросы:\n"
        for i, request in enumerate(requests, 1):
            # Убираем избыточные слова для экономии
            combined += f"{i}. {request.prompt}\n"
        combined += "\nФормат ответа:\n1: ...\n2: ...\n"
        return combined
    
    def _split_results(self, combined_result: str, count: int) -> List[str]:
        """Разделяет объединенный результат на отдельные ответы"""
        # Простая эвристика: ищем паттерны "Ответ N:"
        results = []
        lines = combined_result.split('\n')
        current_answer = []
        answer_num = 1
        
        for line in lines:
            if f"Ответ {answer_num}:" in line or f"Ответ {answer_num} " in line:
                if current_answer:
                    results.append('\n'.join(current_answer))
                    current_answer = []
                answer_num += 1
                # Добавляем строку без префикса
                clean_line = line.split(':', 1)[-1].strip()
                if clean_line:
                    current_answer.append(clean_line)
            else:
                if current_answer or line.strip():
                    current_answer.append(line)
        
        # Добавляем последний ответ
        if current_answer:
            results.append('\n'.join(current_answer))
        
        # Если не удалось разделить, возвращаем одинаковый результат для всех
        if len(results) != count:
            logger.warning(f"⚠️ [BATCH] Could not split result into {count} parts, using same result for all")
            results = [combined_result] * count
        
        return results[:count]

# Singleton instance
_batch_processor_instance = None

async def get_batch_processor(batch_size: int = 5, batch_timeout: float = 2.0) -> BatchProcessor:
    """Получает singleton instance batch processor"""
    global _batch_processor_instance
    if _batch_processor_instance is None:
        _batch_processor_instance = BatchProcessor(batch_size=batch_size, batch_timeout=batch_timeout)
    return _batch_processor_instance


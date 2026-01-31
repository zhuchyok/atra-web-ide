"""
Streaming Service - Singularity v5.0 Integration
SSE стриминг с интеллектуальной обработкой
"""
import asyncio
import json
from typing import AsyncGenerator, Optional, Callable
import logging

logger = logging.getLogger(__name__)


class StreamingProcessor:
    """
    Процессор стриминга ответов из Singularity v5.0
    
    Возможности:
    - Буферизация токенов для плавного отображения
    - Обнаружение кода для подсветки
    - Определение завершённых предложений
    """
    
    def __init__(
        self,
        buffer_size: int = 5,
        min_delay: float = 0.05,
        max_delay: float = 0.2
    ):
        self.buffer_size = buffer_size
        self.min_delay = min_delay
        self.max_delay = max_delay
        self._buffer = []
        self._in_code_block = False
        self._code_language = None
    
    async def process_stream(
        self,
        source: AsyncGenerator[str, None],
        on_chunk: Optional[Callable] = None
    ) -> AsyncGenerator[dict, None]:
        """
        Обработка входящего стрима
        
        Args:
            source: Источник данных (AsyncGenerator)
            on_chunk: Callback для каждого обработанного chunk
            
        Yields:
            Обработанные SSE события
        """
        async for chunk in source:
            processed = self._process_chunk(chunk)
            
            if processed:
                if on_chunk:
                    on_chunk(processed)
                
                yield processed
                
                # Адаптивная задержка
                delay = self._calculate_delay(processed)
                await asyncio.sleep(delay)
        
        # Flush буфера
        if self._buffer:
            final = self._flush_buffer()
            yield final
    
    def _process_chunk(self, chunk: str) -> Optional[dict]:
        """Обработка отдельного chunk"""
        # Проверка на код
        if '```' in chunk:
            if not self._in_code_block:
                self._in_code_block = True
                # Извлечение языка
                if '```' in chunk:
                    parts = chunk.split('```')
                    if len(parts) > 1 and parts[1]:
                        lang = parts[1].split('\n')[0].strip()
                        self._code_language = lang if lang else None
            else:
                self._in_code_block = False
                self._code_language = None
        
        # Буферизация
        self._buffer.append(chunk)
        
        if len(self._buffer) >= self.buffer_size:
            return self._flush_buffer()
        
        return None
    
    def _flush_buffer(self) -> dict:
        """Flush буфера и возврат обработанного контента"""
        content = ''.join(self._buffer)
        self._buffer = []
        
        return {
            'type': 'chunk',
            'content': content,
            'in_code_block': self._in_code_block,
            'code_language': self._code_language
        }
    
    def _calculate_delay(self, chunk: dict) -> float:
        """Адаптивный расчёт задержки для плавного UX"""
        content = chunk.get('content', '')
        
        # Больше задержки для кода (даёт время на подсветку)
        if chunk.get('in_code_block'):
            return self.max_delay
        
        # Меньше задержки для обычного текста
        if len(content) > 20:
            return self.min_delay
        
        return (self.min_delay + self.max_delay) / 2


async def stream_with_processing(
    source: AsyncGenerator[str, None],
    processor: Optional[StreamingProcessor] = None
) -> AsyncGenerator[str, None]:
    """
    Утилита для стриминга с обработкой
    
    Args:
        source: Источник данных
        processor: Процессор (опционально)
        
    Yields:
        SSE события в формате строк
    """
    if processor is None:
        processor = StreamingProcessor()
    
    async for chunk in processor.process_stream(source):
        yield f"data: {json.dumps(chunk)}\n\n"


def create_sse_event(
    event_type: str,
    data: dict,
    event_id: Optional[str] = None
) -> str:
    """
    Создание SSE события
    
    Args:
        event_type: Тип события (start, chunk, end, error)
        data: Данные события
        event_id: ID события (опционально)
        
    Returns:
        Форматированное SSE событие
    """
    lines = []
    
    if event_id:
        lines.append(f"id: {event_id}")
    
    lines.append(f"event: {event_type}")
    lines.append(f"data: {json.dumps(data)}")
    lines.append("")
    
    return "\n".join(lines) + "\n"

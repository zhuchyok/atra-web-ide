"""
Streaming Processor
Стриминг ответов для улучшения воспринимаемой скорости
"""

import asyncio
import logging
import httpx
import json
from typing import AsyncGenerator, Optional
import os

logger = logging.getLogger(__name__)

# Config
MAC_LLM_URL = os.getenv('MAC_LLM_URL', 'http://localhost:11434')
SERVER_LLM_URL = os.getenv('SERVER_LLM_URL', 'http://localhost:11434')

class StreamingProcessor:
    """
    Обработка стриминга ответов от локальных моделей.
    """
    
    def __init__(self):
        self.nodes = [
            {"name": "Mac Studio (Ollama)", "url": MAC_LLM_URL, "priority": 1}
        ]
    
    async def stream_local_llm(
        self,
        prompt: str,
        model: str = "qwen2.5-coder:32b",  # MLX модель (Mac Studio)
        system_prompt: str = "",
        node_url: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Стримит ответ от локальной модели.
        
        Args:
            prompt: Промпт пользователя
            model: Модель для использования
            system_prompt: Системный промпт
            node_url: URL узла (если None, выбирается автоматически)
        
        Yields:
            Chunks ответа
        """
        full_prompt = f"{system_prompt}\n\nUser: {prompt}\nAssistant:"
        
        # Выбираем узел
        if node_url is None:
            # Пробуем узлы по очереди
            for node in self.nodes:
                try:
                    async with httpx.AsyncClient(timeout=2.0) as client:
                        response = await client.get(f"{node['url']}/api/tags")
                        if response.status_code == 200:
                            node_url = node['url']
                            break
                except:
                    continue
        
        if node_url is None:
            logger.error("❌ [STREAMING] No available nodes")
            return
        
        # Стримим ответ
        stream_url = f"{node_url}/api/generate"
        
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream(
                    'POST',
                    stream_url,
                    json={
                        "model": model,
                        "prompt": full_prompt,
                        "stream": True
                    }
                ) as response:
                    if response.status_code != 200:
                        logger.error(f"❌ [STREAMING] Error: {response.status_code}")
                        return
                    
                    async for line in response.aiter_lines():
                        if not line:
                            continue
                        
                        try:
                            chunk_data = json.loads(line)
                            if 'response' in chunk_data:
                                yield chunk_data['response']
                            if chunk_data.get('done', False):
                                break
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error(f"❌ [STREAMING] Error: {e}")
            return
    
    async def stream_to_openai_format(
        self,
        prompt: str,
        model: str = "qwen2.5-coder:32b",  # MLX модель (Mac Studio)
        response_id: str = "chatcmpl-default",
        created: int = None
    ) -> AsyncGenerator[dict, None]:
        """
        Стримит ответ в формате OpenAI API.
        
        Yields:
            Chunks в формате OpenAI
        """
        if created is None:
            import time
            created = int(time.time())
        
        accumulated = ""
        async for chunk in self.stream_local_llm(prompt, model):
            accumulated += chunk
            
            # Форматируем в OpenAI format
            yield {
                "id": response_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [{
                    "index": 0,
                    "delta": {"content": chunk},
                    "finish_reason": None
                }]
            }
        
        # Финальный chunk
        yield {
            "id": response_id,
            "object": "chat.completion.chunk",
            "created": created,
            "model": model,
            "choices": [{
                "index": 0,
                "delta": {},
                "finish_reason": "stop"
            }]
        }

# Singleton instance
_streaming_processor_instance = None

def get_streaming_processor() -> StreamingProcessor:
    """Получает singleton instance streaming processor"""
    global _streaming_processor_instance
    if _streaming_processor_instance is None:
        _streaming_processor_instance = StreamingProcessor()
    return _streaming_processor_instance


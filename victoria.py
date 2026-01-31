"""
Victoria Agent Client (Улучшенная версия)
HTTP клиент для взаимодействия с Victoria :8010
Retry logic, timeout handling, error recovery
"""
import httpx
import asyncio
from typing import AsyncGenerator, Optional
import logging
import json
from datetime import datetime

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class VictoriaClient:
    """Клиент для Victoria Agent с улучшенной обработкой ошибок"""
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.victoria_url
        self.timeout = httpx.Timeout(
            settings.victoria_timeout,
            connect=10.0
        )
        self.max_retries = 3
        self.retry_delay = 1.0
    
    async def _retry_request(self, func, *args, **kwargs):
        """Повторная попытка запроса с экспоненциальной задержкой"""
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Victoria request failed (attempt {attempt + 1}/{self.max_retries}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Victoria request failed after {self.max_retries} attempts: {e}")
        
        raise last_error
    
    async def run(
        self, 
        prompt: str, 
        expert_name: Optional[str] = None,
        stream: bool = False
    ) -> dict:
        """
        Выполнить задачу через Victoria
        
        Args:
            prompt: Текст запроса (goal)
            expert_name: Имя эксперта (опционально)
            stream: Использовать стриминг
        
        Returns:
            Результат выполнения
        """
        async def _make_request():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                payload = {
                    "goal": prompt,  # Victoria expects 'goal', not 'prompt'
                    "max_steps": 500,  # Limit steps for chat responses
                }
                
                response = await client.post(
                    f"{self.base_url}/run",
                    json=payload
                )
                response.raise_for_status()
                return response.json()
        
        try:
            data = await self._retry_request(_make_request)
            # Map Victoria response to expected format
            # Victoria может вернуть output в разных форматах
            output = data.get("output", "")
            if not output and "result" in data:
                output = data.get("result", "")
            if not output and "response" in data:
                output = data.get("response", "")
            
            logger.info(f"Victoria response: status={data.get('status')}, output_length={len(output) if output else 0}")
            
            return {
                "status": data.get("status", "success"),
                "result": output,
                "response": output,
                "raw": data  # Сохраняем полный ответ для отладки
            }
        except httpx.HTTPError as e:
            logger.error(f"Victoria error: {e}")
            return {
                "status": "error",
                "error": str(e),
                "result": None
            }
    
    async def run_stream(
        self, 
        prompt: str, 
        expert_name: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Стриминг ответа от Victoria
        
        Yields:
            Части ответа в формате SSE
        """
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            payload = {
                "prompt": prompt,
                "stream": True
            }
            if expert_name:
                payload["expert_name"] = expert_name
            
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/run",
                    json=payload
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            yield line
            except httpx.HTTPError as e:
                logger.error(f"Victoria stream error: {e}")
                yield json.dumps({"error": str(e)})
    
    async def status(self) -> dict:
        """Получить статус Victoria"""
        async def _make_request():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/status")
                response.raise_for_status()
                return response.json()
        
        try:
            return await self._retry_request(_make_request)
        except httpx.HTTPError as e:
            logger.error(f"Victoria status error: {e}")
            return {"status": "offline", "error": str(e)}
    
    async def health(self) -> dict:
        """Health check Victoria"""
        async def _make_request():
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{self.base_url}/health")
                response.raise_for_status()
                return response.json()
        
        try:
            result = await self._retry_request(_make_request)
            return {"status": "healthy", **result}
        except httpx.HTTPError as e:
            return {"status": "unhealthy", "error": str(e)}


# Singleton instance
victoria_client = VictoriaClient()


async def get_victoria_client() -> VictoriaClient:
    """Dependency для FastAPI"""
    return victoria_client

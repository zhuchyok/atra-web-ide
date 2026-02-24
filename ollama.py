"""
Ollama Client (Улучшенная версия)
HTTP клиент для локальных LLM моделей
Retry logic, timeout handling, connection pooling
"""
import httpx
from typing import AsyncGenerator, Optional, List
import logging
import json
import asyncio

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class OllamaClient:
    """Клиент для Ollama API с улучшенной обработкой ошибок"""

    # Модели (70b/104b удалены)
    MODELS = {
        "complex": "qwen2.5-coder:32b",
        "enterprise": "qwen2.5-coder:32b",
        "reasoning": "qwq:32b",
        "complex_alt": "qwen2.5-coder:32b",
        "coding": "qwen2.5-coder:32b",                 # ~20GB - Качественный код
        "fast": "phi3.5:3.8b",                         # ~2.5GB - Быстрые задачи
        "fast_light": "phi3:mini-4k",                  # ~2GB - Быстрые ответы
        "default": "qwen2.5:3b",                       # ~2GB - По умолчанию
        "tiny": "tinyllama:1.1b-chat"                  # ~700MB - Очень быстрые
    }

    # Быстрая модель для чата (по умолчанию)
    FAST_MODEL = "qwen2.5:3b"  # Используем быструю модель по умолчанию

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.ollama_url
        self.timeout = httpx.Timeout(
            settings.ollama_timeout,
            connect=10.0
        )
        self.max_retries = 2
        self.retry_delay = 2.0

    async def _retry_request(self, func, *args, **kwargs):
        """Повторная попытка запроса"""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(
                        f"Ollama request failed (attempt {attempt + 1}/{self.max_retries}), "
                        f"retrying in {delay}s: {e}"
                    )
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Ollama request failed after {self.max_retries} attempts: {e}")

        raise last_error

    async def list_models(self) -> List[dict]:
        """Получить список доступных моделей"""
        async def _make_request():
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                return response.json()

        try:
            data = await self._retry_request(_make_request)
            return data.get("models", [])
        except httpx.HTTPError as e:
            logger.error(f"Ollama list_models error: {e}")
            return []

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        stream: bool = False
    ) -> dict:
        """
        Генерация ответа от модели

        Args:
            prompt: Текст запроса
            model: Название модели
            system: Системный промпт
            stream: Использовать стриминг

        Returns:
            Результат генерации
        """
        model = model or settings.default_model

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": stream
        }
        if system:
            payload["system"] = system

        async def _make_request():
            logger.info(f"📤 Отправка запроса в Ollama: {self.base_url}/api/generate")
            logger.info(f"📦 Payload: model={payload.get('model')}, prompt_length={len(payload.get('prompt', ''))}")
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                )
                logger.info(f"📥 Ответ Ollama: HTTP {response.status_code}")
                if response.status_code != 200:
                    logger.error(f"❌ Ошибка Ollama: {response.status_code} - {response.text[:200]}")
                response.raise_for_status()
                return response.json()

        try:
            return await self._retry_request(_make_request)
        except httpx.HTTPError as e:
            logger.error(f"Ollama generate error: {e}")
            return {"error": str(e)}

    async def generate_stream(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Стриминг генерации

        Yields:
            JSON строки с частями ответа
        """
        model = model or settings.default_model

        payload = {
            "model": model,
            "prompt": prompt,
            "stream": True
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                async with client.stream(
                    "POST",
                    f"{self.base_url}/api/generate",
                    json=payload
                ) as response:
                    response.raise_for_status()
                    async for line in response.aiter_lines():
                        if line:
                            yield line
            except httpx.HTTPError as e:
                logger.error(f"Ollama stream error: {e}")
                yield json.dumps({"error": str(e)})

    async def health(self) -> dict:
        """Health check Ollama"""
        async def _make_request():
            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
                return {"status": "healthy"}

        try:
            return await self._retry_request(_make_request)
        except httpx.HTTPError as e:
            return {"status": "unhealthy", "error": str(e)}


# Singleton instance
ollama_client = OllamaClient()


async def get_ollama_client() -> OllamaClient:
    """Dependency для FastAPI"""
    return ollama_client

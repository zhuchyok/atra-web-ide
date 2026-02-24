"""
Ollama Client (Улучшенная версия)
HTTP клиент для локальных LLM моделей
Retry logic, timeout handling, connection pooling
Поддержка Ollama Cloud Models и Claude Code Integration
"""

import asyncio
import json
import logging
import os
from collections.abc import AsyncGenerator
from typing import List, Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class OllamaClient:
    """Клиент для Ollama API с улучшенной обработкой ошибок и поддержкой Cloud Models"""

    # Локальные модели (70b/104b удалены — см. MLX_PYTHON_CRASH_CAUSE)
    MODELS = {
        "complex": "qwen3-v1:30b",  # ~19GB - Qwen 3 (NEW)
        "enterprise": "qwen3-v1:30b",
        "reasoning": "lfm2.5-thinking:1.2b",  # ~730MB - Thinking (NEW)
        "complex_alt": "qwen2.5-coder:32b",
        "coding": "qwen2.5-coder:32b",  # ~20GB - Качественный код
        "fast": "lfm2.5-thinking:1.2b",  # ~730MB - Быстрые задачи
        "fast_light": "phi3:mini-4k",  # ~2GB - Быстрые ответы
        "default": "qwen2.5:3b",  # ~2GB - По умолчанию
        "tiny": "tinyllama:1.1b-chat",  # ~700MB - Очень быстрые
        "embedding": "qwen3-embedding:4b",  # ~2.5GB - Эмбеддинги (NEW)
    }

    # Cloud Models (Ollama Cloud - работают без локального GPU)
    CLOUD_MODELS = {
        "cloud_large": "gpt-oss:120b-cloud",  # 120B параметров - Cloud
        "cloud_medium": "gpt-oss:20b-cloud",  # 20B параметров - Cloud
        "cloud_coding": "qwen3-coder-cloud",  # Coding модель - Cloud
        "cloud_reasoning": "glm-4.7-cloud",  # Reasoning модель - Cloud
    }

    # Claude Code рекомендованные модели
    CLAUDE_CODE_MODELS = ["qwen3-coder", "glm-4.7", "gpt-oss:20b", "gpt-oss:120b"]

    # Быстрая модель для чата (по умолчанию)
    FAST_MODEL = "qwen2.5:3b"  # Используем быструю модель по умолчанию

    def __init__(self, base_url: Optional[str] = None, use_cloud: bool = False):
        """
        Инициализация Ollama клиента

        Args:
            base_url: URL Ollama сервера (по умолчанию из settings)
            use_cloud: Использовать Ollama Cloud API (https://ollama.com)
        """
        if use_cloud:
            # Использование Ollama Cloud API
            self.base_url = "https://ollama.com"
            self.api_key = os.getenv("OLLAMA_API_KEY")
            if not self.api_key:
                logger.warning("⚠️ OLLAMA_API_KEY не установлен для Cloud API")
        else:
            self.base_url = base_url or settings.ollama_url
            self.api_key = None

        self.timeout = httpx.Timeout(settings.ollama_timeout, connect=10.0)
        self.max_retries = 2
        self.retry_delay = 2.0
        self.use_cloud = use_cloud

    async def _retry_request(self, func, *args, **kwargs):
        """Повторная попытка запроса"""
        last_error = None

        for attempt in range(self.max_retries):
            try:
                return await func(*args, **kwargs)
            except (httpx.HTTPError, httpx.TimeoutException) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2**attempt)
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
            headers = {}
            if self.use_cloud and self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(f"{self.base_url}/api/tags", headers=headers)
                response.raise_for_status()
                return response.json()

        try:
            data = await self._retry_request(_make_request)
            return data.get("models", [])
        except httpx.HTTPError as e:
            logger.error(f"Ollama list_models error: {e}")
            return []

    async def pull_model(self, model_name: str) -> dict:
        """
        Загрузить модель (pull) из Ollama

        Args:
            model_name: Имя модели для загрузки (например, "gpt-oss:120b-cloud")

        Returns:
            Результат загрузки
        """

        async def _make_request():
            headers = {}
            if self.use_cloud and self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
                response = await client.post(
                    f"{self.base_url}/api/pull", json={"name": model_name}, headers=headers
                )
                response.raise_for_status()
                return response.json()

        try:
            logger.info(f"📥 Загрузка модели: {model_name}")
            return await self._retry_request(_make_request)
        except httpx.HTTPError as e:
            logger.error(f"Ollama pull_model error: {e}")
            return {"error": str(e)}

    def get_anthropic_compatible_config(self) -> dict:
        """
        Получить конфигурацию для Anthropic-compatible API (Claude Code)

        Returns:
            Словарь с переменными окружения для Claude Code
        """
        return {
            "ANTHROPIC_AUTH_TOKEN": "ollama",
            "ANTHROPIC_API_KEY": "",
            "ANTHROPIC_BASE_URL": self.base_url or "http://localhost:11434",
        }

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        stream: bool = False,
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

        payload = {"model": model, "prompt": prompt, "stream": stream}
        if system:
            payload["system"] = system

        async def _make_request():
            headers = {}
            if self.use_cloud and self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            logger.info(f"📤 Отправка запроса в Ollama: {self.base_url}/api/generate")
            logger.info(
                f"📦 Payload: model={payload.get('model')}, prompt_length={len(payload.get('prompt', ''))}"
            )
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate", json=payload, headers=headers
                )
                logger.info(f"📥 Ответ Ollama: HTTP {response.status_code}")
                if response.status_code != 200:
                    logger.error(
                        f"❌ Ошибка Ollama: {response.status_code} - {response.text[:200]}"
                    )
                response.raise_for_status()
                return response.json()

        try:
            return await self._retry_request(_make_request)
        except httpx.HTTPError as e:
            logger.error(f"Ollama generate error: {e}")
            return {"error": str(e)}

    async def generate_stream(
        self, prompt: str, model: Optional[str] = None, system: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        """
        Стриминг генерации

        Yields:
            JSON строки с частями ответа
        """
        model = model or settings.default_model

        payload = {"model": model, "prompt": prompt, "stream": True}
        if system:
            payload["system"] = system

        headers = {}
        if self.use_cloud and self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                async with client.stream(
                    "POST", f"{self.base_url}/api/generate", json=payload, headers=headers
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
            headers = {}
            if self.use_cloud and self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(timeout=httpx.Timeout(5.0)) as client:
                response = await client.get(f"{self.base_url}/api/tags", headers=headers)
                response.raise_for_status()
                return {"status": "healthy", "mode": "cloud" if self.use_cloud else "local"}

        try:
            return await self._retry_request(_make_request)
        except httpx.HTTPError as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "mode": "cloud" if self.use_cloud else "local",
            }


# Singleton instance
ollama_client = OllamaClient()


async def get_ollama_client() -> OllamaClient:
    """Dependency для FastAPI"""
    return ollama_client

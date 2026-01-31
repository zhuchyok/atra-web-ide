"""
MLX Client - Подключение к MLX API Server (приоритет над Ollama)
Использует MLX API Server на порту 11435 через HTTP API
"""
import logging
from typing import Optional, Dict
import httpx
import asyncio
import os

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# URL MLX API Server
MLX_API_URL = os.getenv("MLX_API_URL", "http://localhost:11435")


class MLXClient:
    """Клиент для MLX API Server через HTTP API"""
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or MLX_API_URL
        self.timeout = httpx.Timeout(120.0, connect=10.0)
        self.max_retries = 2
        self.retry_delay = 1.0
    
    async def _check_availability(self) -> bool:
        """Проверка доступности MLX API Server"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                if response.status_code == 200:
                    data = response.json()
                    # Принимаем "healthy" и "degraded" как доступные (degraded = перегружен, но работает)
                    status = data.get("status")
                    return status in ("healthy", "degraded")
        except Exception:
            pass
        return False
    
    def is_available(self) -> bool:
        """Проверка доступности MLX (синхронная, кэшированная)"""
        # Используем кэшированную проверку для быстрого ответа
        # Реальная проверка будет в generate()
        return True  # Всегда возвращаем True, проверка будет в generate()
    
    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 512,
        model: Optional[str] = None
    ) -> Dict:
        """
        Генерация ответа через MLX API Server
        
        Args:
            prompt: Текст запроса
            system: Системный промпт
            max_tokens: Максимальное количество токенов
            model: Имя модели (опционально, будет выбран автоматически)
        
        Returns:
            Результат генерации
        """
        # Проверяем доступность перед запросом
        if not await self._check_availability():
            return {"error": "MLX API Server недоступен"}
        
        try:
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            
            # Формируем запрос к MLX API Server
            payload = {
                "prompt": full_prompt,
                "max_tokens": max_tokens,
                "temperature": 0.7
            }
            if model:
                payload["model"] = model
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    f"{self.base_url}/api/generate",
                    json=payload
                )
                response.raise_for_status()
                data = response.json()
                
                # MLX API Server возвращает {"response": "...", "model": "..."}
                if "response" in data:
                    return {
                        "response": data["response"],
                        "model": data.get("model", model or "mlx"),
                        "source": "mlx_api_server"
                    }
                # Или может вернуть {"text": "..."} для совместимости
                elif "text" in data:
                    return {
                        "response": data["text"],
                        "model": data.get("model", model or "mlx"),
                        "source": "mlx_api_server"
                    }
                elif "error" in data:
                    return {"error": data["error"]}
                else:
                    logger.warning(f"Неожиданный формат ответа от MLX API Server: {data}")
                    return {"error": "Неожиданный формат ответа от MLX API Server"}
                    
        except httpx.HTTPError as e:
            logger.error(f"MLX API Server HTTP error: {e}")
            return {"error": f"Ошибка подключения к MLX API Server: {str(e)}"}
        except Exception as e:
            logger.error(f"MLX generate error: {e}")
            return {"error": str(e)}
    
    async def health(self) -> Dict:
        """Health check MLX API Server"""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{self.base_url}/health")
                if response.status_code == 200:
                    return response.json()
        except Exception as e:
            logger.debug(f"MLX health check failed: {e}")
        
        return {"status": "unavailable", "error": "MLX API Server недоступен"}


# Singleton instance
mlx_client = MLXClient()


async def get_mlx_client() -> MLXClient:
    """Dependency для FastAPI"""
    return mlx_client

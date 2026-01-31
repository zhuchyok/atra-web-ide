"""
Health Check Endpoint
Простой HTTP endpoint для мониторинга состояния системы
Singularity 8.0: Quick Wins
"""

import asyncio
import logging
import asyncpg
import os
import httpx
from typing import Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')
SERVER_LLM_URL = os.getenv('SERVER_LLM_URL', 'http://localhost:11434')

class HealthCheck:
    """
    Health Check для мониторинга состояния системы.
    Предоставляет простой HTTP endpoint.
    """
    
    def __init__(self, db_url: str = DB_URL):
        """
        Args:
            db_url: URL базы данных
        """
        self.db_url = db_url
    
    async def check_health(self) -> Dict[str, Any]:
        """
        Проверяет состояние всех компонентов системы.
        
        Returns:
            Словарь с состоянием компонентов
        """
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "components": {}
        }
        
        # Проверка БД
        db_healthy = await self._check_database()
        health_status["components"]["database"] = {
            "status": "healthy" if db_healthy else "unhealthy",
            "available": db_healthy
        }
        
        # Проверка локальных моделей
        local_models_healthy = await self._check_local_models()
        health_status["components"]["local_models"] = {
            "status": "healthy" if local_models_healthy else "unhealthy",
            "available": local_models_healthy
        }
        
        # Проверка кэша
        cache_healthy = await self._check_cache()
        health_status["components"]["cache"] = {
            "status": "healthy" if cache_healthy else "unhealthy",
            "available": cache_healthy
        }
        
        # Общий статус
        all_healthy = db_healthy and (local_models_healthy or cache_healthy)
        health_status["status"] = "healthy" if all_healthy else "degraded"
        
        return health_status
    
    async def _check_database(self) -> bool:
        """Проверяет доступность БД"""
        try:
            conn = await asyncio.wait_for(
                asyncpg.connect(self.db_url),
                timeout=2.0
            )
            await conn.execute("SELECT 1")
            await conn.close()
            return True
        except Exception as e:
            logger.debug(f"⚠️ [HEALTH CHECK] БД недоступна: {e}")
            return False
    
    async def _check_local_models(self) -> bool:
        """Проверяет доступность локальных моделей"""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                response = await client.get(f"{SERVER_LLM_URL}/api/tags")
                return response.status_code == 200
        except Exception as e:
            logger.debug(f"⚠️ [HEALTH CHECK] Локальные модели недоступны: {e}")
            return False
    
    async def _check_cache(self) -> bool:
        """Проверяет доступность кэша"""
        try:
            conn = await asyncio.wait_for(
                asyncpg.connect(self.db_url),
                timeout=2.0
            )
            await conn.execute("SELECT 1 FROM semantic_ai_cache LIMIT 1")
            await conn.close()
            return True
        except Exception as e:
            logger.debug(f"⚠️ [HEALTH CHECK] Кэш недоступен: {e}")
            return False
    
    def get_health_response(self, health_status: Dict[str, Any]) -> tuple:
        """
        Формирует HTTP ответ для health check.
        
        Args:
            health_status: Статус здоровья системы
        
        Returns:
            Кортеж (status_code, response_body)
        """
        import json
        
        if health_status["status"] == "healthy":
            status_code = 200
        else:
            status_code = 503  # Service Unavailable
        
        response_body = json.dumps(health_status, indent=2, ensure_ascii=False)
        
        return (status_code, response_body)

# Singleton instance
_health_check_instance: HealthCheck = None

def get_health_check(db_url: str = DB_URL) -> HealthCheck:
    """Получить singleton экземпляр health check"""
    global _health_check_instance
    if _health_check_instance is None:
        _health_check_instance = HealthCheck(db_url=db_url)
    return _health_check_instance


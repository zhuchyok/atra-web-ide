"""
Автоматический выбор модели с fallback на доступные модели
"""

import asyncio
import httpx
import logging
import time
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

# Кэш для списка моделей (чтобы не делать частые запросы к /api/tags)
_models_cache = {"data": None, "timestamp": 0}
_MODELS_CACHE_TTL = 120  # 2 минуты кэш для списка моделей


async def check_model_available(model_name: str, mlx_url: str = None, timeout: float = 2.0) -> bool:
    """
    Проверяет доступность модели через MLX API Server (ТОЛЬКО MLX)
    
    Args:
        model_name: Имя модели для проверки
        mlx_url: URL MLX API Server (если None, определяется автоматически)
        timeout: Таймаут проверки
        
    Returns:
        True если модель доступна, False иначе
    """
    import os
    
    # Определяем правильный URL для MLX (в Docker используем host.docker.internal)
    if mlx_url is None:
        is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
        if is_docker:
            mlx_url = os.getenv("MLX_API_URL", "http://host.docker.internal:11435")
        else:
            mlx_url = os.getenv("MLX_API_URL", "http://localhost:11435")
    
    # Проверяем кэш сначала
    current_time = time.time()
    if _models_cache["data"] and (current_time - _models_cache["timestamp"]) < _MODELS_CACHE_TTL:
        models = _models_cache["data"]
    else:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                # Проверяем через /api/tags
                response = await client.get(f"{mlx_url}/api/tags")
                if response.status_code == 200:
                    models_data = response.json()
                    models = models_data.get("models", [])
                    # Обновляем кэш
                    _models_cache = {"data": models, "timestamp": current_time}
                else:
                    # Если ошибка, но есть кэш - используем его
                    if _models_cache["data"]:
                        models = _models_cache["data"]
                    else:
                        return False
        except Exception as e:
            logger.debug(f"MLX API Server недоступен для проверки {model_name}: {e}")
            # Если есть кэш, используем его
            if _models_cache["data"]:
                models = _models_cache["data"]
            else:
                return False
    
    # Проверяем, есть ли модель в списке и она exists=True
    for model in models:
        model_name_in_list = model.get("name", "")
        if model_name_in_list == model_name and model.get("exists", False):
            logger.debug(f"✅ Модель {model_name} найдена в MLX API Server (exists=True)")
            return True
    # Если модель есть в списке, но exists=False, все равно пробуем (может быть загружена)
    for model in models:
        if model.get("name") == model_name:
            logger.debug(f"⚠️ Модель {model_name} найдена в MLX, но exists=False, пробуем использовать")
            return True  # Пробуем использовать даже если exists=False
    
    return False


async def select_available_model(
    priorities: List[str],
    mlx_url: str = None,
    category: str = "unknown"
) -> Optional[str]:
    """
    Выбирает первую доступную модель из списка приоритетов
    Проверяет ТОЛЬКО MLX API Server (Ollama не используется)
    
    Args:
        priorities: Список моделей в порядке приоритета
        mlx_url: URL MLX API Server (если None, определяется автоматически)
        category: Категория задачи (для логирования)
        
    Returns:
        Имя первой доступной модели или None
    """
    import os
    
    logger.info(f"🔍 Выбор модели для категории '{category}' из {len(priorities)} вариантов...")
    
    # Определяем правильный URL для MLX (в Docker используем host.docker.internal)
    if mlx_url is None:
        is_docker = os.path.exists('/.dockerenv') or os.getenv('DOCKER_CONTAINER', 'false').lower() == 'true'
        if is_docker:
            mlx_url = os.getenv("MLX_API_URL", "http://host.docker.internal:11435")
        else:
            mlx_url = os.getenv("MLX_API_URL", "http://localhost:11435")
    
    for i, model in enumerate(priorities):
        logger.debug(f"   Проверка модели {i+1}/{len(priorities)}: {model}")
        # Проверяем ТОЛЬКО MLX API Server
        if await check_model_available(model, mlx_url):
            logger.info(f"✅ Выбрана модель: {model} (приоритет {i+1})")
            return model
        else:
            logger.debug(f"   ⏭️  Модель {model} недоступна")
    
    logger.warning(f"⚠️  Ни одна модель из списка недоступна для категории '{category}'")
    return None


async def get_best_model_for_category(
    category: str,
    model_priorities: Dict[str, List[str]],
    mlx_url: str = None
) -> Optional[str]:
    """
    Получает лучшую доступную модель для категории задачи
    
    Args:
        category: Категория задачи (reasoning, coding, fast, tiny, etc.)
        model_priorities: Словарь приоритетов моделей по категориям
        mlx_url: URL MLX API Server (если None, определяется автоматически)
        
    Returns:
        Имя лучшей доступной модели или None
    """
    if category not in model_priorities:
        logger.warning(f"⚠️  Неизвестная категория: {category}")
        return None
    
    priorities = model_priorities[category]
    return await select_available_model(priorities, mlx_url, category)


"""
Experts Router - Улучшенная версия с кэшированием
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
import logging

from app.services.knowledge_os import KnowledgeOSClient, get_knowledge_os_client
from app.services.cache import get_cache

logger = logging.getLogger(__name__)
router = APIRouter()


class Expert(BaseModel):
    """Эксперт ATRA"""
    id: str
    name: str
    role: Optional[str] = None
    system_prompt: Optional[str] = None
    created_at: Optional[str] = None


@router.get("/", response_model=List[Expert])
async def list_experts(
    knowledge_os: KnowledgeOSClient = Depends(get_knowledge_os_client)
) -> List[Expert]:
    """
    Получить список всех экспертов
    
    Returns:
        Список из 58+ экспертов ATRA
    """
    cache = get_cache()
    cache_key = "experts:list"
    
    # Проверяем кэш
    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug("Experts list served from cache")
        return cached
    
    try:
        experts = await knowledge_os.get_experts()
        result = [
            Expert(
                id=str(e["id"]),
                name=e["name"],
                role=e.get("role"),
                system_prompt=e.get("system_prompt"),
                created_at=str(e.get("created_at")) if e.get("created_at") else None
            )
            for e in experts
        ]
        
        # Сохраняем в кэш
        cache.set(cache_key, result, ttl=300)  # 5 минут
        
        return result
    except Exception as e:
        logger.error(f"List experts error: {e}", exc_info=True)
        # Возвращаем fallback список если БД недоступна
        fallback = [
            Expert(id="1", name="Виктория", role="Team Lead"),
            Expert(id="2", name="Вероника", role="Local Developer"),
            Expert(id="3", name="Дмитрий", role="ML Engineer"),
            Expert(id="4", name="Игорь", role="Backend Developer"),
            Expert(id="5", name="Сергей", role="DevOps Engineer"),
            Expert(id="6", name="Анна", role="QA Engineer"),
            Expert(id="7", name="Максим", role="Data Analyst"),
            Expert(id="8", name="Елена", role="Monitor"),
            Expert(id="9", name="Алексей", role="Security Engineer"),
            Expert(id="10", name="Павел", role="Trading Strategy Developer"),
        ]
        logger.warning(f"Using fallback experts list (DB unavailable)")
        return fallback


@router.get("/{expert_id}", response_model=Expert)
async def get_expert(
    expert_id: str,
    knowledge_os: KnowledgeOSClient = Depends(get_knowledge_os_client)
) -> Expert:
    """
    Получить эксперта по ID
    
    Returns:
        Информация об эксперте
    """
    cache = get_cache()
    cache_key = f"expert:{expert_id}"
    
    # Проверяем кэш
    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug(f"Expert {expert_id} served from cache")
        return cached
    
    try:
        expert = await knowledge_os.get_expert(expert_id)
        
        if not expert:
            raise HTTPException(
                status_code=404,
                detail=f"Expert {expert_id} not found"
            )
        
        result = Expert(
            id=str(expert["id"]),
            name=expert["name"],
            role=expert.get("role"),
            system_prompt=expert.get("system_prompt"),
            created_at=str(expert.get("created_at")) if expert.get("created_at") else None
        )
        
        # Сохраняем в кэш
        cache.set(cache_key, result, ttl=600)  # 10 минут
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get expert error: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Internal server error while fetching expert"
        )

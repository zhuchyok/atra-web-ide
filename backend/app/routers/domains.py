"""
Domains Router - Knowledge OS домены (35 доменов)
"""
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
import logging

from app.services.knowledge_os import KnowledgeOSClient, get_knowledge_os_client
from app.services.cache import get_cache

logger = logging.getLogger(__name__)
router = APIRouter()


class Domain(BaseModel):
    """Домен Knowledge OS"""
    id: str
    name: str
    description: Optional[str] = None
    created_at: Optional[str] = None


@router.get("/", response_model=List[Domain])
async def list_domains(
    knowledge_os: KnowledgeOSClient = Depends(get_knowledge_os_client)
) -> List[Domain]:
    """
    Получить список всех доменов Knowledge OS (35 доменов).

    Returns:
        Список доменов
    """
    cache = get_cache()
    cache_key = "domains:list"

    cached = cache.get(cache_key)
    if cached is not None:
        logger.debug("Domains list served from cache")
        return cached

    try:
        rows = await knowledge_os.get_domains()
        result = [
            Domain(
                id=str(d["id"]),
                name=d["name"],
                description=d.get("description"),
                created_at=str(d["created_at"]) if d.get("created_at") else None,
            )
            for d in rows
        ]
        cache.set(cache_key, result, ttl=300)
        return result
    except Exception as e:
        logger.error(f"List domains error: {e}", exc_info=True)
        return []

"""
Knowledge Router - Поиск по знаниям Knowledge OS
"""
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import List, Optional, Any
import logging

from app.services.knowledge_os import KnowledgeOSClient, get_knowledge_os_client

logger = logging.getLogger(__name__)
router = APIRouter()


class KnowledgeItem(BaseModel):
    """Элемент знания"""
    id: str
    content: str
    metadata: Optional[Any] = None
    confidence_score: Optional[float] = None
    domain_id: Optional[str] = None
    created_at: Optional[str] = None


@router.get("", response_model=List[KnowledgeItem])
@router.get("/", response_model=List[KnowledgeItem])
async def search_knowledge(
    q: str = Query(..., min_length=1, max_length=500, description="Поисковый запрос"),
    limit: int = Query(10, ge=1, le=100, description="Макс. результатов"),
    domain_id: Optional[str] = Query(None, description="Фильтр по домену"),
    knowledge_os: KnowledgeOSClient = Depends(get_knowledge_os_client),
) -> List[KnowledgeItem]:
    """
    Поиск по знаниям Knowledge OS.

    Returns:
        Список релевантных знаний (content, confidence_score, domain_id, ...)
    """
    try:
        rows = await knowledge_os.search_knowledge(
            query=q.strip(),
            limit=limit,
            domain_id=domain_id,
        )
        out = []
        for r in rows:
            try:
                sc = r.get("confidence_score")
                confidence_score = float(sc) if sc is not None else None
            except (TypeError, ValueError):
                confidence_score = None
            out.append(
                KnowledgeItem(
                    id=str(r.get("id", "")),
                    content=r.get("content") or "",
                    metadata=r.get("metadata"),
                    confidence_score=confidence_score,
                    domain_id=str(r["domain_id"]) if r.get("domain_id") else None,
                    created_at=str(r["created_at"]) if r.get("created_at") else None,
                )
            )
        return out
    except Exception as e:
        logger.error(f"Search knowledge error: {e}", exc_info=True)
        return []

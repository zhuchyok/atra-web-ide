from fastapi import APIRouter, HTTPException
from typing import Dict, List, Any
import os
import logging
from ..services.knowledge_service import knowledge_service

# Пытаемся импортировать SandboxManager
try:
    from knowledge_os.app.sandbox_manager import get_sandbox_manager
except ImportError:
    try:
        from app.sandbox_manager import get_sandbox_manager
    except ImportError:
        get_sandbox_manager = lambda: None

router = APIRouter(prefix="/api/sandbox", tags=["sandbox"])
logger = logging.getLogger(__name__)

@router.get("/status/{expert_name}")
async def get_sandbox_status(expert_name: str):
    """Возвращает статус песочницы для конкретного эксперта."""
    manager = get_sandbox_manager()
    if not manager or not manager.client:
        return {"status": "unavailable", "reason": "Docker not connected"}
    
    container_name = manager.get_container_name(expert_name)
    try:
        container = manager.client.containers.get(container_name)
        return {
            "status": container.status,
            "container": container_name,
            "image": container.image.tags[0] if container.image.tags else "unknown",
            "created": container.attrs.get('Created')
        }
    except Exception:
        return {"status": "not_found", "container": container_name}

@router.post("/reset/{expert_name}")
async def reset_sandbox(expert_name: str):
    """Сбрасывает (удаляет) песочницу эксперта."""
    manager = get_sandbox_manager()
    if not manager:
        raise HTTPException(status_code=503, detail="Sandbox Manager unavailable")
    
    manager.cleanup_sandbox(expert_name)
    return {"status": "success", "message": f"Sandbox for {expert_name} reset"}

@router.get("/experiments")
async def get_recent_experiments(limit: int = 10):
    """Возвращает последние логи выполнения в песочницах из БД."""
    # В реальной системе мы бы брали это из таблицы sandbox_logs
    # Пока возвращаем моки, имитируя запрос к БД
    return [
        {"time": "21:15", "expert": "Вероника", "task": "Тест миграции v2", "result": "✅ Успех"},
        {"time": "20:40", "expert": "Игорь", "task": "Нагрузка на Redis", "result": "⚠️ Warning: Latency > 5ms"}
    ]

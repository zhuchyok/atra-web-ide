"""
Централизованная обработка ошибок
"""
from fastapi import Request, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
import logging
import traceback
import os
import asyncio
from typing import Any

logger = logging.getLogger(__name__)


async def trigger_war_room_async(error_msg: str):
    """Фоновый вызов War Room, чтобы не блокировать ответ пользователю"""
    try:
        # Пытаемся импортировать из knowledge_os
        import sys
        ko_path = os.getenv("KNOWLEDGE_OS_PATH", "/app/knowledge_os")
        if ko_path not in sys.path:
            sys.path.append(ko_path)
            
        from app.war_room import trigger_war_room_if_needed
        await trigger_war_room_if_needed(error_msg, severity="critical")
    except Exception as e:
        logger.error(f"Failed to trigger War Room: {e}")


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """Обработчик HTTP исключений"""
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "type": "http_exception",
                "message": exc.detail,
                "status_code": exc.status_code,
                "path": str(request.url.path)
            }
        }
    )


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Обработчик ошибок валидации"""
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "error": {
                "type": "validation_error",
                "message": "Validation error",
                "details": exc.errors(),
                "path": str(request.url.path)
            }
        }
    )


async def general_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Обработчик общих исключений"""
    tb = traceback.format_exc()
    error_msg = f"Unhandled exception at {request.method} {request.url.path}: {exc}\n{tb}"
    
    logger.error(
        f"Unhandled exception: {exc}",
        exc_info=True,
        extra={
            "path": str(request.url.path),
            "method": request.method,
            "traceback": tb
        }
    )
    
    # [SINGULARITY 14.3] Trigger War Room on critical errors
    asyncio.create_task(trigger_war_room_async(error_msg))
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "error": {
                "type": "internal_server_error",
                "message": "An unexpected error occurred",
                "path": str(request.url.path)
            }
        }
    )

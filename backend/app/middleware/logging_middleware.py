"""
Structured Logging Middleware
"""

import json
import logging
import time
from typing import Any, Dict

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class StructuredLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware для структурированного логирования"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Логируем запрос
        log_data: Dict[str, Any] = {
            "type": "request",
            "method": request.method,
            "path": str(request.url.path),
            "query_params": dict(request.query_params),
            "client_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        }

        logger.info(json.dumps(log_data))

        # Выполняем запрос
        response = await call_next(request)

        # Логируем ответ
        process_time = time.time() - start_time
        log_data = {
            "type": "response",
            "method": request.method,
            "path": str(request.url.path),
            "status_code": response.status_code,
            "process_time": round(process_time, 3),
            "client_ip": request.client.host if request.client else None,
        }

        logger.info(json.dumps(log_data))

        # Добавляем заголовок с временем обработки
        response.headers["X-Process-Time"] = str(round(process_time, 3))

        return response

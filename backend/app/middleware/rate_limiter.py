"""
Rate Limiting Middleware
"""
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from collections import defaultdict
import time
import logging
from typing import Dict, Tuple

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RateLimiter:
    """Простой in-memory rate limiter"""
    
    def __init__(self):
        self.requests_per_minute: Dict[str, list] = defaultdict(list)
        self.requests_per_hour: Dict[str, list] = defaultdict(list)
        self.cleanup_interval = 60  # секунды
        self.last_cleanup = time.time()
    
    def _get_client_id(self, request: Request) -> str:
        """Получить идентификатор клиента"""
        # Используем IP адрес
        client_ip = request.client.host if request.client else "unknown"
        return f"{client_ip}:{request.url.path}"
    
    def _cleanup_old_requests(self):
        """Очистить старые записи"""
        current_time = time.time()
        if current_time - self.last_cleanup < self.cleanup_interval:
            return
        
        # Очистка запросов старше минуты
        minute_ago = current_time - 60
        for client_id in list(self.requests_per_minute.keys()):
            self.requests_per_minute[client_id] = [
                ts for ts in self.requests_per_minute[client_id] if ts > minute_ago
            ]
            if not self.requests_per_minute[client_id]:
                del self.requests_per_minute[client_id]
        
        # Очистка запросов старше часа
        hour_ago = current_time - 3600
        for client_id in list(self.requests_per_hour.keys()):
            self.requests_per_hour[client_id] = [
                ts for ts in self.requests_per_hour[client_id] if ts > hour_ago
            ]
            if not self.requests_per_hour[client_id]:
                del self.requests_per_hour[client_id]
        
        self.last_cleanup = current_time
    
    def check_rate_limit(self, request: Request) -> Tuple[bool, str]:
        """
        Проверить rate limit
        
        Returns:
            (allowed, message)
        """
        if not settings.rate_limit_enabled:
            return True, ""
        
        self._cleanup_old_requests()
        
        client_id = self._get_client_id(request)
        current_time = time.time()
        
        # Проверка лимита в минуту
        minute_requests = self.requests_per_minute[client_id]
        minute_requests = [ts for ts in minute_requests if ts > current_time - 60]
        self.requests_per_minute[client_id] = minute_requests
        
        if len(minute_requests) >= settings.rate_limit_per_minute:
            return False, f"Rate limit exceeded: {settings.rate_limit_per_minute} requests per minute"
        
        # Проверка лимита в час
        hour_requests = self.requests_per_hour[client_id]
        hour_requests = [ts for ts in hour_requests if ts > current_time - 3600]
        self.requests_per_hour[client_id] = hour_requests
        
        if len(hour_requests) >= settings.rate_limit_per_hour:
            return False, f"Rate limit exceeded: {settings.rate_limit_per_hour} requests per hour"
        
        # Добавляем текущий запрос
        minute_requests.append(current_time)
        hour_requests.append(current_time)
        
        return True, ""


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware для rate limiting"""
    
    def __init__(self, app):
        super().__init__(app)
        self.rate_limiter = RateLimiter()
    
    async def dispatch(self, request: Request, call_next):
        # Пропускаем health checks, docs, метрики
        if request.url.path in ["/health", "/docs", "/openapi.json", "/", "/metrics", "/metrics/summary"]:
            return await call_next(request)
        
        allowed, message = self.rate_limiter.check_rate_limit(request)
        
        if not allowed:
            logger.warning(f"Rate limit exceeded for {request.client.host}: {message}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={
                    "error": "rate_limit_exceeded",
                    "message": message,
                    "retry_after": 60
                }
            )
        
        response = await call_next(request)
        return response

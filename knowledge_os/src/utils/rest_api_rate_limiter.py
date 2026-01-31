#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Rate Limiter Middleware для REST API
Защита от DDoS и злоупотреблений
"""

import time
import logging
from typing import Dict, Optional, Tuple
from collections import defaultdict, deque
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

logger = logging.getLogger(__name__)


class RateLimiter:
    """Rate limiter с sliding window алгоритмом"""
    
    def __init__(
        self,
        requests_per_minute: int = 60,
        requests_per_hour: int = 1000,
        window_size: int = 60
    ):
        self.requests_per_minute = requests_per_minute
        self.requests_per_hour = requests_per_hour
        self.window_size = window_size
        
        # Хранилище запросов: {ip: deque([timestamp1, timestamp2, ...])}
        self.requests: Dict[str, deque] = defaultdict(lambda: deque(maxlen=1000))
        self.hourly_requests: Dict[str, deque] = defaultdict(lambda: deque(maxlen=10000))
    
    def is_allowed(self, ip: str) -> Tuple[bool, Optional[int]]:
        """
        Проверяет, разрешен ли запрос
        
        Returns:
            (allowed, retry_after_seconds)
        """
        now = time.time()
        
        # Очищаем старые запросы (старше window_size секунд)
        requests_deque = self.requests[ip]
        while requests_deque and now - requests_deque[0] > self.window_size:
            requests_deque.popleft()
        
        # Очищаем старые запросы (старше часа)
        hourly_deque = self.hourly_requests[ip]
        while hourly_deque and now - hourly_deque[0] > 3600:
            hourly_deque.popleft()
        
        # Проверяем лимит в минуту
        if len(requests_deque) >= self.requests_per_minute:
            oldest_request = requests_deque[0]
            retry_after = int(self.window_size - (now - oldest_request)) + 1
            return False, retry_after
        
        # Проверяем лимит в час
        if len(hourly_deque) >= self.requests_per_hour:
            oldest_request = hourly_deque[0]
            retry_after = int(3600 - (now - oldest_request)) + 1
            return False, retry_after
        
        # Запрос разрешен
        requests_deque.append(now)
        hourly_deque.append(now)
        return True, None
    
    def get_remaining(self, ip: str) -> Dict[str, int]:
        """Возвращает оставшиеся запросы для IP"""
        requests_deque = self.requests[ip]
        hourly_deque = self.hourly_requests[ip]
        
        return {
            "remaining_per_minute": max(0, self.requests_per_minute - len(requests_deque)),
            "remaining_per_hour": max(0, self.requests_per_hour - len(hourly_deque))
        }


# Глобальный rate limiter
_global_rate_limiter = RateLimiter(
    requests_per_minute=60,  # 60 запросов в минуту
    requests_per_hour=1000   # 1000 запросов в час
)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware для rate limiting запросов"""
    
    def __init__(self, app, rate_limiter: Optional[RateLimiter] = None):
        super().__init__(app)
        self.rate_limiter = rate_limiter or _global_rate_limiter
    
    async def dispatch(self, request: Request, call_next):
        # Получаем IP адрес клиента
        client_ip = request.client.host if request.client else "unknown"
        
        # Проверяем rate limit (исключаем health check из лимитов)
        if request.url.path != "/api/v1/health":
            allowed, retry_after = self.rate_limiter.is_allowed(client_ip)
            
            if not allowed:
                logger.warning(f"Rate limit exceeded for IP {client_ip}")
                response = Response(
                    content=f"Rate limit exceeded. Try again after {retry_after} seconds.",
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    headers={
                        "Retry-After": str(retry_after),
                        "X-RateLimit-Limit-Minute": str(self.rate_limiter.requests_per_minute),
                        "X-RateLimit-Limit-Hour": str(self.rate_limiter.requests_per_hour),
                    }
                )
                return response
        
        # Выполняем запрос
        response = await call_next(request)
        
        # Добавляем заголовки rate limit
        if request.url.path != "/api/v1/health":
            remaining = self.rate_limiter.get_remaining(client_ip)
            response.headers["X-RateLimit-Remaining-Minute"] = str(remaining["remaining_per_minute"])
            response.headers["X-RateLimit-Remaining-Hour"] = str(remaining["remaining_per_hour"])
            response.headers["X-RateLimit-Limit-Minute"] = str(self.rate_limiter.requests_per_minute)
            response.headers["X-RateLimit-Limit-Hour"] = str(self.rate_limiter.requests_per_hour)
        
        return response


def get_rate_limiter() -> RateLimiter:
    """Возвращает глобальный rate limiter"""
    return _global_rate_limiter

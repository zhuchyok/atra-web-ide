"""
Rate Limiter
Защита от DDoS и злоупотреблений через rate limiting
Singularity 8.0: Security and Reliability
"""

import asyncio
import logging
import asyncpg
import os
import time
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta, timezone
from collections import defaultdict

logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

class RateLimiter:
    """
    Rate Limiter для защиты от злоупотреблений.
    Ограничивает количество запросов по пользователям.
    """
    
    def __init__(self, db_url: str = DB_URL):
        """
        Args:
            db_url: URL базы данных
        """
        self.db_url = db_url
        # In-memory кэш для быстрого доступа
        self._rate_cache: Dict[str, Dict[str, any]] = defaultdict(dict)
        self._cache_ttl = 60  # 1 минута
        
        # Лимиты (можно настроить через environment variables)
        self.requests_per_minute = int(os.getenv('RATE_LIMIT_PER_MINUTE', '30'))
        self.requests_per_hour = int(os.getenv('RATE_LIMIT_PER_HOUR', '500'))
        self.max_requests_per_hour = int(os.getenv('MAX_REQUESTS_PER_HOUR', '1000'))  # Для блокировки
    
    async def check_rate_limit(self, user_id: str, identifier: Optional[str] = None) -> Tuple[bool, Optional[str]]:
        """
        Проверяет, не превышен ли rate limit для пользователя.
        
        Args:
            user_id: ID пользователя
            identifier: Дополнительный идентификатор (например, IP адрес)
        
        Returns:
            Кортеж (allowed, error_message)
            - allowed: True если запрос разрешен
            - error_message: Сообщение об ошибке, если запрос заблокирован
        """
        # Используем identifier или user_id как ключ
        key = identifier or user_id
        
        # Проверяем in-memory кэш
        now = time.time()
        if key in self._rate_cache:
            cache_entry = self._rate_cache[key]
            if now - cache_entry.get('last_check', 0) < self._cache_ttl:
                # Используем кэшированные данные
                if cache_entry.get('blocked', False):
                    return (False, "⚠️ Доступ временно ограничен. Попробуйте позже.")
                if not cache_entry.get('allowed', True):
                    return (False, cache_entry.get('error_message', "⚠️ Превышен лимит запросов."))
                return (True, None)
        
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                # Проверяем наличие таблицы
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'rate_limits'
                    )
                """)
                
                if not table_exists:
                    # Если таблицы нет, используем только in-memory проверку
                    return self._check_memory_rate_limit(key)
                
                # Получаем статистику запросов за последний час
                stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 minute') as requests_last_minute,
                        COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '1 hour') as requests_last_hour
                    FROM rate_limits
                    WHERE user_id = $1
                    AND created_at > NOW() - INTERVAL '1 hour'
                """, user_id)
                
                requests_last_minute = stats['requests_last_minute'] or 0
                requests_last_hour = stats['requests_last_hour'] or 0
                
                # Проверяем лимиты
                if requests_last_hour >= self.max_requests_per_hour:
                    # Блокировка на 1 час
                    await conn.execute("""
                        INSERT INTO rate_limits (user_id, request_count, blocked, created_at)
                        VALUES ($1, 1, TRUE, NOW())
                        ON CONFLICT (user_id) DO UPDATE 
                        SET blocked = TRUE, created_at = NOW()
                    """, user_id)
                    
                    self._rate_cache[key] = {
                        'blocked': True,
                        'last_check': now,
                        'error_message': "⚠️ Превышен максимальный лимит запросов. Доступ заблокирован на 1 час."
                    }
                    
                    logger.warning(f"🚨 [RATE LIMITER] Пользователь {user_id} заблокирован (>{self.max_requests_per_hour} запросов/час)")
                    return (False, "⚠️ Превышен максимальный лимит запросов. Доступ заблокирован на 1 час.")
                
                if requests_last_minute >= self.requests_per_minute:
                    self._rate_cache[key] = {
                        'allowed': False,
                        'last_check': now,
                        'error_message': f"⚠️ Превышен лимит: {self.requests_per_minute} запросов в минуту. Подождите немного."
                    }
                    return (False, f"⚠️ Превышен лимит: {self.requests_per_minute} запросов в минуту. Подождите немного.")
                
                if requests_last_hour >= self.requests_per_hour:
                    self._rate_cache[key] = {
                        'allowed': False,
                        'last_check': now,
                        'error_message': f"⚠️ Превышен лимит: {self.requests_per_hour} запросов в час. Подождите немного."
                    }
                    return (False, f"⚠️ Превышен лимит: {self.requests_per_hour} запросов в час. Подождите немного.")
                
                # Запрос разрешен, записываем в БД
                await conn.execute("""
                    INSERT INTO rate_limits (user_id, request_count, created_at)
                    VALUES ($1, 1, NOW())
                """, user_id)
                
                # Обновляем кэш
                self._rate_cache[key] = {
                    'allowed': True,
                    'last_check': now
                }
                
                return (True, None)
            finally:
                await conn.close()
        except Exception as e:
            logger.error(f"❌ [RATE LIMITER] Ошибка проверки rate limit: {e}")
            # В случае ошибки разрешаем запрос (fail-open)
            return (True, None)
    
    def _check_memory_rate_limit(self, key: str) -> Tuple[bool, Optional[str]]:
        """Проверяет rate limit только в памяти (fallback)"""
        now = time.time()
        
        if key not in self._rate_cache:
            self._rate_cache[key] = {
                'requests': [],
                'last_check': now
            }
        
        cache_entry = self._rate_cache[key]
        requests = cache_entry.get('requests', [])
        
        # Удаляем старые запросы (старше 1 минуты)
        requests = [req_time for req_time in requests if now - req_time < 60]
        
        # Проверяем лимит
        if len(requests) >= self.requests_per_minute:
            return (False, f"⚠️ Превышен лимит: {self.requests_per_minute} запросов в минуту.")
        
        # Добавляем текущий запрос
        requests.append(now)
        cache_entry['requests'] = requests
        cache_entry['last_check'] = now
        
        return (True, None)
    
    async def record_request(self, user_id: str, identifier: Optional[str] = None):
        """Записывает запрос в статистику (для анализа)"""
        # Запись уже происходит в check_rate_limit, но можно добавить дополнительную логику
        pass
    
    async def cleanup_old_records(self):
        """Очищает старые записи (старше 24 часов)"""
        try:
            conn = await asyncpg.connect(self.db_url)
            try:
                deleted = await conn.execute("""
                    DELETE FROM rate_limits
                    WHERE created_at < NOW() - INTERVAL '24 hours'
                """)
                deleted_count = int(deleted.split()[-1]) if deleted else 0
                if deleted_count > 0:
                    logger.info(f"🧹 [RATE LIMITER] Очищено {deleted_count} старых записей")
            finally:
                await conn.close()
        except Exception as e:
            logger.debug(f"⚠️ [RATE LIMITER] Ошибка очистки: {e}")

# Singleton instance
_rate_limiter_instance: Optional[RateLimiter] = None

def get_rate_limiter(db_url: str = DB_URL) -> RateLimiter:
    """Получить singleton экземпляр rate limiter"""
    global _rate_limiter_instance
    if _rate_limiter_instance is None:
        _rate_limiter_instance = RateLimiter(db_url=db_url)
    return _rate_limiter_instance


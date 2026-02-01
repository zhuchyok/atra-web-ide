"""
Circuit Breaker для защиты от каскадных сбоев.
Предотвращает повторные вызовы неисправных сервисов.
"""

import asyncio
import logging
import os
import time
import json
from enum import Enum
from typing import Callable, Optional, Any, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Database connection для логирования событий
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

class CircuitState(Enum):
    """Состояния circuit breaker"""
    CLOSED = "closed"      # Нормальная работа
    OPEN = "open"          # Сбой, блокировка вызовов
    HALF_OPEN = "half_open"  # Тестирование восстановления

class CircuitBreaker:
    """
    Circuit Breaker для защиты от каскадных сбоев.
    
    Принцип работы:
    - CLOSED: Все вызовы проходят нормально
    - OPEN: После N ошибок подряд, все вызовы блокируются на timeout
    - HALF_OPEN: После timeout, пробуем один вызов. Если успешен -> CLOSED, иначе -> OPEN
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        expected_exception: type = Exception,
        name: str = "default"
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        self.name = name
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_success_time: Optional[datetime] = None
        self._previous_state: Optional[CircuitState] = None
        
    def _should_attempt_reset(self) -> bool:
        """Проверяет, можно ли попробовать сбросить circuit breaker"""
        if self.state != CircuitState.OPEN:
            return False
        
        if self.last_failure_time is None:
            return True
        
        time_since_failure = (datetime.now() - self.last_failure_time).total_seconds()
        return time_since_failure >= self.recovery_timeout
    
    def _on_success(self):
        """Обработка успешного вызова"""
        self.last_success_time = datetime.now()
        old_state = self.state
        
        if self.state == CircuitState.HALF_OPEN:
            # Успешный вызов в HALF_OPEN -> переходим в CLOSED
            self.state = CircuitState.CLOSED
            self.failure_count = 0
            self.success_count = 0
            logger.info(f"✅ [CIRCUIT BREAKER {self.name}] Восстановлен, переход в CLOSED")
            # Логируем событие восстановления
            asyncio.create_task(self._log_event("state_change", old_state.value, self.state.value))
        elif self.state == CircuitState.CLOSED:
            # Сбрасываем счетчик ошибок при успехе
            if self.failure_count > 0:
                self.failure_count = max(0, self.failure_count - 1)
            # Логируем успешный вызов
            asyncio.create_task(self._log_event("success", None, None))
    
    def _on_failure(self, error_message: Optional[str] = None):
        """Обработка неудачного вызова"""
        self.last_failure_time = datetime.now()
        self.failure_count += 1
        old_state = self.state
        
        if self.state == CircuitState.HALF_OPEN:
            # Ошибка в HALF_OPEN -> возвращаемся в OPEN
            self.state = CircuitState.OPEN
            logger.warning(f"⚠️ [CIRCUIT BREAKER {self.name}] Восстановление не удалось, возврат в OPEN")
            # Логируем событие с отправкой алерта
            asyncio.create_task(self._log_event("state_change", old_state.value, self.state.value, error_message=error_message, send_alert=True))
        elif self.state == CircuitState.CLOSED:
            # Проверяем, не превысили ли порог ошибок
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                logger.error(f"🚨 [CIRCUIT BREAKER {self.name}] Превышен порог ошибок ({self.failure_count}), переход в OPEN")
                # Логируем событие с отправкой алерта
                asyncio.create_task(self._log_event("state_change", old_state.value, self.state.value, error_message=error_message, send_alert=True))
            else:
                # Логируем обычную ошибку
                asyncio.create_task(self._log_event("failure", None, None, error_message=error_message))
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Выполнить функцию через circuit breaker.
        
        Args:
            func: Функция для выполнения
            *args, **kwargs: Аргументы функции
            
        Returns:
            Результат выполнения функции
            
        Raises:
            CircuitBreakerOpenError: Если circuit breaker в состоянии OPEN
            Exception: Оригинальное исключение от функции
        """
        # Проверяем состояние
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                # Пробуем восстановление
                old_state = self.state
                self.state = CircuitState.HALF_OPEN
                logger.info(f"🔄 [CIRCUIT BREAKER {self.name}] Пробуем восстановление (HALF_OPEN)")
                asyncio.create_task(self._log_event("recovery_attempt", old_state.value, self.state.value))
            else:
                # Все еще в OPEN, блокируем вызов
                time_remaining = self.recovery_timeout - (datetime.now() - self.last_failure_time).total_seconds()
                raise CircuitBreakerOpenError(
                    f"Circuit breaker {self.name} is OPEN. "
                    f"Retry in {time_remaining:.0f} seconds. "
                    f"Failures: {self.failure_count}/{self.failure_threshold}"
                )
        
        # Выполняем функцию
        try:
            if asyncio.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)
            
            self._on_success()
            return result
            
        except self.expected_exception as e:
            self._on_failure(str(e))
            raise
        except Exception as e:
            # Неожиданное исключение - тоже считаем ошибкой
            self._on_failure(str(e))
            raise
    
    async def _log_event(
        self,
        event_type: str,
        old_state: Optional[str],
        new_state: Optional[str],
        error_message: Optional[str] = None,
        send_alert: bool = False
    ):
        """Логирует событие Circuit Breaker в БД"""
        if not ASYNCPG_AVAILABLE:
            return
        
        try:
            conn = await asyncpg.connect(DB_URL)
            try:
                metadata = {
                    "failure_count": self.failure_count,
                    "success_count": self.success_count,
                    "failure_threshold": self.failure_threshold,
                    "recovery_timeout": self.recovery_timeout
                }
                
                await conn.execute("""
                    INSERT INTO circuit_breaker_events 
                    (breaker_name, event_type, old_state, new_state, failure_count, 
                     success_count, error_message, metadata, created_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW())
                """, 
                self.name, event_type, old_state, new_state, 
                self.failure_count, self.success_count, 
                error_message, json.dumps(metadata))
                
                logger.debug(f"✅ [CIRCUIT BREAKER {self.name}] Событие {event_type} сохранено в БД")
                
                # Отправляем Telegram алерт при переходе в OPEN
                if send_alert and new_state == "open":
                    await self._send_telegram_alert()
                    
            finally:
                await conn.close()
        except Exception as e:
            logger.warning(f"⚠️ [CIRCUIT BREAKER {self.name}] Не удалось сохранить событие в БД: {e}")
    
    async def _send_telegram_alert(self):
        """Отправляет Telegram алерт при критическом событии"""
        try:
            import httpx
            tg_token = os.getenv('TG_TOKEN') or os.getenv('TELEGRAM_BOT_TOKEN', '')
            chat_id = os.getenv('CHAT_ID') or os.getenv('TELEGRAM_CHAT_ID', '')
            if not tg_token or not chat_id:
                logger.debug("TG_TOKEN/CHAT_ID не заданы, пропуск Telegram алерта")
                return
            
            message = (
                f"🚨 *CIRCUIT BREAKER ALERT*\n\n"
                f"Circuit Breaker `{self.name}` перешел в состояние *OPEN*\n\n"
                f"• Ошибок: {self.failure_count}/{self.failure_threshold}\n"
                f"• Восстановление через: {self.recovery_timeout} секунд\n"
                f"• Последняя ошибка: {self.last_failure_time.isoformat() if self.last_failure_time else 'N/A'}"
            )
            
            url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
            async with httpx.AsyncClient(timeout=10.0) as client:
                await client.post(
                    url,
                    data={
                        'chat_id': chat_id,
                        'text': message,
                        'parse_mode': 'Markdown'
                    }
                )
            logger.info(f"📨 [CIRCUIT BREAKER {self.name}] Telegram алерт отправлен")
        except Exception as e:
            logger.warning(f"⚠️ [CIRCUIT BREAKER {self.name}] Не удалось отправить Telegram алерт: {e}")
    
    def get_state(self) -> Dict[str, Any]:
        """Получить текущее состояние circuit breaker"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_success_time": self.last_success_time.isoformat() if self.last_success_time else None,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout
        }

class CircuitBreakerOpenError(Exception):
    """Исключение при попытке вызова через открытый circuit breaker"""
    pass

# Глобальные circuit breakers для разных компонентов
_circuit_breakers: Dict[str, CircuitBreaker] = {}

def get_circuit_breaker(name: str, **kwargs) -> CircuitBreaker:
    """Получить или создать circuit breaker для компонента"""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name=name, **kwargs)
    return _circuit_breakers[name]


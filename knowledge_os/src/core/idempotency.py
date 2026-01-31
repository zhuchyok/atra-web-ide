"""
IdempotencyManager - Система идемпотентности для безопасных повторных операций

Принцип: Self-Validating Code - Идемпотентность
Цель: Обеспечить безопасность повторного выполнения операций без побочных эффектов
"""

import hashlib
import json
import logging
from typing import Optional, Dict, Any, Callable
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from functools import wraps

logger = logging.getLogger(__name__)


@dataclass
class IdempotencyKey:
    """Ключ идемпотентности"""
    key: str
    created_at: datetime
    result: Optional[Any] = None
    expires_at: Optional[datetime] = None
    
    def is_expired(self) -> bool:
        """Проверка истечения срока действия"""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at


class IdempotencyManager:
    """
    Менеджер для управления идемпотентностью операций
    
    Обеспечивает:
    - Генерацию уникальных ключей идемпотентности
    - Проверку дублирования операций
    - Сохранение результатов выполненных операций
    - Автоматическое истечение ключей
    """
    
    def __init__(self, ttl_hours: int = 24):
        """
        Инициализация менеджера идемпотентности
        
        Args:
            ttl_hours: Время жизни ключей в часах (по умолчанию 24 часа)
        """
        self._keys: Dict[str, IdempotencyKey] = {}
        self.ttl_hours = ttl_hours
        
    def generate_key(self, data: Dict[str, Any], prefix: str = "") -> str:
        """
        Генерация уникального ключа идемпотентности на основе данных
        
        Args:
            data: Данные для генерации ключа
            prefix: Префикс для ключа (опционально)
            
        Returns:
            Уникальный ключ идемпотентности
        """
        # Создаём строку из данных (сортировка для консистентности)
        key_data = json.dumps(data, sort_keys=True, default=str)
        
        # Добавляем префикс если указан
        if prefix:
            key_data = f"{prefix}:{key_data}"
        
        # Генерируем SHA256 хеш
        key = hashlib.sha256(key_data.encode()).hexdigest()
        
        return key
    
    def check(self, key: str) -> Optional[Any]:
        """
        Проверка, выполнялась ли операция ранее
        
        Args:
            key: Ключ идемпотентности
            
        Returns:
            Результат предыдущего выполнения или None
        """
        if key not in self._keys:
            return None
        
        idempotency_key = self._keys[key]
        
        # Проверяем истечение срока
        if idempotency_key.is_expired():
            logger.debug(f"Idempotency key expired: {key}")
            del self._keys[key]
            return None
        
        logger.info(f"✅ Idempotent operation detected: {key}")
        return idempotency_key.result
    
    def save(self, key: str, result: Any, ttl_hours: Optional[int] = None) -> None:
        """
        Сохранение результата операции
        
        Args:
            key: Ключ идемпотентности
            result: Результат операции
            ttl_hours: Время жизни в часах (если None, используется дефолтное)
        """
        ttl = ttl_hours if ttl_hours is not None else self.ttl_hours
        expires_at = datetime.now(timezone.utc) + timedelta(hours=ttl)
        
        idempotency_key = IdempotencyKey(
            key=key,
            created_at=datetime.now(timezone.utc),
            result=result,
            expires_at=expires_at
        )
        
        self._keys[key] = idempotency_key
        logger.debug(f"Saved idempotency key: {key} (expires at {expires_at})")
    
    def cleanup_expired(self) -> int:
        """
        Очистка истёкших ключей
        
        Returns:
            Количество удалённых ключей
        """
        expired_keys = [
            key for key, idempotency_key in self._keys.items()
            if idempotency_key.is_expired()
        ]
        
        for key in expired_keys:
            del self._keys[key]
        
        if expired_keys:
            logger.debug(f"Cleaned up {len(expired_keys)} expired idempotency keys")
        
        return len(expired_keys)
    
    def get_info(self) -> Dict[str, Any]:
        """Получить информацию о текущем состоянии"""
        self.cleanup_expired()
        return {
            "total_keys": len(self._keys),
            "ttl_hours": self.ttl_hours,
            "keys": [
                {
                    "key": key[:16] + "...",  # Первые 16 символов
                    "created_at": idempotency_key.created_at.isoformat(),
                    "expires_at": idempotency_key.expires_at.isoformat() if idempotency_key.expires_at else None,
                }
                for key, idempotency_key in self._keys.items()
            ]
        }


# Глобальный экземпляр для удобства использования
_global_idempotency_manager: Optional[IdempotencyManager] = None


def get_idempotency_manager() -> IdempotencyManager:
    """
    Получить глобальный экземпляр IdempotencyManager
    
    Returns:
        Глобальный экземпляр менеджера
    """
    global _global_idempotency_manager
    if _global_idempotency_manager is None:
        _global_idempotency_manager = IdempotencyManager()
    return _global_idempotency_manager


def generate_idempotency_key(data: Dict[str, Any], prefix: str = "") -> str:
    """
    Генерация ключа идемпотентности
    
    Args:
        data: Данные для генерации ключа
        prefix: Префикс для ключа
        
    Returns:
        Уникальный ключ идемпотентности
    """
    manager = get_idempotency_manager()
    return manager.generate_key(data, prefix)


def check_idempotency(key: str) -> Optional[Any]:
    """
    Проверка идемпотентности операции
    
    Args:
        key: Ключ идемпотентности
        
    Returns:
        Результат предыдущего выполнения или None
    """
    manager = get_idempotency_manager()
    return manager.check(key)


def save_idempotency_result(key: str, result: Any, ttl_hours: Optional[int] = None) -> None:
    """
    Сохранение результата идемпотентной операции
    
    Args:
        key: Ключ идемпотентности
        result: Результат операции
        ttl_hours: Время жизни в часах
    """
    manager = get_idempotency_manager()
    manager.save(key, result, ttl_hours)


def idempotent(prefix: str = "", ttl_hours: int = 24):
    """
    Декоратор для идемпотентных функций
    
    Args:
        prefix: Префикс для ключа идемпотентности
        ttl_hours: Время жизни ключа в часах
        
    Example:
        @idempotent(prefix="signal", ttl_hours=12)
        def create_signal(symbol: str, price: float):
            # Логика создания сигнала
            return signal_id
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            manager = get_idempotency_manager()
            
            # Генерируем ключ на основе аргументов функции
            key_data = {
                "func": func.__name__,
                "args": args,
                "kwargs": kwargs
            }
            key = manager.generate_key(key_data, prefix)
            
            # Проверяем идемпотентность
            existing_result = manager.check(key)
            if existing_result is not None:
                logger.info(f"Idempotent call to {func.__name__}, returning cached result")
                return existing_result
            
            # Выполняем функцию
            result = func(*args, **kwargs)
            
            # Сохраняем результат
            manager.save(key, result, ttl_hours)
            
            return result
        
        return wrapper
    return decorator


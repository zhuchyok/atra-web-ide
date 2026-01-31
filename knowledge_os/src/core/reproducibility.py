"""
ReproducibilityManager - Централизованное управление seed для воспроизводимости бэктестов

Принцип: Self-Validating Code - Воспроизводимость
Цель: Обеспечить детерминированность всех бэктестов через явное управление seed
"""

import random
import numpy as np
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class ReproducibilityConfig:
    """Конфигурация воспроизводимости"""
    seed: Optional[int] = None
    use_seed: bool = True
    log_seed: bool = True
    validate_determinism: bool = False


class ReproducibilityManager:
    """
    Менеджер для управления воспроизводимостью бэктестов
    
    Обеспечивает:
    - Явное управление seed для всех генераторов случайных чисел
    - Логирование seed для воспроизводимости
    - Валидацию детерминированности результатов
    """
    
    def __init__(self, config: Optional[ReproducibilityConfig] = None):
        """
        Инициализация менеджера воспроизводимости
        
        Args:
            config: Конфигурация воспроизводимости. Если None, используется дефолтная
        """
        self.config = config or ReproducibilityConfig()
        self._initialized = False
        self._seed_history: list[int] = []
        
    def initialize(self, seed: Optional[int] = None) -> None:
        """
        Инициализация генераторов случайных чисел с заданным seed
        
        Args:
            seed: Seed для инициализации. Если None, используется из конфигурации
        """
        if not self.config.use_seed:
            logger.debug("Reproducibility disabled, skipping seed initialization")
            return
            
        actual_seed = seed if seed is not None else self.config.seed
        
        if actual_seed is None:
            # Генерируем seed на основе текущего времени (для уникальности)
            actual_seed = int(datetime.now(timezone.utc).timestamp() * 1000000) % (2**31)
            logger.warning(f"No seed provided, using generated seed: {actual_seed}")
        
        # Устанавливаем seed для всех генераторов
        random.seed(actual_seed)
        np.random.seed(actual_seed)
        
        self._seed_history.append(actual_seed)
        self._initialized = True
        
        if self.config.log_seed:
            logger.info(f"🔢 Reproducibility initialized with seed: {actual_seed}")
            
    def get_seed(self) -> Optional[int]:
        """Получить текущий seed"""
        if not self._seed_history:
            return None
        return self._seed_history[-1]
    
    def reset(self, seed: Optional[int] = None) -> None:
        """
        Сброс генераторов с новым seed
        
        Args:
            seed: Новый seed. Если None, используется текущий
        """
        if seed is not None:
            self.config.seed = seed
        self.initialize(seed)
    
    def validate_determinism(self, func, *args, **kwargs) -> bool:
        """
        Валидация детерминированности функции
        
        Выполняет функцию дважды с одинаковым seed и проверяет,
        что результаты идентичны.
        
        Args:
            func: Функция для проверки
            *args: Аргументы функции
            **kwargs: Ключевые аргументы функции
            
        Returns:
            True если результаты детерминированы, False иначе
        """
        if not self.config.validate_determinism:
            return True
            
        if not self._initialized:
            logger.warning("Cannot validate determinism: not initialized")
            return False
        
        current_seed = self.get_seed()
        if current_seed is None:
            logger.warning("Cannot validate determinism: no seed set")
            return False
        
        # Первый запуск
        self.reset(current_seed)
        result1 = func(*args, **kwargs)
        
        # Второй запуск с тем же seed
        self.reset(current_seed)
        result2 = func(*args, **kwargs)
        
        # Сравнение результатов
        is_deterministic = result1 == result2
        
        if not is_deterministic:
            logger.error(f"❌ Non-deterministic behavior detected with seed {current_seed}")
            logger.error(f"   Result 1: {result1}")
            logger.error(f"   Result 2: {result2}")
        else:
            logger.debug(f"✅ Deterministic behavior validated with seed {current_seed}")
        
        return is_deterministic
    
    def get_info(self) -> Dict[str, Any]:
        """Получить информацию о текущем состоянии"""
        return {
            "initialized": self._initialized,
            "current_seed": self.get_seed(),
            "seed_history": self._seed_history.copy(),
            "config": {
                "use_seed": self.config.use_seed,
                "log_seed": self.config.log_seed,
                "validate_determinism": self.config.validate_determinism,
            }
        }
    
    def __enter__(self):
        """Context manager entry"""
        if not self._initialized:
            self.initialize()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit"""
        # Можно добавить cleanup если нужно
        pass


# Глобальный экземпляр для удобства использования
_global_reproducibility_manager: Optional[ReproducibilityManager] = None


def get_reproducibility_manager() -> ReproducibilityManager:
    """
    Получить глобальный экземпляр ReproducibilityManager
    
    Returns:
        Глобальный экземпляр менеджера
    """
    global _global_reproducibility_manager
    if _global_reproducibility_manager is None:
        _global_reproducibility_manager = ReproducibilityManager()
    return _global_reproducibility_manager


def set_reproducibility_seed(seed: int) -> None:
    """
    Установить seed для глобального менеджера воспроизводимости
    
    Args:
        seed: Seed для установки
    """
    manager = get_reproducibility_manager()
    manager.initialize(seed)


def ensure_reproducibility(seed: Optional[int] = None) -> ReproducibilityManager:
    """
    Убедиться, что воспроизводимость инициализирована
    
    Args:
        seed: Seed для инициализации
        
    Returns:
        Менеджер воспроизводимости
    """
    manager = get_reproducibility_manager()
    if not manager._initialized:
        manager.initialize(seed)
    return manager


import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

class BaseStrategy:
    """
    Базовый класс для всех торговых стратегий ATRA.
    Обеспечивает единый интерфейс и базовую инициализацию.
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.name = self.config.get("name", "BaseStrategy")
        logger.debug(f"Strategy {self.name} initialized")
        
    def generate_signal(self, df: Any, current_price: Any) -> Any:
        """
        Основной метод генерации сигнала. 
        Должен быть переопределен в дочерних классах.
        """
        raise NotImplementedError("generate_signal must be implemented by subclasses")


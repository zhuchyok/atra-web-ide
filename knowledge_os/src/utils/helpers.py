"""
Вспомогательные функции для торговой системы
"""

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def get_msk_now() -> datetime:
    """
    Получение текущего московского времени
    
    Returns:
        datetime: Текущее время в МСК
    """
    try:
        from shared_utils import get_msk_now as fallback_get_msk_now
        return fallback_get_msk_now()
    except ImportError:
        # Fallback к UTC+3
        from src.shared.utils.datetime_utils import get_utc_now
        return get_utc_now() + timedelta(hours=3)


def format_price(price: float, decimals: int = 4) -> str:
    """
    Форматирование цены для отображения
    
    Args:
        price: Цена
        decimals: Количество знаков после запятой
        
    Returns:
        str: Отформатированная цена
    """
    return f"{price:.{decimals}f}"


def validate_symbol(symbol: str) -> bool:
    """
    Валидация торгового символа
    
    Args:
        symbol: Торговый символ
        
    Returns:
        bool: True если символ валиден
    """
    if not symbol or not isinstance(symbol, str):
        return False
    
    # Базовая валидация
    if len(symbol) < 6 or len(symbol) > 12:
        return False
    
    if not symbol.endswith('USDT'):
        return False
    
    return True

"""
Провайдеры данных для торговой системы
"""

import logging
import pandas as pd
from typing import List, Optional

logger = logging.getLogger(__name__)


async def get_ohlc_data(symbol: str, timeframe: str = "1h", limit: int = 300) -> Optional[pd.DataFrame]:
    """
    Получение OHLC данных для символа
    
    Args:
        symbol: Торговый символ
        timeframe: Таймфрейм
        limit: Количество свечей
        
    Returns:
        pd.DataFrame или None при ошибке
    """
    try:
        # Fallback к существующему API
        from exchange_api import get_ohlc_binance_sync_async
        data = await get_ohlc_binance_sync_async(symbol, timeframe, limit)
        if data:
            return pd.DataFrame(data)
        return None
    except Exception as e:
        logger.error("Ошибка получения OHLC данных для %s: %s", symbol, e)
        return None


async def get_top_symbols() -> List[str]:
    """
    Получение списка топовых символов для анализа
    
    Returns:
        List[str]: Список торговых символов
    """
    try:
        # Пробуем импортировать async версию
        try:
            from src.strategies.pair_filtering import get_filtered_top_usdt_pairs_fast
            # Это async функция, нужен await
            return await get_filtered_top_usdt_pairs_fast()
        except ImportError:
            # Fallback к синхронной версии
            from src.execution.exchange_api import get_filtered_top_usdt_pairs_fast
            # Это синхронная функция, возвращает список
            return get_filtered_top_usdt_pairs_fast()
    except Exception as e:
        logger.error("Ошибка получения списка символов: %s", e)
        return ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

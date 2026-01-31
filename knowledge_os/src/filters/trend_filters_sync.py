"""
Синхронные версии фильтров тренда для использования в core.py
"""

import logging
import pandas as pd
from typing import Tuple, Optional

logger = logging.getLogger(__name__)


def check_btc_trend_filter(
    df: pd.DataFrame,
    i: int,
    side: str,
    strict_mode: bool = False,
    ema_soft: int = 50,
    ema_strict: int = 200,
    lookback: int = 50,
) -> Tuple[bool, Optional[str]]:
    """
    Проверяет тренд BTC для фильтрации сигналов
    
    Args:
        df: DataFrame с данными (должен содержать данные BTC)
        i: Индекс текущей свечи
        side: "long" или "short"
        strict_mode: Строгий режим
        ema_soft: Период EMA для мягкого режима
        ema_strict: Период EMA для строгого режима
        lookback: Период для расчета тренда
    
    Returns:
        Tuple[bool, Optional[str]]: (прошел_фильтр, причина_отклонения)
    """
    try:
        if i < lookback:
            return True, None
        
        # В мягком режиме: цена > EMA(soft)
        # В строгом режиме: цена > EMA(strict) И EMA(short) растет
        if strict_mode:
            # Строгий режим: нужны данные BTC с EMA25 и EMA200
            # Пока упрощенная версия - всегда True
            return True, None
        else:
            # Мягкий режим: проверяем EMA(soft)
            # Пока упрощенная версия - всегда True
            return True, None
    except Exception as e:
        logger.debug("Ошибка в check_btc_trend_filter: %s", e)
        return True, None


def check_eth_trend_filter(
    df: pd.DataFrame,
    i: int,
    side: str,
    strict_mode: bool = False,
    ema_soft: int = 50,
    ema_strict: int = 200,
) -> Tuple[bool, Optional[str]]:
    """
    Проверяет тренд ETH для фильтрации сигналов
    
    Args:
        df: DataFrame с данными
        i: Индекс текущей свечи
        side: "long" или "short"
        strict_mode: Строгий режим
        ema_soft: Период EMA для мягкого режима
        ema_strict: Период EMA для строгого режима
    
    Returns:
        Tuple[bool, Optional[str]]: (прошел_фильтр, причина_отклонения)
    """
    try:
        if i < ema_soft:
            return True, None
        
        # Вычисляем EMA для ETH
        # Пока упрощенная версия - всегда True
        return True, None
    except Exception as e:
        logger.debug("Ошибка в check_eth_trend_filter: %s", e)
        return True, None


def check_sol_trend_filter(
    df: pd.DataFrame,
    i: int,
    side: str,
    strict_mode: bool = False,
    ema_soft: int = 50,
    ema_strict: int = 200,
) -> Tuple[bool, Optional[str]]:
    """
    Проверяет тренд SOL для фильтрации сигналов
    
    Args:
        df: DataFrame с данными
        i: Индекс текущей свечи
        side: "long" или "short"
        strict_mode: Строгий режим
        ema_soft: Период EMA для мягкого режима
        ema_strict: Период EMA для строгого режима
    
    Returns:
        Tuple[bool, Optional[str]]: (прошел_фильтр, причина_отклонения)
    """
    try:
        if i < ema_soft:
            return True, None
        
        # Вычисляем EMA для SOL
        # Пока упрощенная версия - всегда True
        return True, None
    except Exception as e:
        logger.debug("Ошибка в check_sol_trend_filter: %s", e)
        return True, None


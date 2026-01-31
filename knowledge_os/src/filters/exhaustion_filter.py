"""
Exhaustion Filter - фильтр для раннего выхода при исчерпании движения

Использует:
- Volume Exhaustion - исчерпание объема
- Price Exhaustion Patterns - паттерны разворота
- Liquidity Exhaustion - исчерпание ликвидности

Рекомендует ранний выход из позиции при обнаружении исчерпания.
"""

import logging
from typing import Tuple, Optional, Dict, Any
import pandas as pd

logger = logging.getLogger(__name__)

# Импорты с fallback
try:
    from src.analysis.exhaustion import (
        VolumeExhaustion,
        PriceExhaustionPatterns,
        LiquidityExhaustion
    )
    EXHAUSTION_AVAILABLE = True
except ImportError:
    EXHAUSTION_AVAILABLE = False
    logger.warning("Exhaustion модули недоступны")


def check_exhaustion_early_exit(
    df: pd.DataFrame,
    i: int,
    side: str,
    entry_price: float,
    current_price: float,
    strict_mode: bool = True,
) -> Tuple[bool, Optional[str], Dict[str, Any]]:
    """
    Проверяет, нужно ли выходить из позиции раньше из-за исчерпания
    
    Args:
        df: DataFrame с данными OHLCV
        i: Индекс текущей свечи
        side: "long" или "short"
        entry_price: Цена входа в позицию
        current_price: Текущая цена
        strict_mode: True для строгого режима (более чувствительный)
    
    Returns:
        Tuple[should_exit, reason, details]
        - should_exit: True если нужно выходить
        - reason: Причина выхода
        - details: Детали исчерпания
    """
    try:
        if not EXHAUSTION_AVAILABLE:
            return False, None, {}
        
        if i >= len(df):
            return False, None, {}
        
        # Инициализируем индикаторы
        volume_exhaustion = VolumeExhaustion()
        price_patterns = PriceExhaustionPatterns()
        liquidity_exhaustion = LiquidityExhaustion()
        
        # Проверяем все типы исчерпания
        volume_exhausted = volume_exhaustion.is_exhausted(df, i, side=side, threshold=0.7 if strict_mode else 0.5)
        price_exhausted = price_patterns.is_exhausted(df, i, side=side, threshold=0.5 if strict_mode else 0.3)
        liquidity_exhausted = liquidity_exhaustion.is_exhausted(df, i, side=side, threshold=0.6 if strict_mode else 0.4)
        
        # Получаем детали
        volume_level = volume_exhaustion.get_exhaustion_level(df, i, side=side)
        price_score = price_patterns.get_exhaustion_score(df, i)
        liquidity_level = liquidity_exhaustion.get_exhaustion_level(df, i, side=side)
        
        details = {
            'volume_exhausted': volume_exhausted,
            'price_exhausted': price_exhausted,
            'liquidity_exhausted': liquidity_exhausted,
            'volume_level': volume_level,
            'price_score': price_score,
            'liquidity_level': liquidity_level,
        }
        
        # Рассчитываем прибыль/убыток
        if side.lower() == 'long':
            pnl_pct = (current_price - entry_price) / entry_price * 100
        else:  # short
            pnl_pct = (entry_price - current_price) / entry_price * 100
        
        # В строгом режиме требуем хотя бы 2 из 3 подтверждений
        # В мягком режиме достаточно 1 из 3
        confirmations = sum([volume_exhausted, price_exhausted, liquidity_exhausted])
        required_confirmations = 2 if strict_mode else 1
        
        # Проверяем, есть ли исчерпание
        if confirmations >= required_confirmations:
            # Проверяем, что позиция в прибыли (не выходим из убыточной позиции по exhaustion)
            if pnl_pct > 0:
                reasons = []
                if volume_exhausted:
                    reasons.append(f"Volume Exhaustion (level={volume_level:.2f})")
                if price_exhausted:
                    reasons.append(f"Price Patterns (score={price_score:.2f})")
                if liquidity_exhausted:
                    reasons.append(f"Liquidity Exhaustion (level={liquidity_level:.2f})")
                
                reason = f"Исчерпание движения: {', '.join(reasons)}. PnL: {pnl_pct:.2f}%"
                return True, reason, details
            else:
                # Позиция в убытке - не выходим по exhaustion
                return False, f"Позиция в убытке ({pnl_pct:.2f}%), не выходим по exhaustion", details
        
        return False, None, details
        
    except Exception as e:
        logger.error(f"Ошибка в check_exhaustion_early_exit: {e}")
        return False, None, {}


def get_exhaustion_recommendation(
    df: pd.DataFrame,
    i: int,
    side: str,
    entry_price: float,
    current_price: float,
) -> Dict[str, Any]:
    """
    Получает рекомендацию по выходу на основе исчерпания
    
    Args:
        df: DataFrame с данными
        i: Индекс текущей свечи
        side: "long" или "short"
        entry_price: Цена входа
        current_price: Текущая цена
    
    Returns:
        Dict с рекомендацией:
        {
            'should_exit': bool,
            'exit_type': 'full' | 'partial' | None,
            'exit_pct': float (0-100),
            'reason': str,
            'exhaustion_level': float (0-1)
        }
    """
    try:
        if not EXHAUSTION_AVAILABLE:
            return {
                'should_exit': False,
                'exit_type': None,
                'exit_pct': 0.0,
                'reason': 'Exhaustion модули недоступны',
                'exhaustion_level': 0.0
            }
        
        # Проверяем исчерпание
        should_exit, reason, details = check_exhaustion_early_exit(
            df, i, side, entry_price, current_price, strict_mode=True
        )
        
        if not should_exit:
            return {
                'should_exit': False,
                'exit_type': None,
                'exit_pct': 0.0,
                'reason': reason or 'Нет исчерпания',
                'exhaustion_level': 0.0
            }
        
        # Рассчитываем общий уровень исчерпания
        exhaustion_level = (
            (details.get('volume_level', 0) or 0) * 0.4 +
            (details.get('price_score', 0) or 0) * 0.4 +
            (details.get('liquidity_level', 0) or 0) * 0.2
        )
        
        # Определяем тип выхода
        if exhaustion_level >= 0.8:
            exit_type = 'full'
            exit_pct = 100.0
        elif exhaustion_level >= 0.5:
            exit_type = 'partial'
            exit_pct = 50.0  # Закрываем 50% позиции
        else:
            exit_type = 'partial'
            exit_pct = 25.0  # Закрываем 25% позиции
        
        return {
            'should_exit': True,
            'exit_type': exit_type,
            'exit_pct': exit_pct,
            'reason': reason,
            'exhaustion_level': exhaustion_level,
            'details': details
        }
        
    except Exception as e:
        logger.error(f"Ошибка получения рекомендации по exhaustion: {e}")
        return {
            'should_exit': False,
            'exit_type': None,
            'exit_pct': 0.0,
            'reason': f'Ошибка: {e}',
            'exhaustion_level': 0.0
        }


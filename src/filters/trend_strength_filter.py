"""
Trend Strength Filter - фильтр на основе силы тренда

Использует:
- ADX (Average Directional Index) - сила тренда
- TSI (True Strength Index) - направление и сила тренда

Фильтрует сигналы, оставляя только те, которые соответствуют сильному тренду.
"""

import logging
from typing import Tuple, Optional
import pandas as pd

logger = logging.getLogger(__name__)

# Импорты с fallback
try:
    from src.analysis.trend import ADXAnalyzer, TrueStrengthIndex
    TREND_AVAILABLE = True
except ImportError:
    TREND_AVAILABLE = False
    logger.warning("Trend модули недоступны")


def check_trend_strength_filter(
    df: pd.DataFrame,
    i: int,
    side: str,
    strict_mode: bool = True,
) -> Tuple[bool, Optional[str]]:
    """
    Проверяет, соответствует ли сигнал фильтрам силы тренда
    
    Логика:
    - Требуется сильный тренд (ADX > 25)
    - TSI должен подтверждать направление
    - В строгом режиме: требуются оба подтверждения
    - В мягком режиме: достаточно ADX
    
    Args:
        df: DataFrame с данными OHLCV
        i: Индекс текущей свечи
        side: "long" или "short"
        strict_mode: True для строгого режима
    
    Returns:
        Tuple[passed, reason]
    """
    try:
        if not TREND_AVAILABLE:
            return True, None  # Если модуль недоступен, пропускаем фильтр
        
        if i >= len(df):
            return False, "Индекс выходит за границы DataFrame"
        
        # Инициализируем индикаторы
        adx = ADXAnalyzer(period=14)
        tsi = TrueStrengthIndex()
        
        # Получаем значения
        adx_value = adx.get_value(df, i)
        tsi_value = tsi.get_value(df, i)
        tsi_signal = tsi.get_signal(df, i)
        adx_direction = adx.get_trend_direction(df, i)
        
        # Используем параметры из config.py
        try:
            from config import TREND_STRENGTH_FILTER_CONFIG
            adx_threshold = TREND_STRENGTH_FILTER_CONFIG.get("adx_threshold", 15)
            require_direction = TREND_STRENGTH_FILTER_CONFIG.get("require_direction", False)
        except ImportError:
            adx_threshold = 15
            require_direction = False
        
        # Проверка силы тренда (ADX)
        adx_ok = False
        if adx_value is not None:
            if strict_mode:
                adx_ok = adx_value > 25.0  # Строгий порог сильного тренда
            else:
                adx_ok = adx_value > adx_threshold  # Используем параметр из config.py
        
        if not adx_ok:
            return False, f"Слабый тренд (ADX={adx_value:.2f}, требуется > {'25' if strict_mode else adx_threshold})"
        
        if side.lower() == "long":
            # LONG: нужен восходящий тренд
            
            # Проверка направления ADX (только если require_direction=True)
            if require_direction or strict_mode:
                adx_direction_ok = adx_direction == 'up' if adx_direction else False
            else:
                adx_direction_ok = True  # Не требуется направление
            
            # Проверка TSI
            tsi_ok = False
            if tsi_signal == 'long':
                tsi_ok = True
            elif tsi_value is not None:
                tsi_ok = tsi_value > 0  # Положительный TSI = восходящий тренд
            
            # Комбинированная проверка
            if require_direction or strict_mode:
                # Требуем подтверждение направления
                if adx_direction_ok and tsi_ok:
                    return True, None
                reasons = []
                if not adx_direction_ok:
                    reasons.append(f"ADX направление не восходящее (direction={adx_direction})")
                if not tsi_ok:
                    reasons.append(f"TSI не подтверждает восходящий тренд (value={tsi_value:.2f})")
                return False, f"LONG: недостаточно подтверждений тренда. {', '.join(reasons)}"
            else:
                # В мягком режиме достаточно ADX направления или TSI
                if adx_direction_ok or tsi_ok:
                    return True, None
                return False, f"LONG: нет подтверждения восходящего тренда (ADX direction={adx_direction}, TSI={tsi_value:.2f})"
        
        elif side.lower() == "short":
            # SHORT: нужен нисходящий тренд
            
            # Проверка направления ADX (только если require_direction=True)
            if require_direction or strict_mode:
                adx_direction_ok = adx_direction == 'down' if adx_direction else False
            else:
                adx_direction_ok = True  # Не требуется направление
            
            # Проверка TSI
            tsi_ok = False
            if tsi_signal == 'short':
                tsi_ok = True
            elif tsi_value is not None:
                tsi_ok = tsi_value < 0  # Отрицательный TSI = нисходящий тренд
            
            # Комбинированная проверка
            if require_direction or strict_mode:
                # Требуем подтверждение направления
                if adx_direction_ok and tsi_ok:
                    return True, None
                reasons = []
                if not adx_direction_ok:
                    reasons.append(f"ADX направление не нисходящее (direction={adx_direction})")
                if not tsi_ok:
                    reasons.append(f"TSI не подтверждает нисходящий тренд (value={tsi_value:.2f})")
                return False, f"SHORT: недостаточно подтверждений тренда. {', '.join(reasons)}"
            else:
                # В мягком режиме достаточно ADX направления или TSI (или не требуется направление)
                if adx_direction_ok or tsi_ok:
                    return True, None
                return False, f"SHORT: нет подтверждения нисходящего тренда (ADX direction={adx_direction}, TSI={tsi_value:.2f})"
        
        return True, None
        
    except Exception as e:
        logger.error(f"Ошибка в check_trend_strength_filter: {e}")
        return True, None  # В случае ошибки пропускаем фильтр


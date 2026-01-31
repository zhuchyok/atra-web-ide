"""
Momentum Filter - фильтр на основе продвинутых индикаторов момента

Использует:
- Money Flow Index (MFI) - комбинация цены и объема
- Stochastic RSI (Stoch RSI) - более чувствительная версия RSI

Фильтрует сигналы, оставляя только те, которые подтверждены momentum индикаторами.
"""

import logging
from typing import Tuple, Optional
import pandas as pd

logger = logging.getLogger(__name__)

# Импорты с fallback
try:
    from src.analysis.momentum import MoneyFlowIndex, StochasticRSI
    MOMENTUM_AVAILABLE = True
except ImportError:
    MOMENTUM_AVAILABLE = False
    logger.warning("Momentum модули недоступны")


def check_momentum_filter(
    df: pd.DataFrame,
    i: int,
    side: str,
    strict_mode: bool = True,
) -> Tuple[bool, Optional[str]]:
    """
    Проверяет, соответствует ли сигнал momentum фильтрам
    
    Логика:
    - LONG: нужны подтверждения перепроданности (MFI < 30, Stoch RSI < 20)
    - SHORT: нужны подтверждения перекупленности (MFI > 70, Stoch RSI > 80)
    - В строгом режиме: требуются оба подтверждения
    - В мягком режиме: достаточно одного
    
    Args:
        df: DataFrame с данными OHLCV
        i: Индекс текущей свечи
        side: "long" или "short"
        strict_mode: True для строгого режима
    
    Returns:
        Tuple[passed, reason]
    """
    try:
        if not MOMENTUM_AVAILABLE:
            return True, None  # Если модуль недоступен, пропускаем фильтр
        
        if i >= len(df):
            return False, "Индекс выходит за границы DataFrame"
        
        # Инициализируем индикаторы
        mfi = MoneyFlowIndex(period=14)
        stoch_rsi = StochasticRSI()
        
        # Получаем значения
        mfi_value = mfi.get_value(df, i)
        stoch_rsi_value = stoch_rsi.get_value(df, i)
        
        # Используем параметры из config.py
        try:
            from config import MOMENTUM_FILTER_CONFIG
            mfi_long = MOMENTUM_FILTER_CONFIG.get("mfi_long", 50)
            mfi_short = MOMENTUM_FILTER_CONFIG.get("mfi_short", 50)
            stoch_long = MOMENTUM_FILTER_CONFIG.get("stoch_long", 50)
            stoch_short = MOMENTUM_FILTER_CONFIG.get("stoch_short", 50)
        except ImportError:
            mfi_long = 50
            mfi_short = 50
            stoch_long = 50
            stoch_short = 50
        
        if side.lower() == "long":
            # LONG: нужны подтверждения перепроданности
            
            # Проверка MFI
            mfi_ok = False
            if mfi_value is not None:
                if strict_mode:
                    mfi_ok = mfi_value < 30.0  # Строгий порог перепроданности
                else:
                    mfi_ok = mfi_value < mfi_long  # Используем параметр из config.py
            
            # Проверка Stoch RSI
            stoch_rsi_ok = False
            if stoch_rsi_value is not None:
                if strict_mode:
                    stoch_rsi_ok = stoch_rsi_value < 20.0  # Строгий порог перепроданности
                else:
                    stoch_rsi_ok = stoch_rsi_value < stoch_long  # Используем параметр из config.py
            
            # Комбинированная проверка
            if strict_mode:
                # В строгом режиме требуем оба подтверждения
                if mfi_ok and stoch_rsi_ok:
                    return True, None
                reasons = []
                if not mfi_ok:
                    reasons.append(f"MFI не в перепроданности (value={mfi_value:.2f})")
                if not stoch_rsi_ok:
                    reasons.append(f"Stoch RSI не в перепроданности (value={stoch_rsi_value:.2f})")
                return False, f"LONG: недостаточно подтверждений momentum. {', '.join(reasons)}"
            else:
                # В мягком режиме достаточно одного подтверждения
                if mfi_ok or stoch_rsi_ok:
                    return True, None
                return False, f"LONG: нет подтверждений перепроданности (MFI={mfi_value:.2f}, Stoch RSI={stoch_rsi_value:.2f})"
        
        elif side.lower() == "short":
            # SHORT: нужны подтверждения перекупленности
            
            # Проверка MFI
            mfi_ok = False
            if mfi_value is not None:
                if strict_mode:
                    mfi_ok = mfi_value > 70.0  # Строгий порог перекупленности
                else:
                    mfi_ok = mfi_value > mfi_short  # Используем параметр из config.py
            
            # Проверка Stoch RSI
            stoch_rsi_ok = False
            if stoch_rsi_value is not None:
                if strict_mode:
                    stoch_rsi_ok = stoch_rsi_value > 80.0  # Строгий порог перекупленности
                else:
                    stoch_rsi_ok = stoch_rsi_value > stoch_short  # Используем параметр из config.py
            
            # Комбинированная проверка
            if strict_mode:
                # В строгом режиме требуем оба подтверждения
                if mfi_ok and stoch_rsi_ok:
                    return True, None
                reasons = []
                if not mfi_ok:
                    reasons.append(f"MFI не в перекупленности (value={mfi_value:.2f})")
                if not stoch_rsi_ok:
                    reasons.append(f"Stoch RSI не в перекупленности (value={stoch_rsi_value:.2f})")
                return False, f"SHORT: недостаточно подтверждений momentum. {', '.join(reasons)}"
            else:
                # В мягком режиме достаточно одного подтверждения
                if mfi_ok or stoch_rsi_ok:
                    return True, None
                return False, f"SHORT: нет подтверждений перекупленности (MFI={mfi_value:.2f}, Stoch RSI={stoch_rsi_value:.2f})"
        
        return True, None
        
    except Exception as e:
        logger.error(f"Ошибка в check_momentum_filter: {e}")
        return True, None  # В случае ошибки пропускаем фильтр


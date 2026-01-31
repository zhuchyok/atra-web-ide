"""
Microstructure Filter - фильтр на основе микроструктуры рынка

Использует:
- Liquidity Zones - зоны скопления стоп-лоссов
- Absorption Levels - уровни поглощения институционалов

Фильтрует сигналы, оставляя только те, которые находятся вблизи значимых уровней.
"""

import logging
from typing import Tuple, Optional, Dict, Any
import pandas as pd

logger = logging.getLogger(__name__)

# Импорты с fallback
try:
    from src.analysis.volume_profile import VolumeProfileAnalyzer
    from src.analysis.microstructure import AbsorptionLevels
    MICROSTRUCTURE_AVAILABLE = True
except ImportError:
    MICROSTRUCTURE_AVAILABLE = False
    logger.warning("Microstructure модули недоступны")


def check_microstructure_filter(
    df: pd.DataFrame,
    i: int,
    side: str,
    strict_mode: bool = True,
) -> Tuple[bool, Optional[str]]:
    """
    Проверяет, соответствует ли сигнал фильтрам микроструктуры
    
    Логика:
    - LONG: цена должна быть вблизи зоны поддержки или уровня поглощения (support)
    - SHORT: цена должна быть вблизи зоны сопротивления или уровня поглощения (resistance)
    - В строгом режиме: требуются более сильные уровни
    
    Args:
        df: DataFrame с данными OHLCV
        i: Индекс текущей свечи
        side: "long" или "short"
        strict_mode: True для строгого режима
    
    Returns:
        Tuple[passed, reason]
    """
    try:
        if not MICROSTRUCTURE_AVAILABLE:
            return True, None  # Если модуль недоступен, пропускаем фильтр
        
        if i >= len(df):
            return False, "Индекс выходит за границы DataFrame"
        
        current_price = df["close"].iloc[i]
        
        # Инициализируем анализаторы
        vp_analyzer = VolumeProfileAnalyzer()
        absorption = AbsorptionLevels()
        
        # Получаем зоны ликвидности
        # Используем параметры из config.py
        try:
            from config import MICROSTRUCTURE_FILTER_CONFIG
            lookback = MICROSTRUCTURE_FILTER_CONFIG.get("lookback", 30)
            tolerance_pct = MICROSTRUCTURE_FILTER_CONFIG.get("tolerance_pct", 2.5)
            min_strength = MICROSTRUCTURE_FILTER_CONFIG.get("min_strength", 0.1)
        except ImportError:
            lookback = 30
            tolerance_pct = 2.5
            min_strength = 0.1
        
        liquidity_zones = vp_analyzer.get_liquidity_zones(
            df.iloc[:i+1],
            lookback_periods=100 if strict_mode else lookback
        )
        
        # Получаем уровни поглощения
        absorption_levels = absorption.detect_absorption_levels(df, i)
        
        if side.lower() == "long":
            # LONG: ищем поддержку или уровни поглощения поддержки
            
            # Проверяем зоны ликвидности (поддержка)
            support_zones = [z for z in liquidity_zones if z['type'] == 'support']
            near_support = False
            support_reason = None
            
            for zone in support_zones:
                distance_pct = abs(current_price - zone['price']) / current_price * 100
                tolerance = 1.0 if strict_mode else tolerance_pct
                
                if distance_pct <= tolerance:
                    # Проверяем силу зоны
                    zone_min_strength = 0.5 if strict_mode else min_strength
                    if zone['strength'] >= zone_min_strength:
                        near_support = True
                        support_reason = f"Liquidity Zone support (price={zone['price']:.2f}, strength={zone['strength']:.2f})"
                        break
            
            # Проверяем уровни поглощения (поддержка)
            support_absorption = [l for l in absorption_levels if l['type'] == 'support']
            near_absorption = False
            absorption_reason = None
            
            for level in support_absorption:
                distance_pct = abs(current_price - level['price']) / current_price * 100
                tolerance = 1.0 if strict_mode else tolerance_pct
                
                if distance_pct <= tolerance:
                    level_min_strength = 0.5 if strict_mode else min_strength
                    if level['strength'] >= level_min_strength:
                        near_absorption = True
                        absorption_reason = f"Absorption Level support (price={level['price']:.2f}, strength={level['strength']:.2f})"
                        break
            
            # В строгом режиме требуем хотя бы один уровень
            # В мягком режиме достаточно одного из двух
            if strict_mode:
                if near_support or near_absorption:
                    reason = support_reason or absorption_reason
                    return True, reason
                return False, f"LONG: цена не вблизи поддержки (price={current_price:.2f}, нет сильных уровней)"
            else:
                if near_support or near_absorption:
                    reason = support_reason or absorption_reason
                    return True, reason
                return False, f"LONG: цена не вблизи поддержки (price={current_price:.2f})"
        
        elif side.lower() == "short":
            # SHORT: ищем сопротивление или уровни поглощения сопротивления
            
            # Проверяем зоны ликвидности (сопротивление)
            resistance_zones = [z for z in liquidity_zones if z['type'] == 'resistance']
            near_resistance = False
            resistance_reason = None
            
            for zone in resistance_zones:
                distance_pct = abs(current_price - zone['price']) / current_price * 100
                tolerance = 1.0 if strict_mode else tolerance_pct
                
                if distance_pct <= tolerance:
                    zone_min_strength = 0.5 if strict_mode else min_strength
                    if zone['strength'] >= zone_min_strength:
                        near_resistance = True
                        resistance_reason = f"Liquidity Zone resistance (price={zone['price']:.2f}, strength={zone['strength']:.2f})"
                        break
            
            # Проверяем уровни поглощения (сопротивление)
            resistance_absorption = [l for l in absorption_levels if l['type'] == 'resistance']
            near_absorption = False
            absorption_reason = None
            
            for level in resistance_absorption:
                distance_pct = abs(current_price - level['price']) / current_price * 100
                tolerance = 1.0 if strict_mode else tolerance_pct
                
                if distance_pct <= tolerance:
                    level_min_strength = 0.5 if strict_mode else min_strength
                    if level['strength'] >= level_min_strength:
                        near_absorption = True
                        absorption_reason = f"Absorption Level resistance (price={level['price']:.2f}, strength={level['strength']:.2f})"
                        break
            
            # В строгом режиме требуем хотя бы один уровень
            # В мягком режиме достаточно одного из двух
            if strict_mode:
                if near_resistance or near_absorption:
                    reason = resistance_reason or absorption_reason
                    return True, reason
                return False, f"SHORT: цена не вблизи сопротивления (price={current_price:.2f}, нет сильных уровней)"
            else:
                if near_resistance or near_absorption:
                    reason = resistance_reason or absorption_reason
                    return True, reason
                return False, f"SHORT: цена не вблизи сопротивления (price={current_price:.2f})"
        
        return True, None
        
    except Exception as e:
        logger.error(f"Ошибка в check_microstructure_filter: {e}")
        return True, None  # В случае ошибки пропускаем фильтр


"""
Zone-based TP/SL Calculator - динамические TP/SL на основе зон Фибоначчи и Interest Zones
"""

import logging
from typing import Dict, Any, Optional, Tuple, List

import pandas as pd

from src.technical.fibonacci import FibonacciCalculator, FibonacciLevel
from src.filters.interest_zone import InterestZone

logger = logging.getLogger(__name__)


class ZoneBasedTPSLCalculator:
    """Калькулятор динамических TP/SL на основе зон"""
    
    def __init__(self):
        self.fib_calculator = FibonacciCalculator()
    
    def calculate_tp_sl_from_fibonacci(
        self,
        entry_price: float,
        direction: str,
        df: pd.DataFrame,
        base_tp1_pct: float,
        base_tp2_pct: float,
        base_sl_pct: float,
        lookback_periods: int = 100,
    ) -> Tuple[float, float, float, Dict[str, Any]]:
        """
        Рассчитывает TP/SL на основе уровней Фибоначчи
        
        Args:
            entry_price: Цена входа
            direction: "LONG" | "SHORT"
            df: DataFrame с OHLCV данными
            base_tp1_pct: Базовый TP1 (%)
            base_tp2_pct: Базовый TP2 (%)
            base_sl_pct: Базовый SL (%)
            lookback_periods: Период для расчета Фибоначчи
        
        Returns:
            Tuple[tp1_pct, tp2_pct, sl_pct, details]
        """
        try:
            # Рассчитываем уровни Фибоначчи
            fib_levels = self.fib_calculator.calculate_fibonacci_levels(
                df,
                lookback_periods=lookback_periods
            )
            
            if not fib_levels:
                # Нет уровней - используем базовые значения
                return base_tp1_pct, base_tp2_pct, base_sl_pct, {"method": "base", "reason": "no_fib_levels"}
            
            # Находим ближайшие уровни выше и ниже цены входа
            levels_above = [l for l in fib_levels if l.price > entry_price]
            levels_below = [l for l in fib_levels if l.price < entry_price]
            
            if direction == "LONG":
                # LONG: TP на уровнях сопротивления выше, SL на уровнях поддержки ниже
                # TP1: ближайший уровень сопротивления выше
                if levels_above:
                    nearest_resistance = min(levels_above, key=lambda x: x.price)
                    tp1_price = nearest_resistance.price
                    tp1_pct = ((tp1_price - entry_price) / entry_price) * 100
                    tp1_pct = max(tp1_pct, base_tp1_pct * 0.8)  # Не меньше 80% от базового
                else:
                    tp1_pct = base_tp1_pct
                    tp1_price = entry_price * (1 + tp1_pct / 100)
                
                # TP2: следующий уровень сопротивления выше TP1
                if levels_above:
                    higher_resistances = [l for l in levels_above if l.price > tp1_price]
                    if higher_resistances:
                        tp2_level = min(higher_resistances, key=lambda x: x.price)
                        tp2_price = tp2_level.price
                        tp2_pct = ((tp2_price - entry_price) / entry_price) * 100
                        tp2_pct = max(tp2_pct, base_tp2_pct * 0.8)
                    else:
                        tp2_pct = base_tp2_pct
                else:
                    tp2_pct = base_tp2_pct
                
                # SL: ближайший уровень поддержки ниже
                if levels_below:
                    nearest_support = max(levels_below, key=lambda x: x.price)
                    sl_price = nearest_support.price
                    sl_pct = ((entry_price - sl_price) / entry_price) * 100
                    sl_pct = min(sl_pct, base_sl_pct * 1.2)  # Не больше 120% от базового
                else:
                    sl_pct = base_sl_pct
                
                return tp1_pct, tp2_pct, sl_pct, {
                    "method": "fibonacci",
                    "tp1_level": nearest_resistance.level if levels_above else None,
                    "tp2_level": tp2_level.level if levels_above and higher_resistances else None,
                    "sl_level": nearest_support.level if levels_below else None,
                }
            
            else:  # SHORT
                # SHORT: TP на уровнях поддержки ниже, SL на уровнях сопротивления выше
                # TP1: ближайший уровень поддержки ниже
                if levels_below:
                    nearest_support = max(levels_below, key=lambda x: x.price)
                    tp1_price = nearest_support.price
                    tp1_pct = ((entry_price - tp1_price) / entry_price) * 100
                    tp1_pct = max(tp1_pct, base_tp1_pct * 0.8)
                else:
                    tp1_pct = base_tp1_pct
                    tp1_price = entry_price * (1 - tp1_pct / 100)
                
                # TP2: следующий уровень поддержки ниже TP1
                if levels_below:
                    lower_supports = [l for l in levels_below if l.price < tp1_price]
                    if lower_supports:
                        tp2_level = max(lower_supports, key=lambda x: x.price)
                        tp2_price = tp2_level.price
                        tp2_pct = ((entry_price - tp2_price) / entry_price) * 100
                        tp2_pct = max(tp2_pct, base_tp2_pct * 0.8)
                    else:
                        tp2_pct = base_tp2_pct
                else:
                    tp2_pct = base_tp2_pct
                
                # SL: ближайший уровень сопротивления выше
                if levels_above:
                    nearest_resistance = min(levels_above, key=lambda x: x.price)
                    sl_price = nearest_resistance.price
                    sl_pct = ((sl_price - entry_price) / entry_price) * 100
                    sl_pct = min(sl_pct, base_sl_pct * 1.2)
                else:
                    sl_pct = base_sl_pct
                
                return tp1_pct, tp2_pct, sl_pct, {
                    "method": "fibonacci",
                    "tp1_level": nearest_support.level if levels_below else None,
                    "tp2_level": tp2_level.level if levels_below and lower_supports else None,
                    "sl_level": nearest_resistance.level if levels_above else None,
                }
                
        except Exception as e:
            logger.error("❌ Ошибка расчета TP/SL от Фибоначчи: %s", e)
            return base_tp1_pct, base_tp2_pct, base_sl_pct, {"method": "base", "error": str(e)}
    
    def calculate_tp_sl_from_interest_zones(
        self,
        entry_price: float,
        direction: str,
        zones: List[InterestZone],
        base_tp1_pct: float,
        base_tp2_pct: float,
        base_sl_pct: float,
    ) -> Tuple[float, float, float, Dict[str, Any]]:
        """
        Рассчитывает TP/SL на основе зон интереса
        
        Args:
            entry_price: Цена входа
            direction: "LONG" | "SHORT"
            zones: Список зон интереса
            base_tp1_pct: Базовый TP1 (%)
            base_tp2_pct: Базовый TP2 (%)
            base_sl_pct: Базовый SL (%)
        
        Returns:
            Tuple[tp1_pct, tp2_pct, sl_pct, details]
        """
        try:
            if not zones:
                return base_tp1_pct, base_tp2_pct, base_sl_pct, {"method": "base", "reason": "no_zones"}
            
            if direction == "LONG":
                # LONG: TP на зонах сопротивления выше, SL на зонах поддержки ниже
                resistance_zones = [z for z in zones if z.zone_type == "resistance" and z.low > entry_price]
                support_zones = [z for z in zones if z.zone_type == "support" and z.high < entry_price]
                
                # TP1: ближайшая зона сопротивления
                if resistance_zones:
                    nearest_resistance = min(resistance_zones, key=lambda x: x.low)
                    tp1_price = nearest_resistance.low
                    tp1_pct = ((tp1_price - entry_price) / entry_price) * 100
                    tp1_pct = max(tp1_pct, base_tp1_pct * 0.8)
                else:
                    tp1_pct = base_tp1_pct
                
                # TP2: следующая зона сопротивления выше TP1
                if resistance_zones:
                    higher_resistances = [z for z in resistance_zones if z.low > (entry_price * (1 + tp1_pct / 100))]
                    if higher_resistances:
                        tp2_zone = min(higher_resistances, key=lambda x: x.low)
                        tp2_price = tp2_zone.low
                        tp2_pct = ((tp2_price - entry_price) / entry_price) * 100
                        tp2_pct = max(tp2_pct, base_tp2_pct * 0.8)
                    else:
                        tp2_pct = base_tp2_pct
                else:
                    tp2_pct = base_tp2_pct
                
                # SL: ближайшая зона поддержки ниже
                if support_zones:
                    nearest_support = max(support_zones, key=lambda x: x.high)
                    sl_price = nearest_support.high
                    sl_pct = ((entry_price - sl_price) / entry_price) * 100
                    sl_pct = min(sl_pct, base_sl_pct * 1.2)
                else:
                    sl_pct = base_sl_pct
                
                return tp1_pct, tp2_pct, sl_pct, {
                    "method": "interest_zones",
                    "tp1_zone_strength": nearest_resistance.strength if resistance_zones else None,
                    "tp2_zone_strength": tp2_zone.strength if resistance_zones and higher_resistances else None,
                    "sl_zone_strength": nearest_support.strength if support_zones else None,
                }
            
            else:  # SHORT
                # SHORT: TP на зонах поддержки ниже, SL на зонах сопротивления выше
                support_zones = [z for z in zones if z.zone_type == "support" and z.high < entry_price]
                resistance_zones = [z for z in zones if z.zone_type == "resistance" and z.low > entry_price]
                
                # TP1: ближайшая зона поддержки ниже
                if support_zones:
                    nearest_support = max(support_zones, key=lambda x: x.high)
                    tp1_price = nearest_support.high
                    tp1_pct = ((entry_price - tp1_price) / entry_price) * 100
                    tp1_pct = max(tp1_pct, base_tp1_pct * 0.8)
                else:
                    tp1_pct = base_tp1_pct
                
                # TP2: следующая зона поддержки ниже TP1
                if support_zones:
                    lower_supports = [z for z in support_zones if z.high < (entry_price * (1 - tp1_pct / 100))]
                    if lower_supports:
                        tp2_zone = max(lower_supports, key=lambda x: x.high)
                        tp2_price = tp2_zone.high
                        tp2_pct = ((entry_price - tp2_price) / entry_price) * 100
                        tp2_pct = max(tp2_pct, base_tp2_pct * 0.8)
                    else:
                        tp2_pct = base_tp2_pct
                else:
                    tp2_pct = base_tp2_pct
                
                # SL: ближайшая зона сопротивления выше
                if resistance_zones:
                    nearest_resistance = min(resistance_zones, key=lambda x: x.low)
                    sl_price = nearest_resistance.low
                    sl_pct = ((sl_price - entry_price) / entry_price) * 100
                    sl_pct = min(sl_pct, base_sl_pct * 1.2)
                else:
                    sl_pct = base_sl_pct
                
                return tp1_pct, tp2_pct, sl_pct, {
                    "method": "interest_zones",
                    "tp1_zone_strength": nearest_support.strength if support_zones else None,
                    "tp2_zone_strength": tp2_zone.strength if support_zones and lower_supports else None,
                    "sl_zone_strength": nearest_resistance.strength if resistance_zones else None,
                }
                
        except Exception as e:
            logger.error("❌ Ошибка расчета TP/SL от зон интереса: %s", e)
            return base_tp1_pct, base_tp2_pct, base_sl_pct, {"method": "base", "error": str(e)}


# Глобальный экземпляр
_zone_tp_sl_calculator: Optional[ZoneBasedTPSLCalculator] = None


def get_zone_tp_sl_calculator() -> ZoneBasedTPSLCalculator:
    """Получает глобальный экземпляр калькулятора"""
    global _zone_tp_sl_calculator
    if _zone_tp_sl_calculator is None:
        _zone_tp_sl_calculator = ZoneBasedTPSLCalculator()
    return _zone_tp_sl_calculator


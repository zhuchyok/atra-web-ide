"""
Fibonacci Retracement Calculator - расчет уровней Фибоначчи
"""

import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class FibonacciLevel:
    """Уровень Фибоначчи"""
    level: float  # Процент ретрайсмента (0.236, 0.382, 0.5, 0.618, 0.786)
    price: float  # Цена уровня
    strength: str  # "strong" | "medium" | "weak"


class FibonacciCalculator:
    """Калькулятор уровней Фибоначчи"""
    
    # Стандартные уровни Фибоначчи
    FIB_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786]
    
    def __init__(self):
        pass
    
    def calculate_fibonacci_levels(
        self,
        df: pd.DataFrame,
        lookback_periods: int = 100,
    ) -> List[FibonacciLevel]:
        """
        Рассчитывает уровни Фибоначчи на основе последних N свечей
        
        Args:
            df: DataFrame с OHLCV данными
            lookback_periods: Количество свечей для анализа
        
        Returns:
            List[FibonacciLevel]: Список уровней Фибоначчи
        """
        try:
            if len(df) < lookback_periods:
                lookback_periods = len(df)
            
            # Берем последние N свечей
            df_recent = df.tail(lookback_periods).copy()
            
            # Находим максимум и минимум
            high_max = df_recent['high'].max()
            low_min = df_recent['low'].min()
                
            # Определяем направление тренда
            current_price = df_recent['close'].iloc[-1]
            
            # Если текущая цена ближе к максимуму - восходящий тренд
            # Если ближе к минимуму - нисходящий тренд
            distance_to_high = abs(current_price - high_max)
            distance_to_low = abs(current_price - low_min)
            
            if distance_to_high < distance_to_low:
                # Восходящий тренд: рассчитываем от минимума к максимуму
                trend_direction = "up"
                swing_low = low_min
                swing_high = high_max
            else:
                # Нисходящий тренд: рассчитываем от максимума к минимуму
                trend_direction = "down"
                swing_high = high_max
                swing_low = low_min
            
            # Разница между максимумом и минимумом
            price_range = swing_high - swing_low
            
            if price_range == 0:
                logger.warning("⚠️ Нулевой диапазон цен для расчета Фибоначчи")
                return []
            
            # Рассчитываем уровни Фибоначчи
            fib_levels = []
            
            for fib_pct in self.FIB_LEVELS:
                if trend_direction == "up":
                    # Восходящий тренд: уровни ниже максимума
                    fib_price = swing_high - (price_range * fib_pct)
                else:
                    # Нисходящий тренд: уровни выше минимума
                    fib_price = swing_low + (price_range * fib_pct)
                
                # Определяем силу уровня
                # 0.618 и 0.382 - самые сильные уровни
                if fib_pct in [0.618, 0.382]:
                    strength = "strong"
                elif fib_pct == 0.5:
                    strength = "medium"
                else:
                    strength = "weak"
                
                fib_levels.append(FibonacciLevel(
                    level=fib_pct,
                    price=fib_price,
                    strength=strength
                ))
            
            # Сортируем по цене (от меньшей к большей)
            fib_levels.sort(key=lambda x: x.price)
            
            return fib_levels
            
        except Exception as e:
            logger.error("❌ Ошибка расчета уровней Фибоначчи: %s", e)
            return []
    
    def find_nearest_fib_level(
        self,
        price: float,
        fib_levels: List[FibonacciLevel],
        tolerance_pct: float = 0.5
    ) -> Optional[FibonacciLevel]:
        """
        Находит ближайший уровень Фибоначчи к заданной цене
        
        Args:
            price: Цена для поиска
            fib_levels: Список уровней Фибоначчи
            tolerance_pct: Допустимое отклонение (% от цены)
        
        Returns:
            FibonacciLevel или None
        """
        if not fib_levels:
            return None
        
        tolerance = price * (tolerance_pct / 100)
        nearest = None
        min_distance = float('inf')
        
        for fib_level in fib_levels:
            distance = abs(price - fib_level.price)
            if distance <= tolerance and distance < min_distance:
                min_distance = distance
                nearest = fib_level
        
        return nearest
    
    def is_price_at_fib_level(
        self,
        price: float,
        fib_levels: List[FibonacciLevel],
        tolerance_pct: float = 0.5
    ) -> Tuple[bool, Optional[FibonacciLevel]]:
        """
        Проверяет, находится ли цена на уровне Фибоначчи
        
        Args:
            price: Цена для проверки
            fib_levels: Список уровней Фибоначчи
            tolerance_pct: Допустимое отклонение (% от цены)
        
        Returns:
            Tuple[bool, Optional[FibonacciLevel]]: (находится ли на уровне, уровень)
        """
        nearest = self.find_nearest_fib_level(price, fib_levels, tolerance_pct)
        return (nearest is not None, nearest)

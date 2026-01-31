"""
Fibonacci Zone Filter - фильтр зон Фибоначчи
Использует уровни ретрайсментов Фибоначчи как точки входа/выхода
"""

import logging
from typing import Dict, Any, Optional, List

from src.filters.base import BaseFilter, FilterResult
from src.technical.fibonacci import FibonacciCalculator, FibonacciLevel

logger = logging.getLogger(__name__)


class FibonacciZoneFilter(BaseFilter):
    """
    Фильтр зон Фибоначчи
    
    Логика:
    - LONG: разрешаем вблизи уровней поддержки (0.618, 0.786 для восходящего тренда)
    - SHORT: разрешаем вблизи уровней сопротивления (0.236, 0.382 для нисходящего тренда)
    - Блокируем входы вдали от уровней Фибоначчи
    """
    
    def __init__(
        self,
        enabled: bool = True,
        lookback_periods: int = 100,
        tolerance_pct: float = 0.5,  # Допустимое отклонение от уровня (%)
        require_strong_levels: bool = False,  # Требовать только сильные уровни (0.618, 0.382)
    ):
        super().__init__(
            name="FibonacciZoneFilter",
            enabled=enabled,
            priority=5  # Низкий приоритет (после других фильтров)
        )
        self.lookback_periods = lookback_periods
        self.tolerance_pct = tolerance_pct
        self.require_strong_levels = require_strong_levels
        self.fib_calculator = FibonacciCalculator()
    
    async def filter_signal(self, signal_data: Dict[str, Any]) -> FilterResult:
        """
        Фильтрует сигнал на основе уровней Фибоначчи
        
        Args:
            signal_data: Данные сигнала
                - direction: "LONG" | "SHORT"
                - symbol: торговый символ
                - entry_price: цена входа
                - df: DataFrame с OHLCV данными
        
        Returns:
            FilterResult: Результат фильтрации
        """
        if not self.enabled:
            return FilterResult(passed=True, reason="FILTER_DISABLED")
        
        self.filter_stats['total_checked'] += 1
        
        try:
            direction = signal_data.get("direction", "").upper()
            symbol = signal_data.get("symbol", "")
            entry_price = signal_data.get("entry_price") or signal_data.get("close")
            df = signal_data.get("df")
            
            if df is None or len(df) < 50:
                logger.debug("⚠️ FibonacciZoneFilter: недостаточно данных для %s, пропускаем", symbol)
                return FilterResult(passed=True, reason="INSUFFICIENT_DATA")
            
            if entry_price is None:
                logger.debug("⚠️ FibonacciZoneFilter: нет цены входа для %s, пропускаем", symbol)
                return FilterResult(passed=True, reason="NO_ENTRY_PRICE")
            
            # Рассчитываем уровни Фибоначчи
            fib_levels = self.fib_calculator.calculate_fibonacci_levels(
                df,
                lookback_periods=self.lookback_periods
            )
            
            if not fib_levels:
                # Нет уровней - разрешаем сигнал (не блокируем)
                self.filter_stats['passed'] += 1
                return FilterResult(passed=True, reason="NO_FIB_LEVELS")
            
            # Проверяем, находится ли цена на уровне Фибоначчи
            is_at_level, nearest_level = self.fib_calculator.is_price_at_fib_level(
                entry_price,
                fib_levels,
                tolerance_pct=self.tolerance_pct
            )
            
            if not is_at_level:
                # Цена не на уровне - разрешаем (не блокируем, но снижаем приоритет)
                self.filter_stats['passed'] += 1
                return FilterResult(
                    passed=True,
                    reason="PRICE_NOT_AT_FIB_LEVEL",
                    details={
                        "fib_levels_count": len(fib_levels),
                        "nearest_level": nearest_level.level if nearest_level else None
                    }
                )
            
            # Цена на уровне - проверяем соответствие направлению
            if self.require_strong_levels and nearest_level.strength != "strong":
                # Требуем сильные уровни, но уровень слабый - разрешаем
                self.filter_stats['passed'] += 1
                return FilterResult(
                    passed=True,
                    reason="WEAK_FIB_LEVEL",
                    details={"level": nearest_level.level, "strength": nearest_level.strength}
                )
            
            # Определяем, подходит ли уровень для направления
            fib_level_value = nearest_level.level
            
            if direction == "LONG":
                # LONG: разрешаем на уровнях поддержки (0.618, 0.786, 0.5)
                if fib_level_value in [0.618, 0.786, 0.5]:
                    self.filter_stats['passed'] += 1
                    return FilterResult(
                        passed=True,
                        reason="AT_FIB_SUPPORT",
                        details={
                            "level": fib_level_value,
                            "strength": nearest_level.strength,
                            "price": nearest_level.price
                        }
                    )
                else:
                    # LONG на уровне сопротивления - блокируем
                    self.filter_stats['blocked'] += 1
                    return FilterResult(
                        passed=False,
                        reason="AT_FIB_RESISTANCE",
                        details={
                            "level": fib_level_value,
                            "strength": nearest_level.strength,
                            "message": f"LONG сигнал на уровне сопротивления Фибоначчи ({fib_level_value})"
                        }
                    )
            
            elif direction == "SHORT":
                # SHORT: разрешаем на уровнях сопротивления (0.236, 0.382, 0.5)
                if fib_level_value in [0.236, 0.382, 0.5]:
                    self.filter_stats['passed'] += 1
                    return FilterResult(
                        passed=True,
                        reason="AT_FIB_RESISTANCE",
                        details={
                            "level": fib_level_value,
                            "strength": nearest_level.strength,
                            "price": nearest_level.price
                        }
                    )
                else:
                    # SHORT на уровне поддержки - блокируем
                    self.filter_stats['blocked'] += 1
                    return FilterResult(
                        passed=False,
                        reason="AT_FIB_SUPPORT",
                        details={
                            "level": fib_level_value,
                            "strength": nearest_level.strength,
                            "message": f"SHORT сигнал на уровне поддержки Фибоначчи ({fib_level_value})"
                        }
                    )
            
            # Неизвестное направление - разрешаем
            self.filter_stats['passed'] += 1
            return FilterResult(passed=True, reason="UNKNOWN_DIRECTION")
            
        except Exception as e:
            logger.error("❌ Ошибка в FibonacciZoneFilter: %s", e)
            self.filter_stats['errors'] += 1
            # При ошибке разрешаем сигнал (graceful degradation)
            return FilterResult(passed=True, reason="ERROR_FALLBACK", details={"error": str(e)})

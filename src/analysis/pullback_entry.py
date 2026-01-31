"""
Pullback Entry Logic - логика входа на откате к поддержке/сопротивлению
"""

import logging
from typing import Dict, Any, Optional, Tuple

import pandas as pd

from src.analysis.market_structure import MarketStructureAnalyzer
from src.analysis.entry_quality import EntryQualityScorer
from src.patterns.candle_patterns import CandlePatternDetector
from src.technical.fibonacci import FibonacciCalculator

logger = logging.getLogger(__name__)

# Импорт адаптивной стратегии (опционально)
try:
    from src.strategies.adaptive_strategy import AdaptiveStrategySelector
    ADAPTIVE_STRATEGY_AVAILABLE = True
    logger.debug("✅ AdaptiveStrategySelector доступен")
except ImportError as e:
    ADAPTIVE_STRATEGY_AVAILABLE = False
    AdaptiveStrategySelector = None
    logger.debug("⚠️ AdaptiveStrategySelector недоступен: %s", e)


class PullbackEntryLogic:
    """
    Логика входа на откате к поддержке/сопротивлению

    Вместо запоздалого EMA кроссовера использует:
    - Вход на откате к поддержке (для LONG)
    - Вход на откате к сопротивлению (для SHORT)
    - Подтверждение свечными паттернами
    - Проверку структуры рынка
    """

    def __init__(self, use_adaptive_strategy: bool = False):
        self.market_structure = MarketStructureAnalyzer()
        self.entry_quality = EntryQualityScorer()
        self.candle_patterns = CandlePatternDetector()
        self.fib_calculator = FibonacciCalculator()

        # Инициализация адаптивной стратегии (если доступна и включена)
        self.use_adaptive_strategy = use_adaptive_strategy and ADAPTIVE_STRATEGY_AVAILABLE
        if self.use_adaptive_strategy and AdaptiveStrategySelector:
            self.adaptive_selector = AdaptiveStrategySelector()
            logger.info("✅ Адаптивная стратегия инициализирована")
        else:
            self.adaptive_selector = None

    def is_near_support(
        self,
        df: pd.DataFrame,
        current_price: float,
        tolerance_pct: float = 0.8  # Оптимизировано: уменьшено с 1.0 до 0.8 для более строгих уровней
    ) -> Tuple[bool, Optional[float]]:
        """
        Проверяет, находится ли цена вблизи уровня поддержки

        Args:
            df: DataFrame с OHLCV данными
            current_price: Текущая цена
            tolerance_pct: Допустимое отклонение от уровня (%)

        Returns:
            Tuple[находится_ли_вблизи, уровень_поддержки]
        """
        try:
            if len(df) < 50:
                return False, None

            # Ищем уровни поддержки (локальные минимумы)
            lookback = min(50, len(df))
            recent_lows = df['low'].tail(lookback).values

            support_levels = []
            for i in range(2, len(recent_lows) - 2):
                if (recent_lows[i] < recent_lows[i-1] and
                    recent_lows[i] < recent_lows[i-2] and
                    recent_lows[i] < recent_lows[i+1] and
                    recent_lows[i] < recent_lows[i+2]):
                    support_levels.append(recent_lows[i])

            if not support_levels:
                return False, None

            # Ищем ближайший уровень поддержки
            tolerance = current_price * (tolerance_pct / 100)
            for support in sorted(support_levels, reverse=True):  # От большего к меньшему
                if current_price >= support and (current_price - support) <= tolerance:
                    return True, support

            # Проверяем EMA как поддержку
            if 'ema_fast' in df.columns and 'ema_slow' in df.columns:
                ema_fast = df['ema_fast'].iloc[-1]

                # Для LONG: цена должна быть выше EMA, но близко к ней
                if current_price >= ema_fast:
                    distance_to_ema = (current_price - ema_fast) / ema_fast * 100
                    if distance_to_ema <= tolerance_pct:
                        return True, ema_fast

            # Проверяем уровни Фибоначчи
            fib_levels = self.fib_calculator.calculate_fibonacci_levels(df, lookback_periods=lookback)
            if fib_levels:
                for fib_level in fib_levels:
                    if fib_level.price < current_price:
                        distance_pct = abs(current_price - fib_level.price) / current_price * 100
                        if distance_pct <= tolerance_pct:
                            return True, fib_level.price

            return False, None
        except Exception as e:
            logger.error("❌ Ошибка проверки поддержки: %s", e)
            return False, None

    def is_near_resistance(
        self,
        df: pd.DataFrame,
        current_price: float,
        tolerance_pct: float = 0.8  # Оптимизировано: уменьшено с 1.0 до 0.8 для более строгих уровней
    ) -> Tuple[bool, Optional[float]]:
        """
        Проверяет, находится ли цена вблизи уровня сопротивления

        Args:
            df: DataFrame с OHLCV данными
            current_price: Текущая цена
            tolerance_pct: Допустимое отклонение от уровня (%)

        Returns:
            Tuple[находится_ли_вблизи, уровень_сопротивления]
        """
        try:
            if len(df) < 50:
                return False, None

            # Ищем уровни сопротивления (локальные максимумы)
            lookback = min(50, len(df))
            recent_highs = df['high'].tail(lookback).values

            resistance_levels = []
            for i in range(2, len(recent_highs) - 2):
                if (recent_highs[i] > recent_highs[i-1] and
                    recent_highs[i] > recent_highs[i-2] and
                    recent_highs[i] > recent_highs[i+1] and
                    recent_highs[i] > recent_highs[i+2]):
                    resistance_levels.append(recent_highs[i])

            if not resistance_levels:
                return False, None

            # Ищем ближайший уровень сопротивления
            tolerance = current_price * (tolerance_pct / 100)
            for resistance in sorted(resistance_levels):  # От меньшего к большему
                if current_price <= resistance and (resistance - current_price) <= tolerance:
                    return True, resistance

            # Проверяем EMA как сопротивление
            if 'ema_fast' in df.columns and 'ema_slow' in df.columns:
                ema_fast = df['ema_fast'].iloc[-1]

                # Для SHORT: цена должна быть ниже EMA, но близко к ней
                if current_price <= ema_fast:
                    distance_to_ema = (ema_fast - current_price) / current_price * 100
                    if distance_to_ema <= tolerance_pct:
                        return True, ema_fast

            # Проверяем уровни Фибоначчи
            fib_levels = self.fib_calculator.calculate_fibonacci_levels(df, lookback_periods=lookback)
            if fib_levels:
                for fib_level in fib_levels:
                    if fib_level.price > current_price:
                        distance_pct = abs(current_price - fib_level.price) / current_price * 100
                        if distance_pct <= tolerance_pct:
                            return True, fib_level.price

            return False, None
        except Exception as e:
            logger.error("❌ Ошибка проверки сопротивления: %s", e)
            return False, None

    def should_enter_long(
        self,
        df: pd.DataFrame,
        current_price: float,
        min_quality_score: float = 0.7,  # Оптимизировано: увеличено с 0.6 до 0.7
        require_trend: bool = True,
        use_adaptive_config: bool = False,  # Использовать адаптивную конфигурацию
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Определяет, следует ли входить в LONG на откате к поддержке

        Args:
            df: DataFrame с OHLCV данными
            current_price: Текущая цена
            min_quality_score: Минимальная оценка качества входа
            require_trend: Требовать ли тренд

        Returns:
            Tuple[следует_ли_входить, детали_анализа]
        """
        try:
            details = {
                "reason": "",
                "quality_score": 0.0,
                "market_regime": "",
                "near_support": False,
                "has_pattern": False,
            }

            # 🆕 АДАПТИВНАЯ КОНФИГУРАЦИЯ (если включена)
            if self.use_adaptive_strategy and self.adaptive_selector:
                try:
                    adaptive_config = self.adaptive_selector.get_entry_config(df)
                    min_quality_score = adaptive_config.get("min_quality_score", min_quality_score)
                    require_trend = adaptive_config.get("require_trend", require_trend)
                    details["adaptive_config"] = adaptive_config
                    logger.debug("🎯 Используется адаптивная конфигурация: %s", adaptive_config.get("regime", "UNKNOWN"))
                except Exception as e:
                    logger.debug("⚠️ Ошибка адаптивной конфигурации: %s, используем базовую", e)

            # 1. Проверка структуры рынка
            regime_info = self.market_structure.get_regime_info(df)
            regime = regime_info["regime"]
            details["market_regime"] = regime

            if require_trend:
                if regime not in ["TREND_UP", "RANGE"]:
                    details["reason"] = f"Неподходящий режим рынка: {regime}"
                    return False, details

            # 2. Проверка отката к поддержке
            near_support, support_level = self.is_near_support(df, current_price)
            details["near_support"] = near_support
            details["support_level"] = support_level

            if not near_support:
                details["reason"] = "Цена не вблизи поддержки"
                return False, details

            # 3. Проверка свечных паттернов
            has_pattern = self.candle_patterns.has_bullish_pattern(df)
            details["has_pattern"] = has_pattern

            # 4. Оценка качества входа
            quality_score, quality_details = self.entry_quality.calculate_entry_quality_score(
                df, "LONG", current_price
            )
            details["quality_score"] = quality_score
            details["quality_details"] = quality_details

            if quality_score < min_quality_score:
                details["reason"] = f"Низкое качество входа: {quality_score:.2f} < {min_quality_score}"
                return False, details

            # 5. Проверка силы тренда (ADX)
            if regime == "TREND_UP":
                adx = regime_info.get("adx", 0)
                if adx < 20:  # Слабый тренд
                    details["reason"] = f"Слабый тренд (ADX={adx:.1f} < 20)"
                    return False, details

            details["reason"] = "Все условия выполнены"
            return True, details

        except Exception as e:
            logger.error("❌ Ошибка проверки входа LONG: %s", e)
            return False, {"reason": f"Ошибка: {str(e)}"}

    def should_enter_short(
        self,
        df: pd.DataFrame,
        current_price: float,
        min_quality_score: float = 0.7,  # Оптимизировано: увеличено с 0.6 до 0.7
        require_trend: bool = True,
        use_adaptive_config: bool = False,  # Использовать адаптивную конфигурацию
    ) -> Tuple[bool, Dict[str, Any]]:
        """
        Определяет, следует ли входить в SHORT на откате к сопротивлению

        Args:
            df: DataFrame с OHLCV данными
            current_price: Текущая цена
            min_quality_score: Минимальная оценка качества входа
            require_trend: Требовать ли тренд

        Returns:
            Tuple[следует_ли_входить, детали_анализа]
        """
        try:
            details = {
                "reason": "",
                "quality_score": 0.0,
                "market_regime": "",
                "near_resistance": False,
                "has_pattern": False,
            }

            # 1. Проверка структуры рынка
            regime_info = self.market_structure.get_regime_info(df)
            regime = regime_info["regime"]
            details["market_regime"] = regime

            if require_trend:
                if regime not in ["TREND_DOWN", "RANGE"]:
                    details["reason"] = f"Неподходящий режим рынка: {regime}"
                    return False, details

            # 2. Проверка отката к сопротивлению
            near_resistance, resistance_level = self.is_near_resistance(df, current_price)
            details["near_resistance"] = near_resistance
            details["resistance_level"] = resistance_level

            if not near_resistance:
                details["reason"] = "Цена не вблизи сопротивления"
                return False, details

            # 3. Проверка свечных паттернов
            has_pattern = self.candle_patterns.has_bearish_pattern(df)
            details["has_pattern"] = has_pattern

            # 4. Оценка качества входа
            quality_score, quality_details = self.entry_quality.calculate_entry_quality_score(
                df, "SHORT", current_price
            )
            details["quality_score"] = quality_score
            details["quality_details"] = quality_details

            if quality_score < min_quality_score:
                details["reason"] = f"Низкое качество входа: {quality_score:.2f} < {min_quality_score}"
                return False, details

            # 5. Проверка силы тренда (ADX)
            if regime == "TREND_DOWN":
                adx = regime_info.get("adx", 0)
                if adx < 20:  # Слабый тренд
                    details["reason"] = f"Слабый тренд (ADX={adx:.1f} < 20)"
                    return False, details

            details["reason"] = "Все условия выполнены"
            return True, details

        except Exception as e:
            logger.error("❌ Ошибка проверки входа SHORT: %s", e)
            return False, {"reason": f"Ошибка: {str(e)}"}


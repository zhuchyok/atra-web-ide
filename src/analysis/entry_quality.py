"""
Entry Quality Scorer - оценка качества точки входа
"""

import logging
from typing import Dict, Optional, Tuple

import pandas as pd
import numpy as np
import talib  # type: ignore # noqa: E1101

from src.analysis.market_structure import MarketStructureAnalyzer
from src.analysis.volume_profile import VolumeProfileAnalyzer
from src.indicators.momentum import MomentumAnalyzer
from src.patterns.candle_patterns import CandlePatternDetector

logger = logging.getLogger(__name__)


class EntryQualityScorer:
    """
    Оценщик качества входа

    Оценивает:
    - Расстояние от локального экстремума
    - Подтверждение свечными паттернами
    - Подтверждение объемом
    - Привязку к уровням (поддержка/сопротивление)
    """

    def __init__(
        self,
        atr_period: int = 14,
        lookback_periods: int = 20,
    ):
        self.atr_period = atr_period
        self.lookback_periods = lookback_periods
        self.market_structure = MarketStructureAnalyzer()
        self.candle_patterns = CandlePatternDetector()
        self.volume_profile = VolumeProfileAnalyzer()
        self.momentum = MomentumAnalyzer()

    def calculate_atr(self, df: pd.DataFrame) -> float:
        """
        Рассчитывает текущий ATR

        Args:
            df: DataFrame с OHLCV данными

        Returns:
            Текущее значение ATR
        """
        try:
            if len(df) < self.atr_period:
                return 0.0

            high = df['high'].values
            low = df['low'].values
            close = df['close'].values

            atr = talib.ATR(high, low, close, timeperiod=self.atr_period)  # type: ignore[no-member]  # pylint: disable=no-member
            return float(atr[-1]) if not np.isnan(atr[-1]) else 0.0
        except Exception as e:
            logger.error("❌ Ошибка расчета ATR: %s", e)
            return 0.0

    def calculate_distance_score(self, df: pd.DataFrame, direction: str) -> float:
        """
        Рассчитывает оценку расстояния от локального экстремума (0.0 - 1.0)

        Чем ближе к экстремуму, тем выше оценка

        Args:
            df: DataFrame с OHLCV данными
            direction: "LONG" или "SHORT"

        Returns:
            Оценка расстояния (0.0 - 1.0)
        """
        try:
            if len(df) < self.lookback_periods:
                return 0.5  # Нейтральная оценка

            current_price = df['close'].iloc[-1]
            atr = self.calculate_atr(df)

            if atr == 0:
                return 0.5

            if direction.upper() == "LONG":
                # Ищем локальный минимум
                recent_lows = df['low'].tail(self.lookback_periods).values
                local_min = np.min(recent_lows)

                # Расстояние от минимума в ATR
                distance_atr = (current_price - local_min) / atr

                # Идеальное расстояние: 0.5-1.5 ATR от минимума
                if 0.5 <= distance_atr <= 1.5:
                    return 1.0
                elif distance_atr < 0.5:
                    # Слишком близко к минимуму (может быть еще ниже)
                    return max(0.0, distance_atr / 0.5)
                else:
                    # Слишком далеко от минимума
                    return max(0.0, 1.0 - (distance_atr - 1.5) / 2.0)

            elif direction.upper() == "SHORT":
                # Ищем локальный максимум
                recent_highs = df['high'].tail(self.lookback_periods).values
                local_max = np.max(recent_highs)

                # Расстояние от максимума в ATR
                distance_atr = (local_max - current_price) / atr

                # Идеальное расстояние: 0.5-1.5 ATR от максимума
                if 0.5 <= distance_atr <= 1.5:
                    return 1.0
                elif distance_atr < 0.5:
                    # Слишком близко к максимуму
                    return max(0.0, distance_atr / 0.5)
                else:
                    # Слишком далеко от максимума
                    return max(0.0, 1.0 - (distance_atr - 1.5) / 2.0)

            return 0.5
        except Exception as e:
            logger.error("❌ Ошибка расчета оценки расстояния: %s", e)
            return 0.5

    def get_pattern_score(self, df: pd.DataFrame, direction: str) -> float:
        """
        Получает оценку свечных паттернов

        Args:
            df: DataFrame с OHLCV данными
            direction: "LONG" или "SHORT"

        Returns:
            Оценка паттернов (0.0 - 1.0)
        """
        return self.candle_patterns.get_pattern_score(df, direction)

    def get_volume_confirmation(self, df: pd.DataFrame, direction: str) -> float:
        """
        Получает оценку подтверждения объемом (0.0 - 1.0)

        Args:
            df: DataFrame с OHLCV данными
            direction: "LONG" или "SHORT"

        Returns:
            Оценка подтверждения объемом (0.0 - 1.0)
        """
        try:
            if len(df) < 20:
                return 0.5

            current_volume = df['volume'].iloc[-1]
            avg_volume = df['volume'].tail(20).mean()

            if avg_volume == 0:
                return 0.5

            volume_ratio = current_volume / avg_volume

            # Для LONG: высокий объем на росте = хорошо
            # Для SHORT: высокий объем на падении = хорошо
            if direction.upper() == "LONG":
                price_change = df['close'].iloc[-1] - df['open'].iloc[-1]
                if price_change > 0 and volume_ratio > 1.2:
                    return 1.0
                elif price_change > 0 and volume_ratio > 1.0:
                    return 0.7
                else:
                    return 0.3

            elif direction.upper() == "SHORT":
                price_change = df['open'].iloc[-1] - df['close'].iloc[-1]
                if price_change > 0 and volume_ratio > 1.2:
                    return 1.0
                elif price_change > 0 and volume_ratio > 1.0:
                    return 0.7
                else:
                    return 0.3

            return 0.5
        except Exception as e:
            logger.error("❌ Ошибка расчета подтверждения объемом: %s", e)
            return 0.5

    def get_level_score(
        self,
        df: pd.DataFrame,
        direction: str,
        entry_price: float,
        use_volume_profile: bool = True,
    ) -> float:
        """
        Получает оценку привязки к уровням (поддержка/сопротивление)

        Args:
            df: DataFrame с OHLCV данными
            direction: "LONG" или "SHORT"
            entry_price: Цена входа

        Returns:
            Оценка привязки к уровням (0.0 - 1.0)
        """
        try:
            if len(df) < 50:
                return 0.5

            # Ищем уровни поддержки/сопротивления
            recent_highs = df['high'].tail(50).values
            recent_lows = df['low'].tail(50).values

            # Рассчитываем ATR для определения близости
            atr = self.calculate_atr(df)
            if atr == 0:
                return 0.5

            tolerance = atr * 0.5  # Допустимое расстояние от уровня

            if direction.upper() == "LONG":
                # Ищем уровень поддержки (локальные минимумы)
                support_levels = []
                for i in range(1, len(recent_lows) - 1):
                    if recent_lows[i] < recent_lows[i-1] and recent_lows[i] < recent_lows[i+1]:
                        support_levels.append(recent_lows[i])

                if support_levels:
                    nearest_support = min(support_levels, key=lambda x: abs(x - entry_price))
                    distance = abs(entry_price - nearest_support)
                    if distance <= tolerance:
                        return 1.0
                    elif distance <= tolerance * 2:
                        return 0.7
                    else:
                        return 0.3

            elif direction.upper() == "SHORT":
                # Ищем уровень сопротивления (локальные максимумы)
                resistance_levels = []
                for i in range(1, len(recent_highs) - 1):
                    if recent_highs[i] > recent_highs[i-1] and recent_highs[i] > recent_highs[i+1]:
                        resistance_levels.append(recent_highs[i])

                if resistance_levels:
                    nearest_resistance = min(resistance_levels, key=lambda x: abs(x - entry_price))
                    distance = abs(entry_price - nearest_resistance)
                    if distance <= tolerance:
                        return 1.0
                    elif distance <= tolerance * 2:
                        return 0.7
                    else:
                        return 0.3

            return 0.5
        except Exception as e:
            logger.error("❌ Ошибка расчета оценки уровней: %s", e)
            return 0.5

    def calculate_entry_quality_score(
        self,
        df: pd.DataFrame,
        direction: str,
        entry_price: float,
        weights: Optional[Dict[str, float]] = None,
        include_momentum: bool = True,
    ) -> Tuple[float, Dict[str, float]]:
        """
        Рассчитывает общую оценку качества входа (0.0 - 1.0)

        Args:
            df: DataFrame с OHLCV данными
            direction: "LONG" или "SHORT"
            entry_price: Цена входа
            weights: Веса компонентов (по умолчанию равные)

        Returns:
            Tuple[общая_оценка, детали_компонентов]
        """
        try:
            if weights is None:
                # Оптимизированные веса: больше внимания к паттернам и уровням
                weights = {
                    "distance": 0.20,  # Уменьшено с 0.25
                    "pattern": 0.35,   # Увеличено с 0.25 (свечные паттерны важнее)
                    "volume": 0.20,   # Уменьшено с 0.25
                    "level": 0.25,    # Без изменений (уровни критичны)
                }

            # Рассчитываем компоненты
            distance_score = self.calculate_distance_score(df, direction)
            pattern_score = self.get_pattern_score(df, direction)
            volume_score = self.get_volume_confirmation(df, direction)
            level_score = self.get_level_score(df, direction, entry_price, use_volume_profile=True)

            # 🆕 Добавляем оценку импульса (Momentum)
            momentum_score = 0.5  # По умолчанию нейтральная
            if include_momentum:
                try:
                    momentum_confirmed, momentum_score = self.momentum.is_momentum_confirmed(
                        df, direction, min_score=0.6
                    )
                    momentum_score = momentum_score if momentum_confirmed else 0.3
                except Exception as e:
                    logger.debug("Ошибка расчета импульса: %s", e)

            # Обновляем веса с учетом импульса
            if include_momentum:
                # Перераспределяем веса: импульс получает 0.15, остальные уменьшаются
                base_weight = 0.20
                momentum_weight = 0.20
                adjusted_weights = {
                    "distance": weights.get("distance", base_weight) * 0.8,
                    "pattern": weights.get("pattern", base_weight) * 0.8,
                    "volume": weights.get("volume", base_weight) * 0.8,
                    "level": weights.get("level", base_weight) * 0.8,
                    "momentum": momentum_weight,
                }
            else:
                adjusted_weights = weights

            # Взвешенная сумма
            if include_momentum:
                total_score = (
                    distance_score * adjusted_weights.get("distance", 0.16) +
                    pattern_score * adjusted_weights.get("pattern", 0.16) +
                    volume_score * adjusted_weights.get("volume", 0.16) +
                    level_score * adjusted_weights.get("level", 0.16) +
                    momentum_score * adjusted_weights.get("momentum", 0.20)
                )
            else:
                total_score = (
                    distance_score * weights.get("distance", 0.25) +
                    pattern_score * weights.get("pattern", 0.25) +
                    volume_score * weights.get("volume", 0.25) +
                    level_score * weights.get("level", 0.25)
                )

            details = {
                "distance": distance_score,
                "pattern": pattern_score,
                "volume": volume_score,
                "level": level_score,
                "momentum": momentum_score if include_momentum else 0.5,
                "total": total_score,
            }

            return total_score, details

        except Exception as e:
            logger.error("❌ Ошибка расчета оценки качества входа: %s", e)
            return 0.5, {
                "distance": 0.5,
                "pattern": 0.5,
                "volume": 0.5,
                "level": 0.5,
                "total": 0.5,
            }

    def is_entry_quality_acceptable(
        self,
        df: pd.DataFrame,
        direction: str,
        entry_price: float,
        min_score: float = 0.6
    ) -> Tuple[bool, float, Dict[str, float]]:
        """
        Проверяет, является ли качество входа приемлемым

        Args:
            df: DataFrame с OHLCV данными
            direction: "LONG" или "SHORT"
            entry_price: Цена входа
            min_score: Минимальная оценка для приемлемого входа

        Returns:
            Tuple[приемлемо, общая_оценка, детали]
        """
        score, details = self.calculate_entry_quality_score(df, direction, entry_price)
        return score >= min_score, score, details

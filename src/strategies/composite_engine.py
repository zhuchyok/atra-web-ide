#!/usr/bin/env python3

"""
Composite Signal Engine - взвешенная оценка множественных торговых стратегий
Объединяет Trend Following, Mean Reversion, Breakout, Volume Analysis
"""

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class CompositeSignalEngine:
    """
    Движок композитных сигналов

    Объединяет:
    1. Trend Following - следование за трендом
    2. Mean Reversion - возврат к среднему
    3. Breakout - пробой уровней
    4. Volume Analysis - анализ объемов
    """

    def __init__(self):
        self.signal_history = []

        # 🆕 ADAPTIVE WEIGHTS - статистика для самообучения
        self.strategy_performance = {
            "trend": {"total": 0, "successful": 0, "avg_pnl": 0.0, "weight": 0.35},
            "mean_reversion": {"total": 0, "successful": 0, "avg_pnl": 0.0, "weight": 0.25},
            "breakout": {"total": 0, "successful": 0, "avg_pnl": 0.0, "weight": 0.25},
            "volume": {"total": 0, "successful": 0, "avg_pnl": 0.0, "weight": 0.15},
        }
        self.last_weight_update = 0
        self.weight_update_interval = 3600  # Обновляем веса каждый час

    def calculate_composite_score(
        self, df: pd.DataFrame, asset_group: str, regime: str, signal_type: str = "BUY"
    ) -> Dict[str, Any]:
        """
        Рассчитывает композитный score на основе множества стратегий

        Args:
            df: DataFrame с OHLC и индикаторами
            asset_group: Группа актива (BTC_HIGH, ETH_MEDIUM и т.д.)
            regime: Рыночный режим (BULL_TREND, BEAR_TREND и т.д.)
            signal_type: Тип сигнала (BUY/SELL)

        Returns:
            Dict с composite_score, confidence, components
        """
        try:
            # 1. Рассчитываем базовые сигналы
            trend_score = self._trend_following_signal(df, signal_type)
            mean_rev_score = self._mean_reversion_signal(df, signal_type)
            breakout_score = self._breakout_signal(df, signal_type)
            volume_score = self._volume_analysis_signal(df)

            # 2. Получаем адаптивные веса
            weights = self._get_adaptive_weights(asset_group, regime)

            # 3. Рассчитываем взвешенный композитный score
            composite_score = (
                trend_score * weights["trend"]
                + mean_rev_score * weights["mean_reversion"]
                + breakout_score * weights["breakout"]
                + volume_score * weights["volume"]
            )

            # 4. Рассчитываем уверенность (согласованность сигналов)
            components = [trend_score, mean_rev_score, breakout_score, volume_score]
            confidence = self._calculate_confidence(components, weights)

            logger.debug(
                "📊 Composite: trend=%.2f, mean_rev=%.2f, breakout=%.2f, volume=%.2f → score=%.2f (conf: %.2f)",
                trend_score,
                mean_rev_score,
                breakout_score,
                volume_score,
                composite_score,
                confidence,
            )

            return {
                "composite_score": composite_score,
                "confidence": confidence,
                "components": {
                    "trend_following": trend_score,
                    "mean_reversion": mean_rev_score,
                    "breakout": breakout_score,
                    "volume_analysis": volume_score,
                },
                "weights": weights,
            }

        except Exception as e:
            logger.error("❌ Ошибка расчета composite signal: %s", e)
            return {"composite_score": 0.5, "confidence": 0.0, "components": {}, "weights": {}}

    def _trend_following_signal(self, df: pd.DataFrame, signal_type: str) -> float:
        """
        Сигнал следования за трендом (0-1)

        Использует:
        - EMA кроссовер
        - ADX (сила тренда)
        - Направление тренда
        """
        try:
            score = 0.0

            # EMA кроссовер
            if "ema_fast" in df.columns and "ema_slow" in df.columns:
                ema_fast = df["ema_fast"].iloc[-1]
                ema_slow = df["ema_slow"].iloc[-1]
                current_price = df["close"].iloc[-1]

                if signal_type == "BUY":
                    if current_price > ema_fast > ema_slow:
                        score += 0.4
                    elif ema_fast > ema_slow:
                        score += 0.2
                elif signal_type == "SELL":
                    if current_price < ema_fast < ema_slow:
                        score += 0.4
                    elif ema_fast < ema_slow:
                        score += 0.2

            # ADX (сила тренда)
            if "adx" in df.columns:
                adx = df["adx"].iloc[-1]
                if adx > 25:
                    score += 0.3
                elif adx > 20:
                    score += 0.2
                elif adx > 15:
                    score += 0.1

            # Направление тренда (последние 10 свечей)
            if len(df) >= 10:
                price_10 = df["close"].iloc[-10]
                price_now = df["close"].iloc[-1]
                trend_direction = (price_now - price_10) / price_10

                if signal_type == "BUY" and trend_direction > 0:
                    score += min(trend_direction * 10, 0.3)  # макс +0.3
                elif signal_type == "SELL" and trend_direction < 0:
                    score += min(abs(trend_direction) * 10, 0.3)

            return min(score, 1.0)

        except Exception as e:
            logger.debug("Ошибка trend_following: %s", e)
            return 0.5

    def _mean_reversion_signal(self, df: pd.DataFrame, signal_type: str) -> float:
        """
        Сигнал возврата к среднему (0-1)

        Использует:
        - RSI (перекупленность/перепроданность)
        - Bollinger Bands (отклонение от средней)
        - Отклонение от MA
        """
        try:
            score = 0.0

            # RSI
            if "rsi" in df.columns:
                rsi = df["rsi"].iloc[-1]

                if signal_type == "BUY":
                    if rsi < 30:
                        score += 0.5  # Сильная перепроданность
                    elif rsi < 40:
                        score += 0.3
                    elif rsi < 50:
                        score += 0.1
                elif signal_type == "SELL":
                    if rsi > 70:
                        score += 0.5  # Сильная перекупленность
                    elif rsi > 60:
                        score += 0.3
                    elif rsi > 50:
                        score += 0.1

            # Bollinger Bands
            if "bb_upper" in df.columns and "bb_lower" in df.columns and "bb_mavg" in df.columns:
                current_price = df["close"].iloc[-1]
                bb_upper = df["bb_upper"].iloc[-1]
                bb_lower = df["bb_lower"].iloc[-1]
                bb_middle = df["bb_mavg"].iloc[-1]

                bb_width = bb_upper - bb_lower
                if bb_width > 0:
                    bb_position = (current_price - bb_lower) / bb_width  # 0-1

                    if signal_type == "BUY" and bb_position < 0.2:
                        score += 0.3  # Близко к нижней границе
                    elif signal_type == "SELL" and bb_position > 0.8:
                        score += 0.3  # Близко к верхней границе

            # Отклонение от MA
            if "sma_20" in df.columns:
                sma_20 = df["sma_20"].iloc[-1]
                current_price = df["close"].iloc[-1]
                deviation = (current_price - sma_20) / sma_20 * 100

                if signal_type == "BUY" and deviation < -2:
                    score += 0.2  # Ниже MA на 2%+
                elif signal_type == "SELL" and deviation > 2:
                    score += 0.2  # Выше MA на 2%+

            return min(score, 1.0)

        except Exception as e:
            logger.debug("Ошибка mean_reversion: %s", e)
            return 0.5

    def _breakout_signal(self, df: pd.DataFrame, signal_type: str) -> float:
        """
        Сигнал пробоя (0-1)

        Использует:
        - Пробой исторических high/low
        - Volume spike при пробое
        - Расстояние от уровня
        """
        try:
            score = 0.0
            current_price = df["close"].iloc[-1]

            # Пробой исторических уровней (20 свечей)
            if len(df) >= 20:
                high_20 = df["high"].iloc[-20:-1].max()
                low_20 = df["low"].iloc[-20:-1].min()

                if signal_type == "BUY" and current_price > high_20:
                    breakout_strength = (current_price - high_20) / high_20 * 100
                    score += min(breakout_strength * 10, 0.5)  # макс +0.5

                elif signal_type == "SELL" and current_price < low_20:
                    breakout_strength = (low_20 - current_price) / low_20 * 100
                    score += min(breakout_strength * 10, 0.5)

            # Volume spike при пробое
            if "volume" in df.columns and len(df) >= 20:
                current_volume = df["volume"].iloc[-1]
                avg_volume_20 = df["volume"].iloc[-20:-1].mean()

                if avg_volume_20 > 0:
                    volume_ratio = current_volume / avg_volume_20

                    if volume_ratio > 1.5:
                        score += 0.3  # Сильный объем
                    elif volume_ratio > 1.2:
                        score += 0.2

            # Близость к уровню (чем ближе пробой, тем сильнее сигнал)
            if len(df) >= 20:
                if signal_type == "BUY":
                    resistance = df["high"].iloc[-20:-1].max()
                    distance_pct = abs(current_price - resistance) / resistance * 100
                    if distance_pct < 0.5:
                        score += 0.2  # Очень близко

                elif signal_type == "SELL":
                    support = df["low"].iloc[-20:-1].min()
                    distance_pct = abs(current_price - support) / support * 100
                    if distance_pct < 0.5:
                        score += 0.2

            return min(score, 1.0)

        except Exception as e:
            logger.debug("Ошибка breakout: %s", e)
            return 0.5

    def _volume_analysis_signal(self, df: pd.DataFrame) -> float:
        """
        Анализ объемов (0-1)

        Использует:
        - Текущий объем vs средний
        - OBV (On-Balance Volume)
        - Volume trend
        """
        try:
            score = 0.0

            # Volume Ratio из индикаторов
            if "volume_ratio" in df.columns:
                volume_ratio = df["volume_ratio"].iloc[-1]

                if volume_ratio > 2.0:
                    score += 0.5  # Очень высокий объем
                elif volume_ratio > 1.5:
                    score += 0.4
                elif volume_ratio > 1.2:
                    score += 0.3
                elif volume_ratio > 1.0:
                    score += 0.2
                else:
                    score += 0.1  # Низкий объем

            # OBV (On-Balance Volume)
            if "obv" in df.columns and len(df) >= 10:
                obv_change = (df["obv"].iloc[-1] - df["obv"].iloc[-10]) / abs(
                    df["obv"].iloc[-10] + 1e-10
                )
                if obv_change > 0.05:
                    score += 0.2  # OBV растет

            # Тренд объема (растет или падает)
            if len(df) >= 10:
                volume_trend = df["volume"].iloc[-10:].corr(pd.Series(range(10)))

                if volume_trend > 0.3:
                    score += 0.3  # Объем растет
                elif volume_trend > 0:
                    score += 0.2

            return min(score, 1.0)

        except Exception as e:
            logger.debug("Ошибка volume_analysis: %s", e)
            return 0.5

    def _get_adaptive_weights(self, asset_group: str, regime: str) -> Dict[str, float]:
        """
        Адаптивные веса стратегий на основе группы актива и режима рынка

        Returns:
            Dict с весами для каждой стратегии (сумма = 1.0)
        """
        # Базовые веса по группе актива
        base_weights = {
            "BTC_HIGH": {"trend": 0.40, "mean_reversion": 0.20, "breakout": 0.25, "volume": 0.15},
            "BTC_MEDIUM": {"trend": 0.35, "mean_reversion": 0.25, "breakout": 0.25, "volume": 0.15},
            "BTC_LOW": {"trend": 0.30, "mean_reversion": 0.30, "breakout": 0.25, "volume": 0.15},
            "ETH_HIGH": {"trend": 0.35, "mean_reversion": 0.25, "breakout": 0.25, "volume": 0.15},
            "ETH_MEDIUM": {"trend": 0.30, "mean_reversion": 0.30, "breakout": 0.25, "volume": 0.15},
            "SOL_HIGH": {"trend": 0.30, "mean_reversion": 0.25, "breakout": 0.30, "volume": 0.15},
            "SOL_MEDIUM": {"trend": 0.25, "mean_reversion": 0.30, "breakout": 0.30, "volume": 0.15},
            "INDEPENDENT": {
                "trend": 0.25,
                "mean_reversion": 0.35,
                "breakout": 0.25,
                "volume": 0.15,
            },
            "OTHER": {"trend": 0.30, "mean_reversion": 0.30, "breakout": 0.25, "volume": 0.15},
        }

        # Коррекция по режиму рынка
        regime_adjustments = {
            "BULL_TREND": {
                "trend": 1.4,  # Тренд важнее
                "mean_reversion": 0.6,  # Mean reversion менее важен
                "breakout": 1.2,
            },
            "BEAR_TREND": {
                "trend": 0.7,  # Тренд менее важен
                "mean_reversion": 1.3,  # Mean reversion важнее
                "breakout": 0.8,
            },
            "HIGH_VOL_RANGE": {
                "mean_reversion": 1.4,  # Mean reversion важнее
                "breakout": 0.9,
                "volume": 1.2,
            },
            "LOW_VOL_RANGE": {"trend": 1.1, "breakout": 1.2, "volume": 0.9},
            "CRASH": {
                "trend": 0.5,  # Все сигналы слабее
                "mean_reversion": 0.5,
                "breakout": 0.5,
                "volume": 1.0,
            },
        }

        # Получаем базовые веса
        weights = base_weights.get(asset_group, base_weights["OTHER"]).copy()

        # Применяем коррекцию по режиму
        adjustments = regime_adjustments.get(regime, {})
        for strategy, adjustment in adjustments.items():
            if strategy in weights:
                weights[strategy] *= adjustment

        # Нормализуем веса (сумма = 1.0)
        total = sum(weights.values())
        if total > 0:
            weights = {k: v / total for k, v in weights.items()}

        return weights

    def _calculate_confidence(self, components: list, weights: Dict[str, float]) -> float:
        """
        Рассчитывает уверенность на основе согласованности сигналов

        Если все стратегии согласны → высокая уверенность
        Если расходятся → низкая уверенность
        """
        try:
            if not components:
                return 0.0

            # Средний score
            mean_score = np.mean(components)

            # Стандартное отклонение (разброс)
            std_score = np.std(components)

            # Уверенность обратно пропорциональна разбросу
            # std = 0 → confidence = 1.0
            # std = 0.5 → confidence = 0.0
            confidence = max(0.0, 1.0 - (std_score * 2))

            # Корректируем на основе среднего score
            # Если средний score высокий и разброс низкий → очень высокая уверенность
            if mean_score > 0.7 and std_score < 0.2:
                confidence = min(1.0, confidence * 1.2)

            return confidence

        except Exception as e:
            logger.debug("Ошибка confidence: %s", e)
            return 0.5

    # 🆕 ADAPTIVE WEIGHTS METHODS

    def update_strategy_performance(self, strategy: str, was_successful: bool, pnl_pct: float):
        """
        Обновляет статистику производительности стратегии

        Args:
            strategy: 'trend', 'mean_reversion', 'breakout', 'volume'
            was_successful: Была ли сделка успешной
            pnl_pct: Прибыль/убыток в процентах
        """
        if strategy not in self.strategy_performance:
            return

        perf = self.strategy_performance[strategy]
        perf["total"] += 1
        if was_successful:
            perf["successful"] += 1

        # Экспоненциальное сглаживание среднего PnL
        alpha = 0.1
        perf["avg_pnl"] = perf["avg_pnl"] * (1 - alpha) + pnl_pct * alpha

        logger.debug(
            "📊 [ADAPTIVE] %s: total=%d, successful=%d, avg_pnl=%.2f%%",
            strategy,
            perf["total"],
            perf["successful"],
            perf["avg_pnl"],
        )

    async def recalculate_adaptive_weights(self):
        """
        Пересчитывает веса стратегий на основе их производительности

        Вызывается автоматически каждый час
        """
        import time

        current_time = time.time()
        if current_time - self.last_weight_update < self.weight_update_interval:
            return  # Еще рано обновлять

        try:
            # Считаем новые веса на основе производительности
            new_weights = {}
            total_score = 0.0

            for strategy, perf in self.strategy_performance.items():
                if perf["total"] < 10:
                    # Недостаточно данных, используем текущий вес
                    new_weights[strategy] = perf["weight"]
                    total_score += perf["weight"]
                    continue

                # Рассчитываем score на основе winrate и avg_pnl
                winrate = perf["successful"] / perf["total"]
                pnl_factor = 1.0 + (perf["avg_pnl"] / 100)  # Нормализуем PnL

                score = winrate * pnl_factor
                new_weights[strategy] = score
                total_score += score

            # Нормализуем веса (сумма = 1.0)
            if total_score > 0:
                for strategy in new_weights:
                    new_weight = new_weights[strategy] / total_score

                    # Плавное изменение (не более 20% за раз)
                    current_weight = self.strategy_performance[strategy]["weight"]
                    max_change = current_weight * 0.2
                    delta = new_weight - current_weight
                    delta = max(-max_change, min(max_change, delta))

                    self.strategy_performance[strategy]["weight"] = current_weight + delta

            self.last_weight_update = current_time

            logger.info(
                "✅ [ADAPTIVE WEIGHTS] Веса обновлены: trend=%.2f, mean_rev=%.2f, breakout=%.2f, volume=%.2f",
                self.strategy_performance["trend"]["weight"],
                self.strategy_performance["mean_reversion"]["weight"],
                self.strategy_performance["breakout"]["weight"],
                self.strategy_performance["volume"]["weight"],
            )

        except Exception as e:
            logger.error("❌ Ошибка пересчета adaptive weights: %s", e)

    def get_adaptive_weights_stats(self) -> Dict[str, Any]:
        """Возвращает статистику adaptive weights"""
        stats = {}
        for strategy, perf in self.strategy_performance.items():
            if perf["total"] > 0:
                stats[strategy] = {
                    "weight": perf["weight"],
                    "total_trades": perf["total"],
                    "winrate": perf["successful"] / perf["total"],
                    "avg_pnl": perf["avg_pnl"],
                }
        return stats


# Глобальный экземпляр
_composite_engine = None


def get_composite_engine() -> CompositeSignalEngine:
    """Получение глобального экземпляра композитного движка"""
    global _composite_engine
    if _composite_engine is None:
        _composite_engine = CompositeSignalEngine()
        logger.info("✅ CompositeSignalEngine инициализирован")
    return _composite_engine

#!/usr/bin/env python3

"""
Market Regime Detector - определение текущего рыночного режима
Адаптирует параметры торговой системы под текущие рыночные условия
"""

import logging
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class MarketRegimeDetector:
    """
    Детектор рыночных режимов

    Определяет:
    - BULL_TREND: Бычий тренд (BTC > EMA200, ADX > 25)
    - BEAR_TREND: Медвежий тренд (BTC < EMA200, ADX > 25)
    - HIGH_VOL_RANGE: Высокая волатильность, флэт (ATR > avg * 1.5, ADX < 20)
    - LOW_VOL_RANGE: Низкая волатильность, флэт (ATR < avg * 0.8, ADX < 20)
    - CRASH: Крах рынка (падение > 8%, высокая волатильность)
    """

    def __init__(self):
        self.current_regime = None
        self.regime_confidence = 0.0
        self.regime_history = []

        # Пороги для определения режимов
        self.thresholds = {
            "ema_period": 200,
            "adx_trend_threshold": 25,
            "adx_range_threshold": 20,
            "atr_high_vol_ratio": 1.5,
            "atr_low_vol_ratio": 0.8,
            "crash_drop_pct": 8.0,
            "crash_atr_ratio": 2.0,
        }

    def detect_regime(self, btc_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Определяет текущий рыночный режим

        Args:
            btc_data: DataFrame с OHLC данными BTC (должен содержать EMA, ADX, ATR)

        Returns:
            Dict с 'regime', 'confidence', 'probabilities'
        """
        try:
            if btc_data is None or len(btc_data) < 200:
                logger.warning("⚠️ Недостаточно данных BTC для определения режима")
                return self._get_default_regime()

            # Рассчитываем индикаторы если их нет
            btc_data = self._ensure_indicators(btc_data)

            # Текущие значения
            current_price = btc_data["close"].iloc[-1]
            ema_200 = (
                btc_data["ema_200"].iloc[-1]
                if "ema_200" in btc_data
                else btc_data["close"].rolling(200).mean().iloc[-1]
            )
            adx = btc_data["adx"].iloc[-1] if "adx" in btc_data else 20

            # ATR анализ
            atr_current = (
                btc_data["atr"].iloc[-1]
                if "atr" in btc_data
                else btc_data["close"].diff().abs().rolling(14).mean().iloc[-1]
            )
            atr_avg = (
                btc_data["atr"].rolling(20).mean().iloc[-1] if "atr" in btc_data else atr_current
            )
            atr_ratio = atr_current / atr_avg if atr_avg > 0 else 1.0

            # Проверка падения (для CRASH)
            price_change_5m = (
                ((current_price - btc_data["close"].iloc[-5]) / btc_data["close"].iloc[-5] * 100)
                if len(btc_data) > 5
                else 0
            )

            # ОПРЕДЕЛЕНИЕ РЕЖИМА
            regime_scores = {
                "BULL_TREND": 0.0,
                "BEAR_TREND": 0.0,
                "HIGH_VOL_RANGE": 0.0,
                "LOW_VOL_RANGE": 0.0,
                "CRASH": 0.0,
            }

            # 1. CRASH (приоритет)
            if (
                price_change_5m < -self.thresholds["crash_drop_pct"]
                and atr_ratio > self.thresholds["crash_atr_ratio"]
            ):
                regime_scores["CRASH"] = 0.9
                logger.warning(
                    "🚨 Обнаружен CRASH режим: падение %.2f%%, ATR ratio %.2f",
                    price_change_5m,
                    atr_ratio,
                )

            # 2. BULL TREND
            if current_price > ema_200 and adx > self.thresholds["adx_trend_threshold"]:
                trend_strength = min((current_price - ema_200) / ema_200 * 100, 10) / 10  # 0-1
                adx_strength = min((adx - self.thresholds["adx_trend_threshold"]) / 30, 1)  # 0-1
                regime_scores["BULL_TREND"] = (trend_strength + adx_strength) / 2

            # 3. BEAR TREND
            elif current_price < ema_200 and adx > self.thresholds["adx_trend_threshold"]:
                trend_strength = min((ema_200 - current_price) / ema_200 * 100, 10) / 10  # 0-1
                adx_strength = min((adx - self.thresholds["adx_trend_threshold"]) / 30, 1)  # 0-1
                regime_scores["BEAR_TREND"] = (trend_strength + adx_strength) / 2

            # 4. HIGH VOL RANGE
            if (
                adx < self.thresholds["adx_range_threshold"]
                and atr_ratio > self.thresholds["atr_high_vol_ratio"]
            ):
                regime_scores["HIGH_VOL_RANGE"] = min(
                    atr_ratio / self.thresholds["atr_high_vol_ratio"], 1.0
                )

            # 5. LOW VOL RANGE
            if (
                adx < self.thresholds["adx_range_threshold"]
                and atr_ratio < self.thresholds["atr_low_vol_ratio"]
            ):
                regime_scores["LOW_VOL_RANGE"] = min(
                    (self.thresholds["atr_low_vol_ratio"] - atr_ratio) / 0.3, 1.0
                )

            # Выбираем режим с максимальным score
            best_regime = max(regime_scores, key=regime_scores.get)
            confidence = regime_scores[best_regime]

            # Если confidence = 0, используем дефолтный режим с минимальной уверенностью
            if confidence == 0.0:
                # Пытаемся определить режим по базовым условиям
                if current_price > ema_200:
                    best_regime = "BULL_TREND"
                    confidence = 0.5  # Минимальная уверенность для бычьего тренда
                elif current_price < ema_200:
                    best_regime = "BEAR_TREND"
                    confidence = 0.5  # Минимальная уверенность для медвежьего тренда
                else:
                    best_regime = "LOW_VOL_RANGE"
                    confidence = 0.5  # Дефолтная уверенность

            # Сохраняем в историю
            self.current_regime = best_regime
            self.regime_confidence = confidence
            self.regime_history.append(
                {"regime": best_regime, "confidence": confidence, "timestamp": pd.Timestamp.now()}
            )

            # Ограничиваем историю последними 100 записями
            if len(self.regime_history) > 100:
                self.regime_history = self.regime_history[-100:]

            logger.info(
                "📊 Рыночный режим: %s (уверенность: %.1f%%), ADX: %.1f, ATR ratio: %.2f",
                best_regime,
                confidence * 100,
                adx,
                atr_ratio,
            )

            return {
                "regime": best_regime,
                "confidence": confidence,
                "probabilities": regime_scores,
                "indicators": {
                    "ema_200": ema_200,
                    "current_price": current_price,
                    "adx": adx,
                    "atr_ratio": atr_ratio,
                    "price_change_5m": price_change_5m,
                },
            }

        except Exception as e:
            logger.error("❌ Ошибка определения режима: %s", e)
            return self._get_default_regime()

    def _ensure_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Убеждаемся что все индикаторы рассчитаны"""
        try:
            # EMA 200
            if "ema_200" not in df.columns:
                df["ema_200"] = df["close"].ewm(span=200, adjust=False).mean()

            # ADX
            if "adx" not in df.columns:
                try:
                    import ta

                    df["adx"] = ta.trend.ADXIndicator(
                        df["high"], df["low"], df["close"], window=14
                    ).adx()
                except:
                    # Fallback: простое приближение
                    df["adx"] = 20.0

            # ATR
            if "atr" not in df.columns:
                try:
                    import ta

                    df["atr"] = ta.volatility.AverageTrueRange(
                        df["high"], df["low"], df["close"], window=14
                    ).average_true_range()
                except:
                    # Fallback: простое приближение
                    df["atr"] = df["close"].diff().abs().rolling(14).mean()

            return df

        except Exception as e:
            logger.error("❌ Ошибка расчета индикаторов для режима: %s", e)
            return df

    def _get_default_regime(self) -> Dict[str, Any]:
        """Режим по умолчанию при ошибках"""
        return {
            "regime": "LOW_VOL_RANGE",
            "confidence": 0.5,
            "probabilities": {
                "BULL_TREND": 0.0,
                "BEAR_TREND": 0.0,
                "HIGH_VOL_RANGE": 0.0,
                "LOW_VOL_RANGE": 0.5,
                "CRASH": 0.0,
            },
            "indicators": {},
        }

    def get_regime_multipliers(self, regime: str, confidence: float = 1.0) -> Dict[str, float]:
        """
        Возвращает множители параметров для режима

        Args:
            regime: Название режима
            confidence: Уверенность в режиме (0-1)

        Returns:
            Dict с множителями для position_size, sl_atr, tp_ratio, aggression
        """
        base_multipliers = {
            "BULL_TREND": {
                "position_size": 1.4,  # +40% размер позиции
                "sl_multiplier": 0.8,  # -20% SL (ужимаем стопы)
                "tp_multiplier": 1.5,  # +50% TP (расширяем цели)
                "aggression": 1.3,  # +30% агрессивность входов
                "quality_threshold": 0.90,  # 90% от базового порога (смягчаем)
            },
            "BEAR_TREND": {
                "position_size": 0.6,  # -40% размер позиции
                "sl_multiplier": 1.3,  # +30% SL (расширяем стопы)
                "tp_multiplier": 1.2,  # +20% TP (скромнее цели)
                "aggression": 0.7,  # -30% агрессивность
                "quality_threshold": 1.15,  # 115% от базового (строже)
            },
            "HIGH_VOL_RANGE": {
                "position_size": 0.8,  # -20% размер
                "sl_multiplier": 1.5,  # +50% SL (широкие стопы)
                "tp_multiplier": 1.3,  # +30% TP
                "aggression": 0.9,  # -10% агрессивность
                "quality_threshold": 1.10,  # 110% от базового
            },
            "LOW_VOL_RANGE": {
                "position_size": 1.2,  # +20% размер
                "sl_multiplier": 0.9,  # -10% SL (узкие стопы)
                "tp_multiplier": 1.4,  # +40% TP (амбициознее)
                "aggression": 1.1,  # +10% агрессивность
                "quality_threshold": 0.95,  # 95% от базового (мягче)
            },
            "CRASH": {
                "position_size": 0.3,  # -70% размер (ЗАЩИТА!)
                "sl_multiplier": 2.0,  # +100% SL (очень широкие)
                "tp_multiplier": 0.8,  # -20% TP (быстрая фиксация)
                "aggression": 0.3,  # -70% агрессивность (почти не входим)
                "quality_threshold": 1.50,  # 150% от базового (ОЧЕНЬ строго)
            },
        }

        regime_mult = base_multipliers.get(regime, base_multipliers["LOW_VOL_RANGE"])

        # Корректируем на основе уверенности
        adjusted_mult = {}
        for param, value in regime_mult.items():
            if param == "quality_threshold":
                # Для порога используем линейную интерполяцию
                adjusted_mult[param] = 1.0 + (value - 1.0) * confidence
            else:
                # Для остальных - также линейная интерполяция к 1.0
                adjusted_mult[param] = 1.0 + (value - 1.0) * confidence

        logger.debug(
            "🎛️ Режим %s (%.0f%%), множители: position=%.2f, sl=%.2f, tp=%.2f",
            regime,
            confidence * 100,
            adjusted_mult["position_size"],
            adjusted_mult["sl_multiplier"],
            adjusted_mult["tp_multiplier"],
        )

        return adjusted_mult

    def get_current_regime(self) -> Optional[str]:
        """Возвращает текущий режим"""
        return self.current_regime

    def get_regime_statistics(self) -> Dict[str, Any]:
        """Статистика по режимам за последнее время"""
        if not self.regime_history:
            return {}

        # Последние 24 записи (примерно за день при часовых проверках)
        recent = self.regime_history[-24:]

        regime_counts = {}
        for record in recent:
            regime = record["regime"]
            regime_counts[regime] = regime_counts.get(regime, 0) + 1

        total = len(recent)
        regime_percentages = {
            regime: (count / total * 100) for regime, count in regime_counts.items()
        }

        return {
            "current_regime": self.current_regime,
            "current_confidence": self.regime_confidence,
            "regime_distribution": regime_percentages,
            "records_analyzed": total,
        }


# Глобальный экземпляр детектора
_regime_detector = None


def get_regime_detector() -> MarketRegimeDetector:
    """Получение глобального экземпляра детектора режимов"""
    global _regime_detector
    if _regime_detector is None:
        _regime_detector = MarketRegimeDetector()
        logger.info("✅ MarketRegimeDetector инициализирован")
    return _regime_detector

#!/usr/bin/env python3

"""
False Breakout Detector - детектор ложных пробоев
Фильтрует ложные сигналы на основе объема, momentum и уровней
"""

import logging
from collections import deque
from typing import Any, Dict, Optional, Tuple

import pandas as pd

try:
    from db import Database

    DB_AVAILABLE = True
except ImportError:  # pragma: no cover
    Database = None  # type: ignore
    DB_AVAILABLE = False

logger = logging.getLogger(__name__)


class FalseBreakoutDetector:
    """
    Детектор ложных пробоев

    Проверяет:
    1. Volume spike - подтверждение объемом
    2. Momentum strength - сила движения
    3. Level break quality - качество пробоя уровня
    """

    def __init__(self):
        # Настройки (ослаблены для интрадей)
        self.settings = {
            "lookback_candles": 20,
            "volume_spike_multiplier": 1.5,  # Минимум 1.5x среднего объема
            "min_volume_confidence": 0.7,
            "min_momentum_confidence": 0.6,
            "min_level_confidence": 0.6,
            "min_total_confidence": 0.20,  # 🔧 ОСЛАБЛЕНО для интрадей (было 0.40)
            "confirmation_candles": 2,
            "recent_window": 200,
            "target_pass_rate_low": 0.45,
            "target_pass_rate_high": 0.70,
            "adaptive_step_relax": 0.12,
            "adaptive_step_tighten": 0.02,
            "volatility_high_pct": 1.6,
            "volatility_low_pct": 1.15,
            "volatility_relaxation": 0.12,
            "volatility_tightening": 0.008,
            "min_confidence_floor": 0.15,  # 🔧 ОСЛАБЛЕНО для интрадей (было 0.25)
            "max_confidence_ceiling": 0.72,
            "regime_multiplier_bounds": (0.20, 0.60),  # 🔧 ОСЛАБЛЕНО (было 0.35, 0.60)
            "regime_thresholds": {
                "BULL_TREND": 0.20,  # 🔧 ОСЛАБЛЕНО (было 0.36)
                "BEAR_TREND": 0.25,  # 🔧 ОСЛАБЛЕНО (было 0.44)
                "HIGH_VOL_RANGE": 0.22,  # 🔧 ОСЛАБЛЕНО (было 0.40)
                "LOW_VOL_RANGE": 0.25,  # 🔧 ОСЛАБЛЕНО (было 0.46)
                "CRASH": 0.30,  # 🔧 ОСЛАБЛЕНО (было 0.50)
            },
            "refresh_interval": 150,
        }

        self.recent_results = deque(maxlen=self.settings["recent_window"])
        self.stats = {
            "total_checks": 0,
            "false_breakouts_detected": 0,
            "true_breakouts_passed": 0,
        }
        self._last_threshold_used = self.settings["min_total_confidence"]
        self._checks_since_refresh = 0
        self.db = Database() if DB_AVAILABLE else None
        self._seed_recent_results()
        self._load_runtime_overrides()

    async def analyze_breakout_quality(
        self,
        df: pd.DataFrame,
        symbol: str,
        direction: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Анализирует качество пробоя

        Args:
            df: DataFrame с OHLC данными
            symbol: Символ актива
            direction: 'BUY' или 'SELL'

        Returns:
            {
                'is_false_breakout': bool,
                'confidence': float (0-1),
                'details': dict
            }
        """
        try:
            self.stats["total_checks"] += 1
            self._checks_since_refresh += 1

            if self._checks_since_refresh >= self.settings["refresh_interval"]:
                self._load_runtime_overrides()
                self._checks_since_refresh = 0

            analysis_context = context or {}
            regime = analysis_context.get("regime")
            regime_confidence = analysis_context.get("regime_confidence")
            manual_threshold = analysis_context.get("min_total_confidence_override")
            ml_threshold = analysis_context.get("ml_false_breakout_threshold")  # 🆕 ML оптимизация

            if df is None or len(df) < self.settings["lookback_candles"]:
                logger.debug("⚠️ [FALSE BREAKOUT] %s: недостаточно данных", symbol)
                return {
                    "is_false_breakout": False,
                    "confidence": 0.5,
                    "details": {"reason": "insufficient_data"},
                }

            # 1. ПРОВЕРКА ОБЪЕМА (40% веса)
            volume_confidence = self._check_volume_spike(df)

            # 2. ПРОВЕРКА MOMENTUM (30% веса)
            momentum_confidence = self._check_momentum_strength(df, direction)

            # 3. ПРОВЕРКА УРОВНЯ (30% веса)
            level_confidence = self._check_level_break(df, direction)

            volatility_pct = analysis_context.get("atr_pct")
            threshold, volatility_pct = self._determine_confidence_threshold(
                regime,
                regime_confidence,
                df,
                volatility_pct=volatility_pct,
                manual_override=manual_threshold,
                ml_override=ml_threshold,  # 🆕 ML оптимизация
            )
            volatility_class = self._classify_volatility(volatility_pct)
            threshold = self._apply_regime_volatility_adjustment(
                threshold, regime, volatility_class
            )
            self._last_threshold_used = threshold

            # 🆕 ML-ОПТИМИЗИРОВАННЫЕ ВЕСА (если доступны)
            ml_weights = analysis_context.get("ml_false_breakout_weights")
            if ml_weights and isinstance(ml_weights, dict):
                # Используем ML-оптимизированные веса
                volume_weight = ml_weights.get("volume", 0.40)
                momentum_weight = ml_weights.get("momentum", 0.30)
                level_weight = ml_weights.get("level", 0.30)
                logger.debug(
                    "🤖 [ML_WEIGHTS] %s: Используем ML веса (vol=%.2f, mom=%.2f, lvl=%.2f)",
                    symbol,
                    volume_weight,
                    momentum_weight,
                    level_weight,
                )
            else:
                # Fallback: стандартные веса
                volume_weight = 0.40
                momentum_weight = 0.30
                level_weight = 0.30

            # Взвешенная комбинация с ML-оптимизированными весами
            total_confidence = (
                volume_confidence * volume_weight
                + momentum_confidence * momentum_weight
                + level_confidence * level_weight
            )

            # Определяем ложный пробой
            is_false_breakout = total_confidence < threshold
            self._update_recent_stats(not is_false_breakout)
            recent_pass_rate = self._calculate_recent_pass_rate()
            self._persist_event(
                symbol=symbol,
                direction=direction,
                total_confidence=total_confidence,
                threshold=threshold,
                passed=not is_false_breakout,
                regime=regime,
                regime_confidence=regime_confidence,
                volatility_pct=volatility_pct,
                volume_confidence=volume_confidence,
                momentum_confidence=momentum_confidence,
                level_confidence=level_confidence,
                recent_pass_rate=recent_pass_rate,
            )

            if is_false_breakout:
                self.stats["false_breakouts_detected"] += 1
                logger.info(
                    "🚫 [FALSE BREAKOUT] %s %s: уверенность %.2f < %.2f (vol: %.2f, mom: %.2f, lvl: %.2f)",
                    symbol,
                    direction,
                    total_confidence,
                    threshold,
                    volume_confidence,
                    momentum_confidence,
                    level_confidence,
                )
            else:
                self.stats["true_breakouts_passed"] += 1
                logger.debug(
                    "✅ [TRUE BREAKOUT] %s %s: уверенность %.2f (vol: %.2f, mom: %.2f, lvl: %.2f)",
                    symbol,
                    direction,
                    total_confidence,
                    volume_confidence,
                    momentum_confidence,
                    level_confidence,
                )

            return {
                "is_false_breakout": is_false_breakout,
                "confidence": total_confidence,
                "details": {
                    "volume_confidence": volume_confidence,
                    "momentum_confidence": momentum_confidence,
                    "level_confidence": level_confidence,
                    "threshold_used": threshold,
                    "recent_pass_rate": recent_pass_rate,
                    "regime": regime,
                    "regime_confidence": regime_confidence,
                    "volatility_pct": volatility_pct,
                    "symbol": symbol,
                    "direction": direction,
                },
            }

        except Exception as e:
            logger.error("❌ Ошибка анализа breakout для %s: %s", symbol, e)
            # Fallback: пропускаем сигнал (безопаснее)
            return {"is_false_breakout": False, "confidence": 0.5, "details": {"error": str(e)}}

    def _check_volume_spike(self, df: pd.DataFrame) -> float:
        """
        Проверка volume spike (0-1)

        Высокий объем при пробое = больше уверенность
        """
        try:
            if "volume" not in df.columns or len(df) < 20:
                return 0.5  # Нейтральная оценка

            current_volume = df["volume"].iloc[-1]
            avg_volume = df["volume"].rolling(self.settings["lookback_candles"]).mean().iloc[-1]

            if avg_volume == 0:
                return 0.5

            volume_ratio = current_volume / avg_volume

            # Рассчитываем confidence
            if volume_ratio >= self.settings["volume_spike_multiplier"] * 1.5:  # 2.25x
                confidence = 1.0
            elif volume_ratio >= self.settings["volume_spike_multiplier"]:  # 1.5x
                confidence = 0.8
            elif volume_ratio >= 1.2:
                confidence = 0.6
            elif volume_ratio >= 1.0:
                confidence = 0.4
            else:
                confidence = 0.2  # Низкий объем - плохо

            return confidence

        except Exception as e:
            logger.debug("Ошибка _check_volume_spike: %s", e)
            return 0.5

    def _check_momentum_strength(self, df: pd.DataFrame, direction: str) -> float:
        """
        Проверка силы momentum (0-1)

        Сильный momentum = больше уверенность
        """
        try:
            if len(df) < 10:
                return 0.5

            current_price = df["close"].iloc[-1]

            # Проверяем momentum за последние 5 свечей
            price_5 = df["close"].iloc[-5]
            momentum_5 = (current_price - price_5) / price_5 * 100

            # Проверяем momentum за последние 10 свечей
            price_10 = df["close"].iloc[-10]
            momentum_10 = (current_price - price_10) / price_10 * 100

            # Для BUY: положительный momentum
            # Для SELL: отрицательный momentum
            if direction == "BUY":
                # Проверяем растущий momentum
                if momentum_5 > 0 and momentum_10 > 0:
                    confidence = min(1.0, (abs(momentum_5) + abs(momentum_10)) / 10)
                elif momentum_5 > 0:
                    confidence = 0.6
                else:
                    confidence = 0.3  # Слабый momentum
            else:  # SELL
                # Проверяем падающий momentum
                if momentum_5 < 0 and momentum_10 < 0:
                    confidence = min(1.0, (abs(momentum_5) + abs(momentum_10)) / 10)
                elif momentum_5 < 0:
                    confidence = 0.6
                else:
                    confidence = 0.3

            return confidence

        except Exception as e:
            logger.debug("Ошибка _check_momentum_strength: %s", e)
            return 0.5

    def _check_level_break(self, df: pd.DataFrame, direction: str) -> float:
        """
        Проверка качества пробоя уровня (0-1)

        Чистый пробой уровня = больше уверенность
        """
        try:
            if len(df) < self.settings["lookback_candles"]:
                return 0.5

            current_price = df["close"].iloc[-1]

            # Определяем ключевые уровни за lookback период
            if direction == "BUY":
                # Для BUY проверяем пробой сопротивления (resistance)
                resistance = df["high"].iloc[-self.settings["lookback_candles"] : -1].max()

                # Проверяем, действительно ли пробили уровень
                if current_price > resistance:
                    # Расстояние от уровня (чем дальше, тем лучше)
                    distance_pct = ((current_price - resistance) / resistance) * 100

                    if distance_pct > 0.5:
                        confidence = 0.9  # Чистый пробой
                    elif distance_pct > 0.2:
                        confidence = 0.7
                    else:
                        confidence = 0.5  # Слабый пробой
                else:
                    confidence = 0.3  # Не пробили уровень
            else:  # SELL
                # Для SELL проверяем пробой поддержки (support)
                support = df["low"].iloc[-self.settings["lookback_candles"] : -1].min()

                if current_price < support:
                    distance_pct = ((support - current_price) / support) * 100

                    if distance_pct > 0.5:
                        confidence = 0.9
                    elif distance_pct > 0.2:
                        confidence = 0.7
                    else:
                        confidence = 0.5
                else:
                    confidence = 0.3

            return confidence

        except Exception as e:
            logger.debug("Ошибка _check_level_break: %s", e)
            return 0.5

    def get_statistics(self) -> Dict[str, Any]:
        """Возвращает статистику детектора"""
        if self.stats["total_checks"] == 0:
            return {"total_checks": 0, "false_breakout_rate": 0.0, "true_breakout_rate": 0.0}

        return {
            "total_checks": self.stats["total_checks"],
            "false_breakouts_detected": self.stats["false_breakouts_detected"],
            "true_breakouts_passed": self.stats["true_breakouts_passed"],
            "false_breakout_rate": self.stats["false_breakouts_detected"]
            / self.stats["total_checks"],
            "true_breakout_rate": self.stats["true_breakouts_passed"] / self.stats["total_checks"],
            "recent_pass_rate": self._calculate_recent_pass_rate(),
            "last_threshold_used": self._last_threshold_used,
        }

    def reset_statistics(self):
        """Сбрасывает статистику"""
        self.stats = {"total_checks": 0, "false_breakouts_detected": 0, "true_breakouts_passed": 0}
        self.recent_results.clear()
        self._last_threshold_used = self.settings["min_total_confidence"]

    def _update_recent_stats(self, passed: bool) -> None:
        """Обновляет окно последних результатов."""
        self.recent_results.append(1 if passed else 0)

    def _calculate_recent_pass_rate(self) -> Optional[float]:
        """Возвращает долю прошедших сигналов в последнем окне."""
        if not self.recent_results:
            return None
        return sum(self.recent_results) / len(self.recent_results)

    def _determine_confidence_threshold(
        self,
        regime: Optional[str],
        regime_confidence: Optional[float],
        df: pd.DataFrame,
        volatility_pct: Optional[float] = None,
        manual_override: Optional[float] = None,
        ml_override: Optional[float] = None,  # 🆕 ML оптимизация
    ) -> Tuple[float, Optional[float]]:
        """Определяет динамический порог уверенности."""
        threshold = self.settings["min_total_confidence"]

        # 🆕 ПРИОРИТЕТ 1: ML оптимизация (если доступна)
        if ml_override is not None:
            threshold = float(ml_override)
            logger.debug(
                "🤖 [ML_FALSE_BREAKOUT] Используем ML оптимизированный порог: %.3f", threshold
            )
        elif manual_override is not None:
            threshold = float(manual_override)

        elif regime:
            regime_thresholds = self.settings.get("regime_thresholds", {})
            threshold = regime_thresholds.get(regime, threshold)
            if regime_confidence is not None:
                threshold -= 0.05 * (
                    1 - float(regime_confidence)
                )  # расслабляем при низкой уверенности

        if volatility_pct is None:
            volatility_pct = self._estimate_intraday_volatility(df)

        if volatility_pct is not None:
            if volatility_pct >= self.settings["volatility_high_pct"]:
                threshold -= self.settings["volatility_relaxation"]
            elif volatility_pct <= self.settings["volatility_low_pct"]:
                threshold += self.settings["volatility_tightening"]

        recent_pass_rate = self._calculate_recent_pass_rate()
        if recent_pass_rate is not None:
            if recent_pass_rate < self.settings["target_pass_rate_low"]:
                threshold -= self.settings["adaptive_step_relax"]
            elif recent_pass_rate > self.settings["target_pass_rate_high"]:
                threshold += self.settings["adaptive_step_tighten"]

        threshold = max(self.settings["min_confidence_floor"], threshold)
        threshold = min(self.settings["max_confidence_ceiling"], threshold)

        return threshold, volatility_pct

    def _classify_volatility(self, volatility_pct: Optional[float]) -> str:
        if volatility_pct is None:
            return "MEDIUM"
        if volatility_pct >= self.settings["volatility_high_pct"]:
            return "HIGH"
        if volatility_pct <= self.settings["volatility_low_pct"]:
            return "LOW"
        return "MEDIUM"

    def _apply_regime_volatility_adjustment(
        self,
        base_threshold: float,
        regime: Optional[str],
        volatility_class: str,
    ) -> float:
        regime = (regime or "UNKNOWN").upper()
        regime_multipliers = {
            "BEAR_TREND": 0.90,
            "BULL_TREND": 0.92,
            "LOW_VOL_RANGE": 0.95,
            "RANGE": 0.95,
            "NEUTRAL": 1.0,
            "CRASH": 0.85,
        }
        vol_multipliers = {
            "HIGH": 0.90,
            "MEDIUM": 1.0,
            "LOW": 1.03,
        }

        multiplier = regime_multipliers.get(regime, 1.0)
        multiplier *= vol_multipliers.get(volatility_class, 1.0)

        adjusted = base_threshold * multiplier
        floor, ceil = self.settings["regime_multiplier_bounds"]
        adjusted = max(floor, min(ceil, adjusted))
        return adjusted

    def _estimate_intraday_volatility(self, df: pd.DataFrame) -> Optional[float]:
        """Приближенно оценивает текущую волатильность в процентах."""
        try:
            if any(col not in df.columns for col in ("high", "low", "close")):
                return None

            true_range = (df["high"] - df["low"]).abs()
            if true_range.empty or len(true_range) < 5:
                return None

            atr = true_range.rolling(window=14, min_periods=5).mean().iloc[-1]
            close_price = df["close"].iloc[-1]
            if close_price <= 0:
                return None

            return float((atr / close_price) * 100)
        except Exception as err:
            logger.debug("⚠️ Ошибка расчёта волатильности: %s", err)
            return None

    def _load_runtime_overrides(self) -> None:
        """Загружает переопределения порогов из базы данных."""
        if not self.db:
            return

        try:
            with self.db.get_lock():
                self.db.cursor.execute(
                    "SELECT key, value FROM system_settings WHERE key LIKE 'false_breakout.%'"
                )
                rows = self.db.cursor.fetchall()

            for key, value in rows:
                if not value:
                    continue
                try:
                    if key == "false_breakout.min_total_confidence":
                        self.settings["min_total_confidence"] = float(value)
                    elif key == "false_breakout.volume_multiplier":
                        self.settings["volume_spike_multiplier"] = float(value)
                    elif key == "false_breakout.pass_rate_low":
                        self.settings["target_pass_rate_low"] = float(value)
                    elif key == "false_breakout.pass_rate_high":
                        self.settings["target_pass_rate_high"] = float(value)
                except (TypeError, ValueError):
                    logger.debug("⚠️ Ignore invalid override %s=%s", key, value)
        except Exception as err:
            logger.debug("⚠️ Ошибка загрузки runtime overrides FalseBreakout: %s", err)

    def _seed_recent_results(self) -> None:
        """Загружает историю последнего окна из БД."""
        if not self.db:
            return
        try:
            with self.db.get_lock():
                self.db.cursor.execute(
                    """
                    SELECT passed
                    FROM false_breakout_events
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (self.recent_results.maxlen,),
                )
                rows = self.db.cursor.fetchall()
            for row in reversed(rows):
                if row and row[0] is not None:
                    self.recent_results.append(1 if row[0] else 0)
        except Exception as err:
            logger.debug("⚠️ Не удалось загрузить историю результатов FalseBreakout: %s", err)

    def _persist_event(
        self,
        symbol: str,
        direction: str,
        total_confidence: float,
        threshold: float,
        passed: bool,
        regime: Optional[str],
        regime_confidence: Optional[float],
        volatility_pct: Optional[float],
        volume_confidence: float,
        momentum_confidence: float,
        level_confidence: float,
        recent_pass_rate: Optional[float],
    ) -> None:
        """Сохраняет результат работы детектора для последующего анализа."""
        if not self.db:
            return
        try:
            with self.db.get_lock():
                self.db.cursor.execute(
                    """
                    INSERT INTO false_breakout_events(
                        symbol,
                        direction,
                        confidence,
                        threshold,
                        passed,
                        regime,
                        regime_confidence,
                        volatility_pct,
                        volume_confidence,
                        momentum_confidence,
                        level_confidence,
                        recent_pass_rate
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        symbol,
                        direction,
                        float(total_confidence),
                        float(threshold),
                        1 if passed else 0,
                        regime,
                        float(regime_confidence) if regime_confidence is not None else None,
                        float(volatility_pct) if volatility_pct is not None else None,
                        float(volume_confidence),
                        float(momentum_confidence),
                        float(level_confidence),
                        float(recent_pass_rate) if recent_pass_rate is not None else None,
                    ),
                )
                self.db.conn.commit()
        except Exception as err:
            logger.debug("⚠️ Не удалось записать событие FalseBreakout: %s", err)


# Глобальный экземпляр
_false_breakout_detector = None


def get_false_breakout_detector() -> FalseBreakoutDetector:
    """Получение глобального экземпляра детектора"""
    global _false_breakout_detector
    if _false_breakout_detector is None:
        _false_breakout_detector = FalseBreakoutDetector()
        logger.info("✅ FalseBreakoutDetector инициализирован")
    return _false_breakout_detector

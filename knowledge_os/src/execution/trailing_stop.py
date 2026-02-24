#!/usr/bin/env python3

"""
Trailing Stop Loss Manager - автоматический перенос стопа в безубыток
Защищает прибыль при развороте цены
"""

import logging
import time
from datetime import datetime
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd

from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)


class AdvancedTrailingStopManager:
    """
    Продвинутая адаптивная система trailing stop

    Учитывает:
    - Волатильность (ATR, стандартное отклонение)
    - Силу тренда (ADX, наклон MA)
    - Рыночный режим (тренд, боковик)
    - Время суток (активные/спокойные часы)
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.adaptive_config = config.get("ADAPTIVE_TRAILING_CONFIG", {})

    def get_adaptive_progress_ratio(
        self, df: pd.DataFrame, symbol: str, direction: str, current_price: float
    ) -> float:
        """
        Продвинутый расчет адаптивного коэффициента для trailing stop

        Args:
            df: DataFrame с OHLCV данными
            symbol: Торговый символ
            direction: Направление позиции (LONG/SHORT)
            current_price: Текущая цена

        Returns:
            adaptive_ratio: Оптимальный коэффициент (0.15 - 1.2)
        """
        if not self.adaptive_config.get("enabled", True):
            return self.config.get("tp1_sl_progress_ratio", 1.0)

        try:
            # 1. Анализ волатильности
            volatility_ratio = self._analyze_volatility(df, current_price)

            # 2. Анализ тренда
            trend_ratio = self._analyze_trend_strength(df, direction)

            # 3. Анализ рыночного режима
            regime_ratio = self._analyze_market_regime(df)

            # 4. Временные факторы
            time_ratio = self._analyze_time_factors()

            # 5. Комбинируем все факторы
            base_ratio = self._combine_factors(
                volatility_ratio, trend_ratio, regime_ratio, time_ratio
            )

            # 6. Применяем ограничения
            final_ratio = self._apply_constraints(base_ratio, df, current_price)

            logger.info(
                "🎯 Адаптивный SL для %s: ratio=%.3f "
                "(vol=%.3f, trend=%.3f, regime=%.3f, time=%.3f)",
                symbol,
                final_ratio,
                volatility_ratio,
                trend_ratio,
                regime_ratio,
                time_ratio,
            )

            return final_ratio

        except Exception as e:
            logger.error("❌ Ошибка расчета адаптивного SL: %s", e)
            return self.config.get("tp1_sl_progress_ratio", 1.0)

    def _analyze_volatility(self, df: pd.DataFrame, current_price: float) -> float:
        """Анализ волатильности на основе ATR и стандартного отклонения"""
        try:
            # Расчет ATR
            high_low = df["high"] - df["low"]
            high_close = np.abs(df["high"] - df["close"].shift())
            low_close = np.abs(df["low"] - df["close"].shift())
            true_range = np.maximum(np.maximum(high_low, high_close), low_close)
            atr = true_range.rolling(window=14).mean().iloc[-1]

            atr_pct = atr / current_price if current_price > 0 else 0

            # Дополнительно: стандартное отклонение
            returns = df["close"].pct_change().dropna()
            if len(returns) > 0:
                std_dev = returns.std()
            else:
                std_dev = 0

            # Комбинированная оценка волатильности
            combined_volatility = atr_pct * 0.7 + std_dev * 0.3

            # Определение режима волатильности
            regimes = self.adaptive_config.get("volatility_regimes", {})

            if combined_volatility < regimes.get("LOW", {}).get("atr_threshold", 0.01):
                regime = "LOW"
                base_ratio = regimes.get("LOW", {}).get("max_ratio", 1.0)
            elif combined_volatility < regimes.get("MEDIUM", {}).get("atr_threshold", 0.025):
                regime = "MEDIUM"
                # Интерполяция
                low_thresh = regimes.get("LOW", {}).get("atr_threshold", 0.01)
                med_thresh = regimes.get("MEDIUM", {}).get("atr_threshold", 0.025)
                progress = (
                    (combined_volatility - low_thresh) / (med_thresh - low_thresh)
                    if (med_thresh - low_thresh) > 0
                    else 0
                )
                base_ratio = (
                    regimes.get("LOW", {}).get("max_ratio", 1.0) * (1 - progress)
                    + regimes.get("MEDIUM", {}).get("max_ratio", 0.8) * progress
                )
            elif combined_volatility < regimes.get("HIGH", {}).get("atr_threshold", 0.05):
                regime = "HIGH"
                med_thresh = regimes.get("MEDIUM", {}).get("atr_threshold", 0.025)
                high_thresh = regimes.get("HIGH", {}).get("atr_threshold", 0.05)
                progress = (
                    (combined_volatility - med_thresh) / (high_thresh - med_thresh)
                    if (high_thresh - med_thresh) > 0
                    else 0
                )
                base_ratio = (
                    regimes.get("MEDIUM", {}).get("max_ratio", 0.8) * (1 - progress)
                    + regimes.get("HIGH", {}).get("max_ratio", 0.6) * progress
                )
            else:
                regime = "EXTREME"
                base_ratio = regimes.get("EXTREME", {}).get("min_ratio", 0.2)

            logger.debug(
                "📊 Волатильность: %.4f, режим: %s, ratio: %.3f",
                combined_volatility,
                regime,
                base_ratio,
            )
            return base_ratio

        except Exception as e:
            logger.error("Ошибка анализа волатильности: %s", e)
            return 0.7

    def _analyze_trend_strength(self, df: pd.DataFrame, direction: str) -> float:
        """Анализ силы тренда с использованием ADX и наклона MA"""
        try:
            # Упрощенный ADX расчет
            high, low, close = df["high"], df["low"], df["close"]

            # +DM и -DM
            plus_dm = high.diff()
            minus_dm = low.diff().abs()

            plus_dm = np.where((plus_dm > minus_dm) & (plus_dm > 0), plus_dm, 0)
            minus_dm = np.where((minus_dm > plus_dm) & (minus_dm > 0), minus_dm, 0)

            # True Range
            tr1 = high - low
            tr2 = abs(high - close.shift())
            tr3 = abs(low - close.shift())
            tr = np.maximum(np.maximum(tr1, tr2), tr3)

            # Скользящие средние
            period = 14
            atr = tr.rolling(period).mean()
            plus_di = 100 * (pd.Series(plus_dm, index=high.index).rolling(period).mean() / atr)
            minus_di = 100 * (pd.Series(minus_dm, index=low.index).rolling(period).mean() / atr)

            dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
            adx = dx.rolling(period).mean().iloc[-1] if not dx.empty and not dx.isna().all() else 25

            # Наклон скользящей средней
            ma_fast = close.rolling(20).mean()
            ma_slow = close.rolling(50).mean()

            if (
                len(ma_fast) > 5
                and len(ma_slow) > 5
                and not ma_fast.isna().iloc[-5]
                and not ma_slow.isna().iloc[-5]
            ):
                ma_fast_slope = (ma_fast.iloc[-1] - ma_fast.iloc[-5]) / ma_fast.iloc[-5]
                ma_slow_slope = (ma_slow.iloc[-1] - ma_slow.iloc[-5]) / ma_slow.iloc[-5]
                ma_alignment = 1.0 if (ma_fast_slope * ma_slow_slope) > 0 else 0.5
            else:
                ma_alignment = 0.5

            # Определение силы тренда
            if adx > 40 and ma_alignment > 0.8:
                trend_strength = "STRONG"
            elif adx > 25:
                trend_strength = "MEDIUM"
            elif adx < 20:
                trend_strength = "RANGING"
            else:
                trend_strength = "WEAK"

            # Проверка направления тренда
            if len(plus_di) > 0 and len(minus_di) > 0:
                if (
                    direction == "LONG"
                    and plus_di.iloc[-1] < minus_di.iloc[-1]
                    or direction == "SHORT"
                    and plus_di.iloc[-1] > minus_di.iloc[-1]
                ):
                    trend_strength = "REVERSAL"

            multiplier = self.adaptive_config.get("trend_strength", {}).get(trend_strength, 1.0)

            logger.debug(
                "📈 Тренд: ADX=%.1f, сила=%s, множитель=%.2f", adx, trend_strength, multiplier
            )
            return multiplier

        except Exception as e:
            logger.error("Ошибка анализа тренда: %s", e)
            return 1.0

    def _analyze_market_regime(self, df: pd.DataFrame) -> float:
        """Анализ общего рыночного режима"""
        try:
            # 1. Анализ волатильности кластерами
            returns_pct = df["close"].pct_change().dropna()
            volatility_rolling = returns_pct.rolling(20).std()

            if not volatility_rolling.empty:
                current_vol = volatility_rolling.iloc[-1]
                avg_vol = volatility_rolling.mean()

                if current_vol > avg_vol * 1.5:
                    regime_multiplier = 0.8  # Высокая волатильность - консервативно
                elif current_vol < avg_vol * 0.7:
                    regime_multiplier = 1.1  # Низкая волатильность - агрессивно
                else:
                    regime_multiplier = 1.0  # Нормальный режим
            else:
                regime_multiplier = 1.0

            return regime_multiplier

        except Exception as e:
            logger.error("Ошибка анализа рыночного режима: %s", e)
            return 1.0

    def _analyze_time_factors(self) -> float:
        """Учет временных факторов (время суток, дни недели)"""
        try:
            now = get_utc_now()
            hour = now.hour
            day_of_week = now.weekday()  # 0=понедельник, 6=воскресенье

            time_config = self.adaptive_config.get("time_factors", {})
            high_vol_hours = time_config.get("HIGH_VOLATILITY_HOURS", [9, 10, 16, 17])

            if hour in high_vol_hours:
                # Часы высокой волатильности - консервативный подход
                multiplier = time_config.get("high_vol_multiplier", 0.8)
            elif hour >= 22 or hour <= 4:
                # Ночные часы - низкая ликвидность, консервативно
                multiplier = 0.7
            else:
                # Нормальные часы - стандартный подход
                multiplier = time_config.get("low_vol_multiplier", 1.0)

            # Учет дня недели
            if day_of_week == 0:  # Понедельник
                multiplier *= 0.9  # Консервативнее в начале недели
            elif day_of_week >= 4:  # Четверг-пятница
                multiplier *= 1.1  # Агрессивнее в конце недели

            return multiplier

        except Exception as e:
            logger.error("Ошибка анализа временных факторов: %s", e)
            return 1.0

    def _combine_factors(
        self, volatility_ratio: float, trend_ratio: float, regime_ratio: float, time_ratio: float
    ) -> float:
        """Комбинирование всех факторов с весами"""
        # Веса факторов (можно настроить)
        weights = {
            "volatility": 0.40,  # Самый важный фактор
            "trend": 0.30,  # Сила тренда
            "regime": 0.20,  # Общий рыночный режим
            "time": 0.10,  # Временные факторы
        }

        combined_ratio = (
            volatility_ratio * weights["volatility"]
            + trend_ratio * weights["trend"]
            + regime_ratio * weights["regime"]
            + time_ratio * weights["time"]
        )

        # Нормализация к общему множителю
        total_weight = sum(weights.values())
        normalized_ratio = combined_ratio / total_weight

        return normalized_ratio

    def _apply_constraints(self, ratio: float, df: pd.DataFrame, current_price: float) -> float:
        """Применение ограничений к коэффициенту"""
        min_ratio = self.adaptive_config.get("min_ratio", 0.15)
        max_ratio = self.adaptive_config.get("max_ratio", 1.2)

        # Проверка безопасного расстояния через ATR
        try:
            high_low = df["high"] - df["low"]
            atr = high_low.rolling(14).mean().iloc[-1]

            # Если ATR очень большой, ограничиваем агрессивность
            atr_pct = atr / current_price if current_price > 0 else 0
            if atr_pct > 0.1:  # ATR > 10%
                ratio = min(ratio, 0.3)
        except (ValueError, TypeError, KeyError, IndexError, AttributeError) as e:
            logger.debug("Ошибка расчета ATR для trailing stop: %s", e)
            pass

        # Ограничение диапазона
        constrained_ratio = max(min_ratio, min(max_ratio, ratio))

        return constrained_ratio


class TrailingStopManager:
    """
    Управление трейлинг-стопами

    Функционал:
    - Отслеживание максимальной цены после входа
    - Автоматический перенос SL при росте прибыли
    - Адаптация расстояния по ATR
    - Учет рыночного режима
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.positions_tracking = {}

        # Загружаем конфиг
        if config is None:
            try:
                from config import ADAPTIVE_TRAILING_CONFIG

                self.config = {"ADAPTIVE_TRAILING_CONFIG": ADAPTIVE_TRAILING_CONFIG}
            except ImportError:
                self.config = {}
        else:
            self.config = config

        # Инициализируем продвинутый менеджер
        try:
            self.advanced_manager = AdvancedTrailingStopManager(self.config)
        except Exception as e:
            logger.warning("⚠️ Не удалось инициализировать AdvancedTrailingStopManager: %s", e)
            self.advanced_manager = None

        # Настройки
        self.settings = {
            "activation_min_profit_pct": 1.0,  # Активация при +1% прибыли
            "min_trail_distance_pct": 0.5,  # Минимальное расстояние 0.5%
            "use_atr_based": True,  # Использовать ATR
            "breakeven_offset_pct": 0.3,  # Безубыток + 0.3%
            "max_trail_distance_pct": 8.0,  # Максимум 8%
            # 🔧 НОВОЕ: Настройки подтягивания к TP1
            "tp1_trailing_enabled": True,  # Включить подтягивание к TP1
            "tp1_activation_progress": 0.5,  # Активация при 50% пути к TP1
            "tp1_sl_progress_ratio": 1.0,  # Подтягивать SL на такое же расстояние (100% от пройденного пути)
            "tp1_min_atr_multiplier": 2.0,  # Минимум ATR * 2.0 от текущей цены
        }

    def setup_position(
        self,
        symbol: str,
        entry_price: float,
        initial_sl: float,
        side: str = "LONG",
        tp1_price: Optional[float] = None,
        tp2_price: Optional[float] = None,
    ):
        """Инициализирует отслеживание позиции"""
        try:
            self.positions_tracking[symbol] = {
                "entry_price": entry_price,
                "highest_price": entry_price if side == "LONG" else entry_price,
                "lowest_price": entry_price if side == "SHORT" else entry_price,
                "current_stop": initial_sl,
                "initial_stop": initial_sl,
                "trailing_activated": False,
                "tp1_trailing_activated": False,
                "tp2_trailing_activated": False,  # 🆕 Флаг для TP2
                "tp1_price": tp1_price,
                "tp2_price": tp2_price,  # 🆕 Цена TP2
                "side": side,
                "last_update": time.time(),
                "stop_moves_count": 0,
                "tp1_trailing_moves_count": 0,
                "tp2_trailing_moves_count": 0,  # 🆕 Счетчик для TP2
            }

            logger.info(
                "🎯 [TRAILING] %s: позиция инициализирована (вход: %.4f, SL: %.4f, TP1: %s, сторона: %s)",
                symbol,
                entry_price,
                initial_sl,
                f"{tp1_price:.4f}" if tp1_price else "N/A",
                side,
            )

        except Exception as e:
            logger.error("❌ Ошибка инициализации trailing stop для %s: %s", symbol, e)

    def calculate_tp1_trailing_stop(
        self,
        symbol: str,
        current_price: float,
        atr_value: Optional[float] = None,
        df: Optional[pd.DataFrame] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        🔧 НОВОЕ: Подтягивание SL по мере движения к TP1 (консервативный вариант)

        Returns:
            Dict с новым SL или None если не нужно обновлять
        """
        try:
            if symbol not in self.positions_tracking:
                return None

            position = self.positions_tracking[symbol]

            # Проверяем, включено ли подтягивание к TP1
            if not self.settings["tp1_trailing_enabled"]:
                return None

            # Проверяем наличие TP1
            tp1_price = position.get("tp1_price")
            if not tp1_price:
                return None

            # Если уже достигли TP1, не подтягиваем
            side = position["side"]
            entry_price = position["entry_price"]
            current_stop = position["current_stop"]

            if side == "LONG":
                if current_price >= tp1_price:
                    return None  # Уже достигли TP1
                # Рассчитываем прогресс к TP1
                if tp1_price <= entry_price:
                    return None  # Некорректный TP1
                progress = (current_price - entry_price) / (tp1_price - entry_price)
            else:  # SHORT
                if current_price <= tp1_price:
                    return None  # Уже достигли TP1
                # Рассчитываем прогресс к TP1
                if tp1_price >= entry_price:
                    return None  # Некорректный TP1
                progress = (entry_price - current_price) / (entry_price - tp1_price)

            # Активация только при значительном прогрессе (50%+ пути к TP1)
            activation_progress = self.settings["tp1_activation_progress"]
            if progress < activation_progress:
                return None

            # 🆕 АДАПТИВНЫЙ РАСЧЕТ: Используем продвинутую логику если доступна
            if self.advanced_manager and df is not None:
                try:
                    adaptive_ratio = self.advanced_manager.get_adaptive_progress_ratio(
                        df, symbol, side, current_price
                    )
                    sl_progress_ratio = adaptive_ratio
                    logger.debug(
                        "🎯 [ADAPTIVE] %s: Использован адаптивный ratio=%.3f "
                        "(вместо статического %.3f)",
                        symbol,
                        adaptive_ratio,
                        self.settings["tp1_sl_progress_ratio"],
                    )
                except Exception as adaptive_err:
                    logger.debug("⚠️ [ADAPTIVE] Ошибка адаптивного расчета: %s", adaptive_err)
                    sl_progress_ratio = self.settings["tp1_sl_progress_ratio"]
            else:
                # Fallback на статический коэффициент
                sl_progress_ratio = self.settings["tp1_sl_progress_ratio"]

            # Рассчитываем новый SL
            sl_progress = progress * sl_progress_ratio

            if side == "LONG":
                # Подтягиваем SL пропорционально прогрессу
                new_sl = entry_price + (tp1_price - entry_price) * sl_progress

                # Минимум - безубыток с учетом комиссий (0.2%)
                breakeven = entry_price * 1.002
                new_sl = max(new_sl, breakeven)

                # Но не ближе чем ATR * multiplier от текущей цены
                if atr_value:
                    min_distance = atr_value * self.settings["tp1_min_atr_multiplier"]
                    min_sl = current_price - min_distance
                    new_sl = max(new_sl, min_sl)

                # Стоп только улучшается (только вверх)
                if new_sl <= current_stop:
                    return None
            else:  # SHORT
                # Подтягиваем SL пропорционально прогрессу
                new_sl = entry_price - (entry_price - tp1_price) * sl_progress

                # Минимум - безубыток с учетом комиссий (0.2%)
                breakeven = entry_price * 0.998
                new_sl = min(new_sl, breakeven)

                # 🔧 ИСПРАВЛЕНО: Для SHORT ограничиваем SL снизу (не ближе к цене), а не сверху
                # Это позволяет SL подтягиваться вниз (улучшаться), но не слишком близко к текущей цене
                if atr_value:
                    min_distance = atr_value * self.settings["tp1_min_atr_multiplier"]
                    min_sl = current_price + min_distance  # Минимальный SL (не ближе к цене)
                    new_sl = max(new_sl, min_sl)  # Ограничиваем снизу, чтобы не был слишком близко

                # Стоп только улучшается (только вниз, т.е. new_sl < current_stop)
                if new_sl >= current_stop:
                    return None

            # Обновляем позицию
            position["current_stop"] = new_sl
            position["last_update"] = time.time()
            position["tp1_trailing_activated"] = True
            position["tp1_trailing_moves_count"] = position.get("tp1_trailing_moves_count", 0) + 1

            logger.info(
                "🎯 [TP1_TRAILING] %s: SL подтянут к TP1 %.4f → %.4f (прогресс: %.1f%%, расстояние: %.2f%%)",
                symbol,
                current_stop,
                new_sl,
                progress * 100,
                abs((new_sl - current_price) / current_price * 100) if current_price > 0 else 0,
            )

            return {
                "new_stop": new_sl,
                "stop_moved": True,
                "progress_to_tp1": progress * 100,
                "reason": f"TP1 trailing: {progress * 100:.1f}% progress",
                "tp1_trailing_moves_count": position["tp1_trailing_moves_count"],
            }

        except Exception as e:
            logger.error("❌ Ошибка расчета TP1 trailing stop для %s: %s", symbol, e)
            return None

    def calculate_tp2_trailing_stop(
        self,
        symbol: str,
        current_price: float,
        atr_value: Optional[float] = None,
        df: Optional[pd.DataFrame] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        🆕 Подтягивание SL по мере движения от TP1 к TP2
        """
        try:
            if symbol not in self.positions_tracking:
                return None

            position = self.positions_tracking[symbol]
            tp1_price = position.get("tp1_price")
            tp2_price = position.get("tp2_price")

            if not tp1_price or not tp2_price:
                return None

            side = position["side"]
            current_stop = position["current_stop"]

            # Проверяем, прошли ли мы TP1
            is_past_tp1 = False
            if side == "LONG":
                is_past_tp1 = current_price >= tp1_price
            else:
                is_past_tp1 = current_price <= tp1_price

            if not is_past_tp1:
                return None

            # Рассчитываем прогресс от TP1 к TP2
            if side == "LONG":
                if tp2_price <= tp1_price:
                    return None
                if current_price >= tp2_price:
                    return None
                progress = (current_price - tp1_price) / (tp2_price - tp1_price)
            else:
                if tp2_price >= tp1_price:
                    return None
                if current_price <= tp2_price:
                    return None
                progress = (tp1_price - current_price) / (tp1_price - tp2_price)

            # Адаптивный расчет для TP2
            sl_progress_ratio = self.settings.get("tp1_sl_progress_ratio", 0.7)
            if self.advanced_manager and df is not None:
                try:
                    adaptive_ratio = self.advanced_manager.get_adaptive_progress_ratio(
                        df, symbol, side, current_price
                    )
                    sl_progress_ratio = adaptive_ratio
                except (ValueError, TypeError, AttributeError, RuntimeError) as e:
                    logger.debug("Ошибка получения адаптивного ratio для trailing stop: %s", e)
                    pass

            sl_progress = progress * sl_progress_ratio

            if side == "LONG":
                # Подтягиваем SL от TP1 к TP2
                new_sl = tp1_price + (tp2_price - tp1_price) * sl_progress
                if new_sl <= current_stop:
                    return None
            else:
                new_sl = tp1_price - (tp1_price - tp2_price) * sl_progress
                if new_sl >= current_stop:
                    return None

            # Обновляем
            position["current_stop"] = new_sl
            position["tp2_trailing_activated"] = True
            position["tp2_trailing_moves_count"] = position.get("tp2_trailing_moves_count", 0) + 1

            logger.info(
                "🎯 [TP2_TRAILING] %s: SL подтянут к TP2 %.4f → %.4f (прогресс: %.1f%%)",
                symbol,
                current_stop,
                new_sl,
                progress * 100,
            )

            return {
                "new_stop": new_sl,
                "stop_moved": True,
                "progress_to_tp2": progress * 100,
                "reason": f"TP2 trailing: {progress * 100:.1f}% progress",
            }
        except Exception as e:
            logger.error("❌ Ошибка расчета TP2 trailing stop для %s: %s", symbol, e)
            return None

    def update_trailing_stop(
        self,
        symbol: str,
        current_price: float,
        atr_value: Optional[float] = None,
        regime: str = "NEUTRAL",
        df: Optional[pd.DataFrame] = None,
    ) -> Dict[str, Any]:
        """
        Обновляет трейлинг стоп

        Returns:
            {
                'new_stop': float,
                'stop_moved': bool,
                'profit_pct': float,
                'reason': str
            }
        """
        try:
            if symbol not in self.positions_tracking:
                return {
                    "new_stop": None,
                    "stop_moved": False,
                    "profit_pct": 0.0,
                    "reason": "Position not tracked",
                }

            position = self.positions_tracking[symbol]
            side = position["side"]
            entry_price = position["entry_price"]
            current_stop = position["current_stop"]

            # Рассчитываем текущую прибыль
            if side == "LONG":
                profit_pct = ((current_price - entry_price) / entry_price) * 100

                # Обновляем максимальную цену
                if current_price > position["highest_price"]:
                    position["highest_price"] = current_price
            else:  # SHORT
                profit_pct = ((entry_price - current_price) / entry_price) * 100

                # Обновляем минимальную цену
                if current_price < position["lowest_price"]:
                    position["lowest_price"] = current_price

            # 🔧 НОВОЕ: Сначала проверяем подтягивание к TP1 (приоритет)
            if self.settings["tp1_trailing_enabled"] and position.get("tp1_price"):
                # Если мы еще не дошли до TP1, используем логику TP1
                # Если дошли - логика TP2 (внутри функции есть проверка)
                tp1_result = self.calculate_tp1_trailing_stop(symbol, current_price, atr_value, df)
                if tp1_result and tp1_result.get("stop_moved"):
                    return tp1_result

                # 🆕 Логика подтягивания от TP1 к TP2
                tp2_result = self.calculate_tp2_trailing_stop(symbol, current_price, atr_value, df)
                if tp2_result and tp2_result.get("stop_moved"):
                    return tp2_result

            # Проверяем активацию трейлинга
            if not position["trailing_activated"]:
                if profit_pct >= self.settings["activation_min_profit_pct"]:
                    position["trailing_activated"] = True
                    logger.info(
                        "✅ [TRAILING] %s: трейлинг активирован при прибыли %.2f%%",
                        symbol,
                        profit_pct,
                    )
                else:
                    return {
                        "new_stop": current_stop,
                        "stop_moved": False,
                        "profit_pct": profit_pct,
                        "reason": f"Waiting for {self.settings['activation_min_profit_pct']}% profit",
                    }

            # Рассчитываем новый стоп
            if position["trailing_activated"]:
                # Определяем расстояние для стопа
                if self.settings["use_atr_based"] and atr_value:
                    # Используем ATR
                    atr_distance_pct = (atr_value / current_price) * 100

                    # Адаптируем по режиму
                    if regime == "HIGH_VOL_RANGE":
                        trail_distance_pct = min(
                            atr_distance_pct * 2.0, self.settings["max_trail_distance_pct"]
                        )
                    elif regime == "BULL_TREND":
                        trail_distance_pct = max(
                            atr_distance_pct * 1.0, self.settings["min_trail_distance_pct"]
                        )
                    else:
                        trail_distance_pct = min(
                            atr_distance_pct * 1.5, self.settings["max_trail_distance_pct"]
                        )
                else:
                    # Фиксированное расстояние
                    trail_distance_pct = self.settings["min_trail_distance_pct"]

                # Рассчитываем новый стоп
                if side == "LONG":
                    new_stop = position["highest_price"] * (1 - trail_distance_pct / 100)

                    # Минимум - безубыток + offset
                    breakeven_stop = entry_price * (1 + self.settings["breakeven_offset_pct"] / 100)
                    new_stop = max(new_stop, breakeven_stop)
                else:  # SHORT
                    new_stop = position["lowest_price"] * (1 + trail_distance_pct / 100)

                    # Минимум - безубыток - offset
                    breakeven_stop = entry_price * (1 - self.settings["breakeven_offset_pct"] / 100)
                    new_stop = min(new_stop, breakeven_stop)

                # Стоп только улучшается, никогда не ухудшается
                stop_improved = False
                if side == "LONG":
                    if new_stop > current_stop:
                        stop_improved = True
                else:  # SHORT
                    if new_stop < current_stop:
                        stop_improved = True

                if stop_improved:
                    position["current_stop"] = new_stop
                    position["last_update"] = time.time()
                    position["stop_moves_count"] += 1

                    logger.info(
                        "🎯 [TRAILING] %s: SL перемещен %.4f → %.4f (прибыль: %.2f%%, расстояние: %.2f%%)",
                        symbol,
                        current_stop,
                        new_stop,
                        profit_pct,
                        trail_distance_pct,
                    )

                    return {
                        "new_stop": new_stop,
                        "stop_moved": True,
                        "profit_pct": profit_pct,
                        "reason": f"Trail distance: {trail_distance_pct:.2f}%",
                        "stop_moves_count": position["stop_moves_count"],
                    }

            return {
                "new_stop": current_stop,
                "stop_moved": False,
                "profit_pct": profit_pct,
                "reason": "No update needed",
            }

        except Exception as e:
            logger.error("❌ Ошибка обновления trailing stop для %s: %s", symbol, e)
            return {
                "new_stop": None,
                "stop_moved": False,
                "profit_pct": 0.0,
                "reason": f"Error: {e}",
            }

    def remove_position(self, symbol: str):
        """Удаляет позицию из отслеживания"""
        if symbol in self.positions_tracking:
            del self.positions_tracking[symbol]
            logger.info("🗑️ [TRAILING] %s: позиция удалена из отслеживания", symbol)

    def get_position_info(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Получает информацию о позиции"""
        return self.positions_tracking.get(symbol)

    def get_statistics(self) -> Dict[str, Any]:
        """Статистика по трейлинг-стопам"""
        total_positions = len(self.positions_tracking)
        active_trailing = sum(
            1 for p in self.positions_tracking.values() if p["trailing_activated"]
        )
        total_moves = sum(p["stop_moves_count"] for p in self.positions_tracking.values())

        return {
            "total_positions": total_positions,
            "active_trailing": active_trailing,
            "total_stop_moves": total_moves,
            "avg_moves_per_position": total_moves / total_positions if total_positions > 0 else 0,
        }


# Глобальный экземпляр
_TRAILING_MANAGER = None


def get_trailing_manager() -> TrailingStopManager:
    """Получение глобального экземпляра"""
    global _TRAILING_MANAGER
    if _TRAILING_MANAGER is None:
        # Загружаем конфиг для адаптивной системы
        try:
            from config import ADAPTIVE_TRAILING_CONFIG

            config = {"ADAPTIVE_TRAILING_CONFIG": ADAPTIVE_TRAILING_CONFIG}
        except ImportError:
            config = {}

        _TRAILING_MANAGER = TrailingStopManager(config=config)
        logger.info("✅ TrailingStopManager инициализирован с адаптивной системой")
    return _TRAILING_MANAGER

"""
Unified Leverage Manager - Единая система расчета плеча
"""

import logging
from typing import Tuple, Optional, Dict, Any
from decimal import Decimal
import pandas as pd
import ta
from ..core.config import MAX_LEVERAGE, DEFAULT_LEVERAGE

logger = logging.getLogger(__name__)


class LeverageManager:
    """
    Единый менеджер расчета динамического плеча с поддержкой высокой точности (Decimal)
    """

    def __init__(self):
        self.cache: Dict[str, Any] = {}
        self.cache_ttl = 300  # 5 минут

    def calculate_dynamic_leverage(
        self,
        df: pd.DataFrame,
        i: int,
        base_leverage: Optional[float] = None,
        market_condition: str = "normal"
    ) -> float:
        """
        Расчет динамического плеча на основе всех факторов

        Args:
            df: DataFrame с данными
            i: Индекс текущего бара
            base_leverage: Базовое плечо
            market_condition: Условия рынка

        Returns:
            float: Динамическое плечо
        """
        # Конвертация в Decimal для точности
        if base_leverage is None:
            base_lev_dec = Decimal(str(DEFAULT_LEVERAGE))
        else:
            base_lev_dec = Decimal(str(base_leverage))

        if i < 50:  # Недостаточно данных
            return float(base_lev_dec)

        try:
            # Расчет всех факторов (все возвращают Decimal)
            trend_factor = Decimal(str(self._calculate_trend_factor(df, i)))
            volatility_factor = Decimal(str(self._calculate_volatility_factor(df, i)))
            volume_factor = Decimal(str(self._calculate_volume_factor(df, i)))
            market_condition_factor = Decimal(str(self._get_market_condition_factor(market_condition)))

            # Комбинированный фактор
            combined_factor = (
                trend_factor * Decimal("0.4") +
                volatility_factor * Decimal("0.3") +
                volume_factor * Decimal("0.2") +
                market_condition_factor * Decimal("0.1")
            )

            # Применение фактора к базовому плечу
            dynamic_leverage = base_lev_dec * combined_factor

            # Ограничения
            max_leverage_dec = Decimal(str(MAX_LEVERAGE))
            dynamic_leverage = min(dynamic_leverage, max_leverage_dec)
            dynamic_leverage = max(dynamic_leverage, Decimal("1.0"))

            return float(round(dynamic_leverage, 2))

        except Exception as e:
            logger.error("Ошибка расчета динамического плеча: %s", e, exc_info=True)
            return float(base_lev_dec)

    def _calculate_trend_factor(self, df: pd.DataFrame, i: int) -> float:
        """
        Расчет фактора тренда
        """
        try:
            # Используем несколько EMA для определения силы тренда
            ema_short = ta.trend.EMAIndicator(df["close"], window=7).ema_indicator()
            ema_medium = ta.trend.EMAIndicator(df["close"], window=25).ema_indicator()
            ema_long = ta.trend.EMAIndicator(df["close"], window=50).ema_indicator()

            if i < len(ema_short) and i < len(ema_medium) and i < len(ema_long):
                short_val = Decimal(str(ema_short.iloc[i]))
                medium_val = Decimal(str(ema_medium.iloc[i]))
                long_val = Decimal(str(ema_long.iloc[i]))

                # Расчет силы тренда
                short_trend = (short_val - medium_val) / medium_val * Decimal("100")
                medium_trend = (medium_val - long_val) / long_val * Decimal("100")

                # Комбинированная сила тренда
                trend_strength = short_trend * Decimal("0.6") + medium_trend * Decimal("0.4")

                # Фактор тренда: выше тренд = выше плечо
                if trend_strength > Decimal("2.0"):
                    return 1.5  # Сильный восходящий тренд
                if trend_strength > Decimal("1.0"):
                    return 1.3  # Умеренный восходящий тренд
                if trend_strength < Decimal("-2.0"):
                    return 0.7  # Сильный нисходящий тренд
                if trend_strength < Decimal("-1.0"):
                    return 0.8  # Умеренный нисходящий тренд
                return 1.0  # Боковой тренд

        except Exception as e:
            logger.error("Ошибка расчета фактора тренда: %s", e, exc_info=True)

        return 1.0

    def _calculate_volatility_factor(self, df: pd.DataFrame, i: int) -> float:
        """
        Расчет фактора волатильности
        """
        try:
            # Используем ATR для измерения волатильности
            atr = ta.volatility.AverageTrueRange(
                high=df["high"], low=df["low"], close=df["close"], window=14
            ).average_true_range()

            if i < len(atr):
                atr_val = Decimal(str(atr.iloc[i]))
                current_price = Decimal(str(df["close"].iloc[i]))

                if not pd.isna(atr_val) and current_price > Decimal("0"):
                    atr_pct = (atr_val / current_price) * Decimal("100")

                    # Фактор волатильности: выше волатильность = ниже плечо
                    if atr_pct > Decimal("4.0"):
                        return 0.6  # Очень высокая волатильность
                    if atr_pct > Decimal("3.0"):
                        return 0.7  # Высокая волатильность
                    if atr_pct > Decimal("2.0"):
                        return 0.8  # Средняя волатильность
                    if atr_pct < Decimal("1.0"):
                        return 1.2  # Низкая волатильность
                    return 1.0  # Нормальная волатильность

        except Exception as e:
            logger.error("Ошибка расчета фактора волатильности: %s", e, exc_info=True)

        return 1.0

    def _calculate_volume_factor(self, df: pd.DataFrame, i: int) -> float:
        """
        Расчет фактора объема
        """
        try:
            if "volume" not in df.columns or i < 20:
                return 1.0

            # Расчет среднего объема
            current_volume = Decimal(str(df["volume"].iloc[i]))
            avg_volume = Decimal(str(df["volume"].iloc[i-20:i].mean()))

            if avg_volume > Decimal("0"):
                volume_ratio = current_volume / avg_volume

                # Фактор объема: выше объем = выше плечо
                if volume_ratio > Decimal("3.0"):
                    return 1.3  # Очень высокий объем
                if volume_ratio > Decimal("2.0"):
                    return 1.2  # Высокий объем
                if volume_ratio > Decimal("1.5"):
                    return 1.1  # Повышенный объем
                if volume_ratio < Decimal("0.5"):
                    return 0.9  # Низкий объем
                return 1.0  # Нормальный объем

        except Exception as e:
            logger.error("Ошибка расчета фактора объема: %s", e, exc_info=True)

        return 1.0

    def _get_market_condition_factor(self, market_condition: str) -> float:
        """
        Получение фактора рыночных условий
        """
        factors = {
            "bull": 1.2,      # Бычий рынок - выше плечо
            "bear": 0.8,      # Медвежий рынок - ниже плечо
            "volatile": 0.7,  # Волатильный рынок - ниже плечо
            "sideways": 1.0,  # Боковой рынок - нормальное плечо
            "normal": 1.0     # Нормальный рынок - нормальное плечо
        }

        return factors.get(market_condition.lower(), 1.0)

    def calculate_risk_based_leverage(
        self,
        risk_pct: float,
        distance_pct: float,
        current_price: float
    ) -> float:
        """
        Расчет плеча на основе риска и дистанции до стоп-лосса (Decimal precision)

        Args:
            risk_pct: Процент риска
            distance_pct: Процент дистанции до SL
            current_price: Текущая цена

        Returns:
            float: Рекомендуемое плечо
        """
        try:
            risk_pct_dec = Decimal(str(risk_pct))
            dist_pct_dec = Decimal(str(distance_pct))
            price_dec = Decimal(str(current_price))

            if dist_pct_dec <= Decimal("0"):
                return 1.0

            # Расчет позиции на основе риска
            position_size_usdt = Decimal("1000")  # Пример депозита
            risk_amount = position_size_usdt * (risk_pct_dec / Decimal("100"))

            # Размер позиции в монетах
            # position_size_coins = risk_amount / (price * distance_pct / 100)
            position_size_coins = risk_amount / (price_dec * dist_pct_dec / Decimal("100"))

            # Размер позиции в USDT
            position_value = position_size_coins * price_dec

            # Необходимое плечо
            leverage = position_value / position_size_usdt

            # Ограничения
            max_leverage_dec = Decimal(str(MAX_LEVERAGE))
            return float(min(leverage, max_leverage_dec))

        except Exception as e:
            logger.error("Ошибка расчета плеча на основе риска: %s", e, exc_info=True)
            return 1.0

    def get_leverage_smoothing(
        self,
        current_leverage: float,
        previous_leverage: Optional[float],
        smoothing_factor: float = 0.3
    ) -> float:
        """
        Сглаживание изменения плеча

        Args:
            current_leverage: Текущее рассчитанное плечо
            previous_leverage: Предыдущее плечо
            smoothing_factor: Фактор сглаживания (0-1)

        Returns:
            float: Сглаженное плечо
        """
        try:
            if previous_leverage is None:
                return float(round(Decimal(str(current_leverage)), 2))

            curr_dec = Decimal(str(current_leverage))
            prev_dec = Decimal(str(previous_leverage))
            smooth_dec = Decimal(str(smoothing_factor))

            # Экспоненциальное сглаживание: prev * (1 - alpha) + curr * alpha
            smoothed = prev_dec * (Decimal("1.0") - smooth_dec) + curr_dec * smooth_dec

            return float(round(smoothed, 2))

        except Exception as e:
            logger.error("Ошибка сглаживания плеча: %s", e, exc_info=True)
            return current_leverage

    def get_adaptive_leverage_limits(
        self,
        market_condition: str,
        volatility_pct: float
    ) -> Tuple[float, float]:
        """
        Получение адаптивных лимитов плеча (Decimal precision)
        """
        vol_pct_dec = Decimal(str(volatility_pct))
        base_min = Decimal("1.0")
        base_max = Decimal(str(MAX_LEVERAGE))

        # Корректировка на основе волатильности
        if vol_pct_dec > Decimal("4.0"):
            max_limit = min(base_max * Decimal("0.5"), Decimal("5.0"))
        elif vol_pct_dec > Decimal("3.0"):
            max_limit = min(base_max * Decimal("0.7"), Decimal("10.0"))
        elif vol_pct_dec < Decimal("1.0"):
            max_limit = min(base_max * Decimal("1.2"), base_max)
        else:
            max_limit = base_max

        # Корректировка на основе рыночных условий
        if market_condition == "volatile":
            max_limit = min(max_limit, Decimal("8.0"))
        elif market_condition == "bull":
            max_limit = min(max_limit * Decimal("1.1"), base_max)

        return float(base_min), float(max_limit)


# Глобальный экземпляр менеджера плеча
leverage_manager = LeverageManager()


# Обратная совместимость
def get_dynamic_leverage(df: pd.DataFrame, i: int, base_leverage: float = None) -> float:
    return leverage_manager.calculate_dynamic_leverage(df, i, base_leverage)


def calculate_leverage_smoothing(current: float, previous: float, factor: float = 0.3) -> float:
    return leverage_manager.get_leverage_smoothing(current, previous, factor)


def get_adaptive_leverage_limits(market_condition: str, volatility_pct: float) -> Tuple[float, float]:
    return leverage_manager.get_adaptive_leverage_limits(market_condition, volatility_pct)


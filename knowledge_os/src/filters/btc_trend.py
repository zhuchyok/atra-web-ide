"""
Фильтры BTC тренда для торговых сигналов
"""

import logging
from typing import Optional, Tuple, Dict, Any
import pandas as pd
import ta
from .base import BaseFilter, FilterResult

logger = logging.getLogger(__name__)


class BTCTrendFilter(BaseFilter):
    """Фильтр тренда BTC"""

    def __init__(self, enabled: bool = True):
        super().__init__("btc_trend", enabled, priority=1)

    async def filter_signal(self, signal_data: Dict[str, Any]) -> FilterResult:
        """Фильтрация сигнала на основе тренда BTC"""
        try:
            symbol = signal_data.get('symbol', '')
            direction = signal_data.get('direction', 'BUY')

            # Используем существующую логику из src.signals.filters
            from src.signals.filters import check_btc_alignment

            passed = await check_btc_alignment(symbol, direction)

            if passed:
                return FilterResult(True, "Тренд BTC благоприятный")
            else:
                return FilterResult(False, "Тренд BTC неблагоприятный")

        except Exception as e:
            logger.error("Ошибка в BTCTrendFilter: %s", e)
            return FilterResult(True, f"Ошибка проверки тренда BTC (пропущено): {e}")


def get_btc_trend_status() -> bool:
    """
    Получение статуса BTC тренда
    
    Returns:
        bool: True если тренд благоприятный для торговли
    """
    try:
        # Fallback реализация - всегда True
        return True
    except Exception as e:
        logger.error("Ошибка получения статуса BTC тренда: %s", e)
        return True


def bollinger_direction_filter(
    df: pd.DataFrame,
    i: int,
    near_mid_band_epsilon: Optional[float] = None,
    slope_lookback: Optional[int] = None,
    adx_threshold: Optional[float] = None,
    use_ema50_slope: Optional[bool] = None,
    atr_buffer_frac: Optional[float] = None,
) -> Tuple[bool, bool]:
    """Гейт направления у средней полосы Боллинджера.

    Возвращает кортеж (long_ok, short_ok), где признаки True означают,
    что условия по положению относительно средней полосы и наклонам
    (BB mid/EMA50) не противоречат соответствующему направлению.
    """
    try:
        # Используем константы вместо globals() для лучшей производительности
        eps = float(
            near_mid_band_epsilon
            if near_mid_band_epsilon is not None
            else 0.11  # BB_DIR_NEAR_MID_EPSILON_SOFT
        )
        k = int(
            slope_lookback
            if slope_lookback is not None
            else 4  # BB_DIR_SLOPE_LOOKBACK
        )
        adx_thr = float(
            adx_threshold
            if adx_threshold is not None
            else 20.0  # BB_DIR_ADX_THRESHOLD_SOFT
        )
        use_e50 = bool(
            use_ema50_slope
            if use_ema50_slope is not None
            else True  # BB_DIR_USE_EMA50_SLOPE
        )

        if i < max(2, k):
            return True, True

        close = df["close"].astype(float)
        bb = ta.volatility.BollingerBands(close, window=20, window_dev=2.0)
        bb_up = bb.bollinger_hband().ffill()
        bb_lo = bb.bollinger_lband().ffill()
        bb_md = bb.bollinger_mavg().ffill()

        # %B позиция относительно полос
        rng = float(bb_up.iloc[i] - bb_lo.iloc[i])
        if rng == 0:
            return True, True
        pb = float((close.iloc[i] - bb_lo.iloc[i]) / max(rng, 1e-9))

        # Наклоны средней BB и EMA50
        def slope(series: pd.Series, back: int) -> float:
            """Calculate slope of series over back periods."""
            try:
                return float(series.iloc[i] - series.iloc[i - back]) / max(
                    1e-9,
                    abs(float(series.iloc[i - back])),
                )
            except (ValueError, TypeError, KeyError, IndexError, ZeroDivisionError):
                return 0.0

        bb_md_slope = slope(bb_md, k)
        ema50 = ta.trend.EMAIndicator(close, window=50).ema_indicator()
        ema50_slope = slope(ema50, k)

        # ADX как прокси силы тренда
        adx_ok = True
        if {"high", "low", "close"}.issubset(set(df.columns)):
            try:
                adx_val = ta.trend.ADXIndicator(df["high"], df["low"], df["close"]).adx().iloc[i]
                adx_ok = True if pd.isna(adx_val) else (float(adx_val) >= adx_thr)
            except (ValueError, KeyError, TypeError, ZeroDivisionError, IndexError):
                adx_ok = True

        # Условия по положению относительно средней полосы
        near_long_ok = pb >= (0.5 + eps)
        near_short_ok = pb <= (0.5 - eps)

        # Направление по наклонам
        dir_long_ok = (bb_md_slope >= 0.0) and (ema50_slope >= 0.0 if use_e50 else True)
        dir_short_ok = (bb_md_slope <= 0.0) and (ema50_slope <= 0.0 if use_e50 else True)

        long_ok = bool(near_long_ok and dir_long_ok and adx_ok)
        short_ok = bool(near_short_ok and dir_short_ok and adx_ok)
        return long_ok, short_ok
    except (ValueError, TypeError, KeyError, IndexError, ZeroDivisionError, AttributeError) as e:
        # В случае любых ошибок не блокируем направление
        logger.debug("Ошибка в bollinger_direction_filter: %s", e)
        return True, True

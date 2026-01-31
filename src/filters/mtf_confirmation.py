#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Модуль для Multi-Timeframe подтверждения сигналов
"""

import logging
from copy import deepcopy
from typing import Optional, Tuple

import pandas as pd

try:
    from exchange_api import get_ohlc_with_fallback
except ImportError:  # pragma: no cover - модуль может отсутствовать в окружении
    get_ohlc_with_fallback = None  # type: ignore

logger = logging.getLogger(__name__)

BASE_THRESHOLDS = {
    'ema_gap': 0.0008,       # 0.08 %
    'ema_slope': 0.00025,    # 0.025 % за бар
    'volume_ratio': 0.95,    # допускаем небольшое снижение объёма
    'macd_power': 0.0,       # MACD должен быть >= 0 для лонга, <= 0 для шорта
}


def adjust_mtf_thresholds(market_regime: str, direction: str, base_thresholds: dict) -> dict:
    """Масштабирует пороговые величины под рыночный режим и направление сделки."""
    adjustments = {
        'BEAR': {
            'SHORT': {'ema_slope': 0.65, 'ema_gap': 1.35, 'volume_ratio': 0.85, 'macd_power': 0.8},
            'LONG': {'ema_slope': 1.3, 'ema_gap': 0.7, 'volume_ratio': 1.25, 'macd_power': 1.2},
        },
        'BULL': {
            'LONG': {'ema_slope': 0.65, 'ema_gap': 1.35, 'volume_ratio': 0.85, 'macd_power': 0.8},
            'SHORT': {'ema_slope': 1.3, 'ema_gap': 0.7, 'volume_ratio': 1.25, 'macd_power': 1.2},
        },
    }

    regime_adj = adjustments.get(market_regime, {}).get(direction, {})
    adjusted = deepcopy(base_thresholds)
    for key, multiplier in regime_adj.items():
        adjusted[key] = adjusted.get(key, 1.0) * multiplier
    return adjusted


def calculate_base_mtf_score(
    direction: str,
    metrics: dict,
    thresholds: dict,
) -> float:
    """Собирает базовый скоринг MTF подтверждения на основе EMA, MACD и объёма."""
    score = 0.0

    ema_gap = metrics['ema_gap']
    fast_slope = metrics['fast_slope']
    slow_slope = metrics['slow_slope']
    macd_value = metrics['macd']
    volume_ratio = metrics['volume_ratio']
    price_above = metrics['price_above']
    price_below = metrics['price_below']

    if direction in ('LONG', 'BUY'):
        if price_above:
            score += 0.20
        if ema_gap >= -thresholds['ema_gap']:
            score += 0.30
        if fast_slope >= -thresholds['ema_slope'] and slow_slope >= -thresholds['ema_slope']:
            score += 0.20
        if macd_value >= thresholds['macd_power']:
            score += 0.20
        if volume_ratio >= thresholds['volume_ratio']:
            score += 0.10
        if abs(ema_gap) <= thresholds['ema_gap'] * 1.5 and macd_value >= thresholds['macd_power'] - 0.05:
            score += 0.10  # near-crossover
    else:
        if price_below:
            score += 0.20
        if ema_gap <= thresholds['ema_gap']:
            score += 0.30
        if fast_slope <= thresholds['ema_slope'] and slow_slope <= thresholds['ema_slope']:
            score += 0.20
        if macd_value <= -thresholds['macd_power']:
            score += 0.20
        if volume_ratio >= thresholds['volume_ratio']:
            score += 0.10
        if abs(ema_gap) <= thresholds['ema_gap'] * 1.5 and macd_value <= thresholds['macd_power'] + 0.05:
            score += 0.10

    return score - 0.45  # приводим к диапазону (-0.45; 0.55)


def apply_hysteresis_bonus(
    base_score: float,
    market_regime: str,
    direction: str,
) -> Tuple[float, bool]:
    """Добавляет бонус за совпадение направления сигнала с текущим рыночным режимом."""
    regime = market_regime.upper()
    direction_upper = direction.upper()

    alignment_bonus = 0.0
    aligned = (regime == 'BEAR' and direction_upper in ('SHORT', 'SELL')) or (
        regime == 'BULL' and direction_upper in ('LONG', 'BUY')
    )
    if aligned:
        alignment_bonus = 0.25
    elif regime in ('RANGE', 'LOW_VOL_RANGE', 'NEUTRAL'):
        alignment_bonus = 0.12

    return base_score + alignment_bonus, aligned


async def check_mtf_confirmation(
    symbol: str,
    direction: str,
    timeframe: str = '4h',
    regime_data: Optional[dict] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Проверяет подтверждение сигнала на более высоком таймфрейме (H4)

    Args:
        symbol: Торговая пара
        direction: Направление сигнала ('LONG' или 'SHORT')
        timeframe: Таймфрейм для проверки (по умолчанию '4h')

    Returns:
        Tuple[bool, Optional[str]]: (подтвержден ли сигнал, сообщение об ошибке)
    """
    try:
        if get_ohlc_with_fallback is None:
            return False, "exchange_api недоступен"

        # Получаем OHLC данные на H4
        h4_data = await get_ohlc_with_fallback(symbol, interval=timeframe, limit=50)

        if not h4_data or len(h4_data) < 20:
            return False, f"Недостаточно данных H4 для {symbol}"

        df = pd.DataFrame(h4_data)
        current_index = len(df) - 1

        # Рассчитываем EMA на H4 для определения тренда
        ema_fast = df['close'].ewm(span=12, adjust=False).mean()
        ema_slow = df['close'].ewm(span=26, adjust=False).mean()

        current_ema_fast = float(ema_fast.iloc[current_index])
        current_ema_slow = float(ema_slow.iloc[current_index])
        prev_ema_fast = float(ema_fast.iloc[current_index - 1])
        prev_ema_slow = float(ema_slow.iloc[current_index - 1])

        fast_slope = current_ema_fast - prev_ema_fast
        slow_slope = current_ema_slow - prev_ema_slow
        ema_gap_ratio = (
            (current_ema_fast - current_ema_slow) / current_ema_slow
            if current_ema_slow
            else 0.0
        )

        # Рассчитываем MACD для дополнительного подтверждения
        try:
            macd_fast = df['close'].ewm(span=12, adjust=False).mean()
            macd_slow = df['close'].ewm(span=26, adjust=False).mean()
            macd = macd_fast - macd_slow
            macd_signal = macd.ewm(span=9, adjust=False).mean()
            macd_hist = macd - macd_signal
            macd_value = float(macd_hist.iloc[current_index])
        except Exception:
            macd_value = 0.0

        close_price = float(df['close'].iloc[current_index])
        price_change = df['close'].pct_change().rolling(window=12, min_periods=5).std()
        volatility_valid = not price_change.isna().iloc[current_index]
        recent_volatility = float(price_change.iloc[current_index]) if volatility_valid else None
        low_vol = recent_volatility is not None and recent_volatility < 0.007  # <0.7% среднеквадратичное
        high_vol = recent_volatility is not None and recent_volatility > 0.015

        regime_from_context = (regime_data or {}).get('regime', 'UNKNOWN')
        regime_from_context = (regime_from_context or 'UNKNOWN').upper()

        direction_upper = direction.upper()
        confirmed = False
        trend_status = "нейтральный"

        rolling_volume = (
            df['volume'].rolling(window=20, min_periods=5).mean().iloc[current_index]
            if 'volume' in df
            else None
        )
        volume_ratio = (
            float(df['volume'].iloc[current_index] / rolling_volume)
            if rolling_volume and rolling_volume > 0
            else 1.0
        )

        thresholds = adjust_mtf_thresholds(regime_from_context, direction_upper, BASE_THRESHOLDS)

        if low_vol:
            thresholds['ema_gap'] *= 1.4
            thresholds['ema_slope'] *= 0.6
            thresholds['volume_ratio'] *= 0.9
        if high_vol:
            thresholds['ema_gap'] *= 0.8
            thresholds['ema_slope'] *= 1.35
            thresholds['volume_ratio'] *= 1.1

        metrics = {
            'ema_gap': ema_gap_ratio,
            'fast_slope': fast_slope,
            'slow_slope': slow_slope,
            'macd': macd_value,
            'volume_ratio': volume_ratio,
            'price_above': close_price >= current_ema_fast and close_price >= current_ema_slow,
            'price_below': close_price <= current_ema_fast and close_price <= current_ema_slow,
        }

        base_score = calculate_base_mtf_score(direction_upper, metrics, thresholds)
        final_score, aligned_with_regime = apply_hysteresis_bonus(base_score, regime_from_context, direction_upper)

        regime_thresholds = {
            ('BULL_TREND', 'LONG'): -0.12,
            ('BULL_TREND', 'BUY'): -0.12,
            ('BULL_TREND', 'SHORT'): -0.04,
            ('BULL_TREND', 'SELL'): -0.04,
            ('BEAR_TREND', 'SHORT'): -0.28,
            ('BEAR_TREND', 'SELL'): -0.28,
            ('BEAR_TREND', 'LONG'): -0.06,
            ('BEAR_TREND', 'BUY'): -0.06,
            ('LOW_VOL_RANGE', 'LONG'): -0.10,
            ('LOW_VOL_RANGE', 'BUY'): -0.10,
            ('LOW_VOL_RANGE', 'SHORT'): -0.16,
            ('LOW_VOL_RANGE', 'SELL'): -0.16,
        }
        base_threshold = -0.18
        threshold = regime_thresholds.get((regime_from_context, direction_upper), base_threshold)

        if direction_upper in ('LONG', 'BUY'):
            confirmed = final_score >= threshold
            trend_status = "бычий" if confirmed else "не подтверждён (EMA/MACD)"
            if not confirmed and ema_gap_ratio < -thresholds['ema_gap'] and fast_slope < -thresholds['ema_slope']:
                trend_status = "медвежий"
            if (
                not confirmed
                and regime_from_context in ('BULL_TREND', 'LOW_VOL_RANGE')
                and metrics['price_above']
                and macd_value >= thresholds['macd_power'] - 0.08
            ):
                confirmed = final_score >= (threshold - 0.05)
                if confirmed:
                    trend_status = "бычий (режимное послабление)"
            if not confirmed and aligned_with_regime and metrics['price_above']:
                confirmed = final_score >= (threshold - 0.10)
                if confirmed:
                    trend_status = "бычий (гистерезис)"
        elif direction_upper in ('SHORT', 'SELL'):
            confirmed = final_score >= threshold
            trend_status = "медвежий" if confirmed else "не подтверждён (EMA/MACD)"
            if not confirmed and ema_gap_ratio > thresholds['ema_gap'] and fast_slope > thresholds['ema_slope']:
                trend_status = "бычий"
            if (
                not confirmed
                and regime_from_context in ('BEAR_TREND', 'LOW_VOL_RANGE')
                and metrics['price_below']
                and macd_value <= thresholds['macd_power'] + 0.08
            ):
                confirmed = final_score >= (threshold - 0.05)
                if confirmed:
                    trend_status = "медвежий (режимное послабление)"
            if not confirmed and aligned_with_regime and metrics['price_below']:
                confirmed = final_score >= (threshold - 0.10)
                if confirmed:
                    trend_status = "медвежий (гистерезис)"
        else:
            return False, f"Неизвестное направление: {direction}"

        # Для повышенной волатильности ужесточаем требования, чтобы избежать ложных подтверждений
        if confirmed and high_vol:
            if direction_upper in ('LONG', 'BUY'):
                confirmed = ema_gap_ratio >= 0.0006 and macd_value >= -0.0005
                if not confirmed:
                    trend_status = "высокая волатильность без подтверждения"
            else:
                confirmed = ema_gap_ratio <= -0.0006 and macd_value <= 0.0005
                if not confirmed:
                    trend_status = "высокая волатильность без подтверждения"

        if confirmed:
            logger.debug(
                (
                    "✅ MTF подтверждение для %s %s: тренд=%s "
                    "(gap=%.4f, slope_fast=%.5f, slope_slow=%.5f, MACD=%.5f, σ=%.5f)"
                ),
                symbol,
                direction,
                trend_status,
                ema_gap_ratio,
                fast_slope,
                slow_slope,
                macd_value,
                recent_volatility or -1,
            )
            return True, None

        logger.debug(
            "❌ MTF подтверждение для %s %s: gap=%.4f, slope_fast=%.5f, slope_slow=%.5f, MACD=%.5f, σ=%.5f",
            symbol,
            direction,
            ema_gap_ratio,
            fast_slope,
            slow_slope,
            macd_value,
            recent_volatility or -1,
        )
        return False, trend_status

    except Exception as e:
        error_msg = f"Ошибка MTF подтверждения для {symbol}: {e}"
        logger.error(error_msg)
        return False, error_msg


async def get_mtf_trend(
    symbol: str,
    timeframe: str = '4h'
) -> Optional[str]:
    """
    Получает тренд на указанном таймфрейме

    Args:
        symbol: Торговая пара
        timeframe: Таймфрейм (по умолчанию '4h')

    Returns:
        'BULL', 'BEAR' или None
    """
    try:
        if get_ohlc_with_fallback is None:
            return None

        h4_data = await get_ohlc_with_fallback(symbol, interval=timeframe, limit=50)

        if not h4_data or len(h4_data) < 20:
            return None

        df = pd.DataFrame(h4_data)
        current_index = len(df) - 1

        # Рассчитываем EMA
        ema_fast = df['close'].ewm(span=12, adjust=False).mean()
        ema_slow = df['close'].ewm(span=26, adjust=False).mean()

        current_ema_fast = ema_fast.iloc[current_index]
        current_ema_slow = ema_slow.iloc[current_index]

        if current_ema_fast > current_ema_slow:
            return 'BULL'
        elif current_ema_fast < current_ema_slow:
            return 'BEAR'
        else:
            return None

    except Exception as e:
        logger.error("Ошибка получения MTF тренда для %s: %s", symbol, e)
        return None

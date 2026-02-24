#!/usr/bin/env python3
"""
🚀 Модуль технических индикаторов ATRA
Централизованный модуль для расчета всех индикаторов с поддержкой Rust-ускорения
и оптимизацией потребления памяти.
"""

import logging
import os
from typing import Optional

import numpy as np
import pandas as pd
import ta

from src.data.dataframe_optimizer import optimize_dataframe_types

logger = logging.getLogger(__name__)

# 🔧 ПРОВЕРЯЕМ RUST УСКОРЕНИЕ
try:
    from src.infrastructure.performance.rust_accelerator import RUST_AVAILABLE, RustAccelerator

    if RUST_AVAILABLE:
        rust_accelerator = RustAccelerator()
        logger.info("✅ Rust acceleration включен для индикаторов")
    else:
        rust_accelerator = None
except ImportError:
    rust_accelerator = None
    logger.debug("⚠️ Rust модуль не найден, используем Python (ta)")


def add_technical_indicators(
    df: pd.DataFrame,
    rsi_period: int = 14,
    ema_periods: list = [7, 25, 12, 26],
    bb_period: int = 20,
    bb_std: float = 2.0,
    atr_period: int = 14,
) -> pd.DataFrame:
    """
    Добавляет технические индикаторы к DataFrame.
    Использует Rust если доступен, иначе fallback на библиотеку ta.
    В конце проводит оптимизацию типов данных для экономии памяти.
    """
    try:
        # ПРИНУДИТЕЛЬНАЯ КОНВЕРТАЦИЯ В FLOAT ДЛЯ СОВМЕСТИМОСТИ С TA/RUST/NUMPY
        # (так как в ohlc_utils мы теперь используем Decimal для точности денег)
        for col in ["open", "high", "low", "close", "volume"]:
            if col in df.columns:
                df[col] = df[col].astype(float)

        if len(df) < max(
            rsi_period, max(ema_periods) if ema_periods else 0, bb_period, atr_period, 50
        ):
            logger.warning(
                "Недостаточно данных для расчета индикаторов (нужно >50, есть %d)", len(df)
            )
            return df

        # Подготовка данных для Rust (если доступен)
        if rust_accelerator and rust_accelerator.available:
            closes = df["close"].tolist()
            highs = df["high"].tolist()
            lows = df["low"].tolist()

            # RSI
            df[f"rsi_{rsi_period}"] = rust_accelerator.calculate_rsi(closes, period=rsi_period)
            df["rsi"] = df[f"rsi_{rsi_period}"]  # Backward compatibility

            # ATR & Volatility
            df["atr"] = rust_accelerator.calculate_atr(highs, lows, closes, period=atr_period)
            df["volatility"] = (df["atr"] / df["close"]) * 100

            # Bollinger Bands
            upper, middle, lower = rust_accelerator.calculate_bollinger_bands(
                closes, period=bb_period, std_dev=bb_std
            )
            df["bb_upper"], df["bb_mavg"], df["bb_lower"] = upper, middle, lower

            # EMA
            for period in ema_periods:
                df[f"ema{period}"] = rust_accelerator.calculate_ema(closes, period=period)

            # Backward compatibility for common names
            if 7 in ema_periods:
                df["ema7"] = df["ema7"]
            if 25 in ema_periods:
                df["ema25"] = df["ema25"]
            if 12 in ema_periods:
                df["ema_fast"] = df["ema12"]
            if 26 in ema_periods:
                df["ema_slow"] = df["ema26"]

            # MACD
            macd_line, signal_line, hist = rust_accelerator.calculate_macd(closes, 12, 26, 9)
            df["macd"], df["macd_signal"], df["macd_histogram"] = macd_line, signal_line, hist

            # ADX (Fallback to ta as it is not yet in Rust)
            adx_ind = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14)
            df["adx"] = adx_ind.adx()
            df["trend_strength"] = df["adx"]
        else:
            # --- Fallback на Python (ta) ---
            # RSI
            df[f"rsi_{rsi_period}"] = ta.momentum.RSIIndicator(df["close"], window=rsi_period).rsi()
            df["rsi"] = df[f"rsi_{rsi_period}"]

            # ATR & Volatility
            atr_ind = ta.volatility.AverageTrueRange(
                df["high"], df["low"], df["close"], window=atr_period
            )
            df["atr"] = atr_ind.average_true_range()
            df["volatility"] = (df["atr"] / df["close"]) * 100

            # Bollinger Bands
            bb_ind = ta.volatility.BollingerBands(df["close"], window=bb_period, window_dev=bb_std)
            df["bb_upper"] = bb_ind.bollinger_hband()
            df["bb_lower"] = bb_ind.bollinger_lband()
            df["bb_mavg"] = bb_ind.bollinger_mavg()

            # EMA
            for period in ema_periods:
                df[f"ema{period}"] = ta.trend.EMAIndicator(
                    df["close"], window=period
                ).ema_indicator()

            # Backward compatibility
            if 12 in ema_periods:
                df["ema_fast"] = df["ema12"]
            if 26 in ema_periods:
                df["ema_slow"] = df["ema26"]

            # MACD
            macd_ind = ta.trend.MACD(df["close"], window_slow=26, window_fast=12, window_sign=9)
            df["macd"] = macd_ind.macd()
            df["macd_signal"] = macd_ind.macd_signal()
            df["macd_histogram"] = macd_ind.macd_diff()

            # ADX
            adx_ind = ta.trend.ADXIndicator(df["high"], df["low"], df["close"], window=14)
            df["adx"] = adx_ind.adx()
            df["trend_strength"] = df["adx"]

        # Индикаторы без Rust-версии (всегда Python)
        # SMA
        df["sma20"] = df["close"].rolling(window=20).mean()
        df["sma_20"] = df["sma20"]  # Backward compatibility

        # OBV
        df["obv"] = (np.sign(df["close"].diff()) * df["volume"]).fillna(0).cumsum()

        # Volume Ratio
        df["volume_ratio"] = df["volume"] / df["volume"].rolling(window=20).mean()

        # Momentum
        df["momentum"] = (df["close"] - df["close"].shift(5)) / df["close"].shift(5) * 100

        # ⚡ ОПТИМИЗАЦИЯ ПАМЯТИ
        df = optimize_dataframe_types(df)

        logger.debug("✅ Индикаторы рассчитаны и DataFrame оптимизирован")
        return df

    except Exception as e:
        logger.error("❌ Ошибка в add_technical_indicators: %s", e)
        return df

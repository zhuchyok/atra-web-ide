#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📈 MARKET REGIME DETECTION (Autonomous Adaptability)
Identifies current market phase for strategy and sizing adjustment.
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class MarketRegimeDetector:
    """
    Identifies if we are in a Trend or a Range, and Volatility levels.
    """
    def __init__(self, window: int = 50):
        self.window = window

    async def detect_regime(self, symbol: str) -> Dict[str, Any]:
        """
        Асинхронная версия: получает OHLCV и определяет режим.
        """
        try:
            from src.data.price_api import get_ohlc_with_fallback
            df = await get_ohlc_with_fallback(symbol, interval='1h', limit=100)
            
            if df is None or len(df) < self.window:
                return {"regime": "NEUTRAL", "confidence": 0.5}

            # 1. Trend Strength (ADX)
            # Убеждаемся что есть нужные колонки
            if 'adx' not in df.columns:
                from src.infrastructure.performance.rust_accelerator import fast_adx
                df['adx'] = fast_adx(df['high'].values, df['low'].values, df['close'].values, period=14)

            adx = df['adx'].iloc[-1]
            
            # 2. Price vs EMA (Direction)
            if 'ema_slow' not in df.columns:
                df['ema_slow'] = df['close'].ewm(span=50).mean()
                
            price = df['close'].iloc[-1]
            ema = df['ema_slow'].iloc[-1]
            
            # 3. Volatility (ATR %)
            if 'volatility' not in df.columns:
                df['volatility'] = (df['high'] - df['low']).rolling(20).mean() / df['close'] * 100

            volatility = df['volatility'].iloc[-1]
            
            if adx > 25:
                if price > ema:
                    regime = "BULL_TREND"
                else:
                    regime = "BEAR_TREND"
                confidence = min(1.0, adx / 50.0)
            else:
                if volatility > 2.0:
                    regime = "HIGH_VOL_RANGE"
                else:
                    regime = "LOW_VOL_RANGE"
                confidence = 1.0 - (adx / 25.0)

            return {"regime": regime, "confidence": confidence}
        except Exception as e:
            logger.error(f"❌ [Regime] Ошибка для {symbol}: {e}")
            return {"regime": "NEUTRAL", "confidence": 0.5}

def get_regime_detector():
    return MarketRegimeDetector()

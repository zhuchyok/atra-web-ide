"""
Market Structure Analyzer - определение структуры рынка (тренд/флэт/волатильность)
"""

import logging
from typing import Dict, Any, Optional
from enum import Enum

import pandas as pd
import numpy as np
from src.signals.indicators import add_technical_indicators

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Режим рынка"""
    TREND_UP = "TREND_UP"  # Восходящий тренд
    TREND_DOWN = "TREND_DOWN"  # Нисходящий тренд
    RANGE = "RANGE"  # Флэт/диапазон
    VOLATILE = "VOLATILE"  # Высокая волатильность
    REVERSAL = "REVERSAL"  # Разворот


class MarketStructureAnalyzer:
    """
    Анализатор структуры рынка
    
    Определяет:
    - Тренд (восходящий/нисходящий)
    - Флэт/диапазон
    - Волатильность
    - Разворот
    """
    
    def __init__(
        self,
        adx_period: int = 14,
        adx_threshold: float = 25.0,  # Порог силы тренда
        atr_period: int = 14,
        range_threshold: float = 0.5,  # Порог для определения флэта (ATR ratio)
    ):
        self.adx_period = adx_period
        self.adx_threshold = adx_threshold
        self.atr_period = atr_period
        self.range_threshold = range_threshold
    
    def calculate_adx(self, df: pd.DataFrame) -> pd.Series:
        """
        Рассчитывает ADX через централизованный модуль.
        """
        try:
            if 'adx' not in df.columns:
                df = add_technical_indicators(df)
            return df['adx']
        except Exception as e:
            logger.error("❌ Ошибка расчета ADX: %s", e)
            return pd.Series([np.nan] * len(df), index=df.index)

    def calculate_atr_ratio(self, df: pd.DataFrame, lookback: int = 20) -> float:
        """
        Рассчитывает отношение текущего ATR к среднему ATR через централизованный модуль.
        """
        try:
            if 'atr' not in df.columns:
                df = add_technical_indicators(df)
            
            atr = df['atr'].values
            current_atr = atr[-1]
            avg_atr = np.mean(atr[-lookback:])
            
            if avg_atr == 0:
                return 1.0
            
            return float(current_atr / avg_atr)
        except Exception as e:
            logger.error("❌ Ошибка расчета ATR ratio: %s", e)
            return 1.0

    def is_uptrend(self, df: pd.DataFrame, ema_fast_period: int = 7, ema_slow_period: int = 25) -> bool:
        """
        Определяет восходящий тренд через централизованные индикаторы.
        """
        try:
            if 'ema7' not in df.columns or 'ema25' not in df.columns:
                df = add_technical_indicators(df)
            
            ema_fast = df['ema7'].values
            ema_slow = df['ema25'].values
            
            if ema_fast[-1] <= ema_slow[-1]:
                return False
            
            current_price = float(df['close'].iloc[-1])
            if current_price < ema_fast[-1]:
                return False
            
            # Структура свечей
            recent_highs = df['high'].tail(10).values
            recent_lows = df['low'].tail(10).values
            
            if len(recent_highs) >= 3:
                if recent_highs[-1] < recent_highs[-2] or recent_highs[-2] < recent_highs[-3]:
                    return False
            
            if len(recent_lows) >= 3:
                if recent_lows[-1] < recent_lows[-2] or recent_lows[-2] < recent_lows[-3]:
                    return False
            
            return True
        except Exception as e:
            logger.error("❌ Ошибка определения восходящего тренда: %s", e)
            return False

    def is_downtrend(self, df: pd.DataFrame, ema_fast_period: int = 7, ema_slow_period: int = 25) -> bool:
        """
        Определяет нисходящий тренд через централизованные индикаторы.
        """
        try:
            if 'ema7' not in df.columns or 'ema25' not in df.columns:
                df = add_technical_indicators(df)
            
            ema_fast = df['ema7'].values
            ema_slow = df['ema25'].values
            
            if ema_fast[-1] >= ema_slow[-1]:
                return False
            
            current_price = float(df['close'].iloc[-1])
            if current_price > ema_fast[-1]:
                return False
            
            recent_highs = df['high'].tail(10).values
            recent_lows = df['low'].tail(10).values
            
            if len(recent_highs) >= 3:
                if recent_highs[-1] > recent_highs[-2] or recent_highs[-2] > recent_highs[-3]:
                    return False
            
            if len(recent_lows) >= 3:
                if recent_lows[-1] > recent_lows[-2] or recent_lows[-2] > recent_lows[-3]:
                    return False
            
            return True
        except Exception as e:
            logger.error("❌ Ошибка определения нисходящего тренда: %s", e)
            return False
    
    def is_range(self, df: pd.DataFrame) -> bool:
        """
        Определяет, находится ли рынок во флэте/диапазоне
        
        Args:
            df: DataFrame с OHLCV данными
        
        Returns:
            True если флэт
        """
        try:
            if len(df) < 20:
                return False
            
            # Рассчитываем ATR ratio
            atr_ratio = self.calculate_atr_ratio(df)
            
            # Низкая волатильность = флэт
            if atr_ratio < self.range_threshold:
                return True
            
            # Проверяем диапазон цен за последние 20 свечей
            recent_high = df['high'].tail(20).max()
            recent_low = df['low'].tail(20).min()
            price_range = (recent_high - recent_low) / recent_low * 100
            
            # Если диапазон меньше 3% - флэт
            if price_range < 3.0:
                return True
            
            return False
        except Exception as e:
            logger.error("❌ Ошибка определения флэта: %s", e)
            return False
    
    def get_market_regime(self, df: pd.DataFrame) -> MarketRegime:
        """
        Определяет текущий режим рынка
        
        Args:
            df: DataFrame с OHLCV данными
        
        Returns:
            MarketRegime: Режим рынка
        """
        try:
            if len(df) < max(self.adx_period, 25):
                return MarketRegime.VOLATILE
            
            # Рассчитываем ADX
            adx_series = self.calculate_adx(df)
            current_adx = adx_series.iloc[-1] if not pd.isna(adx_series.iloc[-1]) else 0
            
            # Рассчитываем ATR ratio
            atr_ratio = self.calculate_atr_ratio(df)
            
            # Высокая волатильность
            if atr_ratio > 2.0:
                return MarketRegime.VOLATILE
            
            # Флэт
            if self.is_range(df):
                return MarketRegime.RANGE
            
            # Тренд (требует сильного ADX)
            if current_adx > self.adx_threshold:
                if self.is_uptrend(df):
                    return MarketRegime.TREND_UP
                elif self.is_downtrend(df):
                    return MarketRegime.TREND_DOWN
            
            # По умолчанию - волатильность
            return MarketRegime.VOLATILE
            
        except Exception as e:
            logger.error("❌ Ошибка определения режима рынка: %s", e)
            return MarketRegime.VOLATILE
    
    def get_regime_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        """
        Возвращает детальную информацию о режиме рынка
        
        Args:
            df: DataFrame с OHLCV данными
        
        Returns:
            Dict с информацией о режиме
        """
        try:
            regime = self.get_market_regime(df)
            adx_series = self.calculate_adx(df)
            current_adx = adx_series.iloc[-1] if not pd.isna(adx_series.iloc[-1]) else 0
            atr_ratio = self.calculate_atr_ratio(df)
            
            return {
                "regime": regime.value,
                "adx": current_adx,
                "atr_ratio": atr_ratio,
                "is_uptrend": self.is_uptrend(df),
                "is_downtrend": self.is_downtrend(df),
                "is_range": self.is_range(df),
            }
        except Exception as e:
            logger.error("❌ Ошибка получения информации о режиме: %s", e)
            return {
                "regime": MarketRegime.VOLATILE.value,
                "adx": 0.0,
                "atr_ratio": 1.0,
                "is_uptrend": False,
                "is_downtrend": False,
                "is_range": False,
            }

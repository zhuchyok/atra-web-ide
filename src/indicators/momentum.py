"""
Momentum Indicators - индикаторы импульса для подтверждения движения
"""

import logging
from typing import Dict, Optional, Tuple

import pandas as pd
import numpy as np
import talib  # type: ignore

logger = logging.getLogger(__name__)


class MomentumAnalyzer:
    """
    Анализатор импульса
    
    Рассчитывает:
    - RSI (Relative Strength Index)
    - MACD (Moving Average Convergence Divergence)
    - Momentum
    - Rate of Change (ROC)
    """
    
    def __init__(
        self,
        rsi_period: int = 14,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        momentum_period: int = 10,
        roc_period: int = 10,
    ):
        self.rsi_period = rsi_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.momentum_period = momentum_period
        self.roc_period = roc_period
    
    def calculate_rsi(self, df: pd.DataFrame) -> Optional[pd.Series]:
        """
        Рассчитывает RSI
        
        Args:
            df: DataFrame с OHLCV данными
        
        Returns:
            Series с значениями RSI
        """
        try:
            if len(df) < self.rsi_period + 1:
                return None
            
            close = df['close'].values
            rsi = talib.RSI(close, timeperiod=self.rsi_period)
            return pd.Series(rsi, index=df.index)
        except Exception as e:
            logger.error("❌ Ошибка расчета RSI: %s", e)
            return None
    
    def calculate_macd(self, df: pd.DataFrame) -> Dict[str, Optional[pd.Series]]:
        """
        Рассчитывает MACD
        
        Args:
            df: DataFrame с OHLCV данными
        
        Returns:
            Dict с macd, signal, histogram
        """
        try:
            if len(df) < self.macd_slow + self.macd_signal:
                return {
                    "macd": None,
                    "signal": None,
                    "histogram": None,
                }
            
            close = df['close'].values
            macd, signal, histogram = talib.MACD(
                close,
                fastperiod=self.macd_fast,
                slowperiod=self.macd_slow,
                signalperiod=self.macd_signal,
            )
            
            return {
                "macd": pd.Series(macd, index=df.index),
                "signal": pd.Series(signal, index=df.index),
                "histogram": pd.Series(histogram, index=df.index),
            }
        except Exception as e:
            logger.error("❌ Ошибка расчета MACD: %s", e)
            return {
                "macd": None,
                "signal": None,
                "histogram": None,
            }
    
    def calculate_momentum(self, df: pd.DataFrame) -> Optional[pd.Series]:
        """
        Рассчитывает Momentum
        
        Args:
            df: DataFrame с OHLCV данными
        
        Returns:
            Series с значениями Momentum
        """
        try:
            if len(df) < self.momentum_period + 1:
                return None
            
            close = df['close'].values
            momentum = talib.MOM(close, timeperiod=self.momentum_period)
            return pd.Series(momentum, index=df.index)
        except Exception as e:
            logger.error("❌ Ошибка расчета Momentum: %s", e)
            return None
    
    def calculate_roc(self, df: pd.DataFrame) -> Optional[pd.Series]:
        """
        Рассчитывает Rate of Change (ROC)
        
        Args:
            df: DataFrame с OHLCV данными
        
        Returns:
            Series с значениями ROC
        """
        try:
            if len(df) < self.roc_period + 1:
                return None
            
            close = df['close'].values
            roc = talib.ROC(close, timeperiod=self.roc_period)
            return pd.Series(roc, index=df.index)
        except Exception as e:
            logger.error("❌ Ошибка расчета ROC: %s", e)
            return None
    
    def get_momentum_score(
        self,
        df: pd.DataFrame,
        direction: str,
    ) -> float:
        """
        Рассчитывает общую оценку импульса (0.0 - 1.0)
        
        Args:
            df: DataFrame с OHLCV данными
            direction: "LONG" или "SHORT"
        
        Returns:
            Оценка импульса (0.0 - 1.0)
        """
        try:
            if len(df) < max(self.rsi_period, self.macd_slow, self.momentum_period) + 1:
                return 0.5
            
            score = 0.0
            components = 0
            
            # RSI
            rsi_series = self.calculate_rsi(df)
            if rsi_series is not None and not pd.isna(rsi_series.iloc[-1]):
                rsi_value = rsi_series.iloc[-1]
                if direction.upper() == "LONG":
                    # Для LONG: RSI должен быть не перекупленным (< 70)
                    if 30 <= rsi_value < 70:
                        score += 0.3
                    elif rsi_value < 30:
                        score += 0.5  # Сильная перепроданность
                elif direction.upper() == "SHORT":
                    # Для SHORT: RSI должен быть не перепроданным (> 30)
                    if 30 < rsi_value <= 70:
                        score += 0.3
                    elif rsi_value > 70:
                        score += 0.5  # Сильная перекупленность
                components += 1
            
            # MACD
            macd_data = self.calculate_macd(df)
            if macd_data.get("macd") is not None and macd_data.get("signal") is not None:
                macd = macd_data["macd"].iloc[-1]
                signal = macd_data["signal"].iloc[-1]
                histogram = macd_data.get("histogram")
                
                if not pd.isna(macd) and not pd.isna(signal):
                    if direction.upper() == "LONG":
                        # Для LONG: MACD должен быть выше сигнала
                        if macd > signal:
                            score += 0.3
                        if histogram is not None and not pd.isna(histogram.iloc[-1]):
                            if histogram.iloc[-1] > 0:
                                score += 0.2  # Растущий гистограмм
                    elif direction.upper() == "SHORT":
                        # Для SHORT: MACD должен быть ниже сигнала
                        if macd < signal:
                            score += 0.3
                        if histogram is not None and not pd.isna(histogram.iloc[-1]):
                            if histogram.iloc[-1] < 0:
                                score += 0.2  # Падающий гистограмм
                    components += 1
            
            # Momentum
            momentum_series = self.calculate_momentum(df)
            if momentum_series is not None and not pd.isna(momentum_series.iloc[-1]):
                momentum_value = momentum_series.iloc[-1]
                if direction.upper() == "LONG":
                    if momentum_value > 0:
                        score += 0.2
                elif direction.upper() == "SHORT":
                    if momentum_value < 0:
                        score += 0.2
                components += 1
            
            # ROC
            roc_series = self.calculate_roc(df)
            if roc_series is not None and not pd.isna(roc_series.iloc[-1]):
                roc_value = roc_series.iloc[-1]
                if direction.upper() == "LONG":
                    if roc_value > 0:
                        score += 0.2
                elif direction.upper() == "SHORT":
                    if roc_value < 0:
                        score += 0.2
                components += 1
            
            # Нормализуем оценку
            if components > 0:
                return min(1.0, score)
            else:
                return 0.5
                
        except Exception as e:
            logger.error("❌ Ошибка расчета оценки импульса: %s", e)
            return 0.5
    
    def is_momentum_confirmed(
        self,
        df: pd.DataFrame,
        direction: str,
        min_score: float = 0.6,
    ) -> Tuple[bool, float]:
        """
        Проверяет, подтвержден ли импульс для направления
        
        Args:
            df: DataFrame с OHLCV данными
            direction: "LONG" или "SHORT"
            min_score: Минимальная оценка для подтверждения
        
        Returns:
            Tuple[подтвержден_ли, оценка]
        """
        score = self.get_momentum_score(df, direction)
        return score >= min_score, score


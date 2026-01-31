"""
Stochastic RSI (Stoch RSI) - стохастический RSI

Более чувствительная версия RSI, показывает перекупленность/перепроданность раньше.
Используется для фильтрации входов и раннего выхода.
"""

import logging
from typing import Optional, Dict
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class StochasticRSI:
    """
    Stochastic RSI (Stoch RSI) - стохастический RSI
    
    Stoch RSI = (RSI - min(RSI)) / (max(RSI) - min(RSI))
    где min/max берутся за период
    
    Более чувствительный чем обычный RSI, так как нормализует значения.
    """
    
    def __init__(
        self,
        rsi_period: int = 14,  # Период для RSI
        stoch_period: int = 14,  # Период для Stochastic
        k_period: int = 3,  # Период сглаживания %K
        d_period: int = 3,  # Период сглаживания %D
    ):
        """
        Args:
            rsi_period: Период для расчета RSI
            stoch_period: Период для расчета Stochastic
            k_period: Период сглаживания %K
            d_period: Период сглаживания %D
        """
        self.rsi_period = rsi_period
        self.stoch_period = stoch_period
        self.k_period = k_period
        self.d_period = d_period
    
    def calculate_rsi(self, df: pd.DataFrame) -> pd.Series:
        """
        Рассчитывает RSI
        
        Args:
            df: DataFrame с OHLCV данными
            
        Returns:
            Series с RSI значениями
        """
        try:
            if len(df) < self.rsi_period + 1:
                return pd.Series(index=df.index, dtype=float)
            
            # Рассчитываем изменения цен
            price_changes = df['close'].diff()
            
            # Разделяем на прибыли и убытки
            gains = price_changes.where(price_changes > 0, 0)
            losses = -price_changes.where(price_changes < 0, 0)
            
            # Скользящие средние
            avg_gain = gains.rolling(window=self.rsi_period, min_periods=1).mean()
            avg_loss = losses.rolling(window=self.rsi_period, min_periods=1).mean()
            
            # Избегаем деления на ноль
            avg_loss = avg_loss.replace(0, 1e-10)
            
            # Рассчитываем RS и RSI
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            
            return pd.Series(rsi, index=df.index)
            
        except Exception as e:
            logger.error(f"Ошибка расчета RSI для Stoch RSI: {e}")
            return pd.Series(index=df.index, dtype=float)
    
    def calculate(self, df: pd.DataFrame) -> Dict[str, pd.Series]:
        """
        Рассчитывает Stochastic RSI
        
        Args:
            df: DataFrame с OHLCV данными
            
        Returns:
            Dict с Series:
            {
                'stoch_rsi': Series с Stoch RSI значениями (0-100),
                'stoch_rsi_k': Series с %K (сглаженный),
                'stoch_rsi_d': Series с %D (сглаженный %K)
            }
        """
        try:
            if len(df) < self.rsi_period + self.stoch_period:
                return {
                    'stoch_rsi': pd.Series(index=df.index, dtype=float),
                    'stoch_rsi_k': pd.Series(index=df.index, dtype=float),
                    'stoch_rsi_d': pd.Series(index=df.index, dtype=float),
                }
            
            # Рассчитываем RSI
            rsi = self.calculate_rsi(df)
            
            # Рассчитываем Stochastic от RSI
            stoch_rsi_values = pd.Series(index=df.index, dtype=float)
            
            for i in range(self.rsi_period + self.stoch_period - 1, len(rsi)):
                # Берем окно RSI значений
                rsi_window = rsi.iloc[i - self.stoch_period + 1:i + 1]
                
                if len(rsi_window) == 0:
                    continue
                
                current_rsi = rsi.iloc[i]
                min_rsi = rsi_window.min()
                max_rsi = rsi_window.max()
                
                # Избегаем деления на ноль
                rsi_range = max_rsi - min_rsi
                if rsi_range == 0:
                    stoch_rsi_values.iloc[i] = 50.0  # Нейтральное значение
                else:
                    # Stochastic RSI = (RSI - min) / (max - min) * 100
                    stoch_rsi = ((current_rsi - min_rsi) / rsi_range) * 100
                    stoch_rsi_values.iloc[i] = stoch_rsi
            
            # Сглаживаем %K
            stoch_rsi_k = stoch_rsi_values.rolling(window=self.k_period, min_periods=1).mean()
            
            # Сглаживаем %D (среднее от %K)
            stoch_rsi_d = stoch_rsi_k.rolling(window=self.d_period, min_periods=1).mean()
            
            return {
                'stoch_rsi': stoch_rsi_values,
                'stoch_rsi_k': stoch_rsi_k,
                'stoch_rsi_d': stoch_rsi_d,
            }
            
        except Exception as e:
            logger.error(f"Ошибка расчета Stochastic RSI: {e}")
            return {
                'stoch_rsi': pd.Series(index=df.index, dtype=float),
                'stoch_rsi_k': pd.Series(index=df.index, dtype=float),
                'stoch_rsi_d': pd.Series(index=df.index, dtype=float),
            }
    
    def get_value(self, df: pd.DataFrame, i: int) -> Optional[float]:
        """
        Получает текущее значение Stoch RSI %K
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            
        Returns:
            Значение Stoch RSI %K или None
        """
        try:
            stoch_rsi = self.calculate(df)
            if len(stoch_rsi['stoch_rsi_k']) > i:
                value = stoch_rsi['stoch_rsi_k'].iloc[i]
                return float(value) if not pd.isna(value) else None
            return None
        except Exception as e:
            logger.error(f"Ошибка получения значения Stoch RSI: {e}")
            return None
    
    def is_overbought(self, df: pd.DataFrame, i: int, threshold: float = 80.0) -> bool:
        """
        Проверяет, находится ли Stoch RSI в зоне перекупленности
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            threshold: Порог перекупленности (по умолчанию 80)
            
        Returns:
            True если перекупленность
        """
        try:
            stoch_rsi = self.get_value(df, i)
            return stoch_rsi is not None and stoch_rsi > threshold
        except Exception as e:
            logger.error(f"Ошибка проверки перекупленности Stoch RSI: {e}")
            return False
    
    def is_oversold(self, df: pd.DataFrame, i: int, threshold: float = 20.0) -> bool:
        """
        Проверяет, находится ли Stoch RSI в зоне перепроданности
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            threshold: Порог перепроданности (по умолчанию 20)
            
        Returns:
            True если перепроданность
        """
        try:
            stoch_rsi = self.get_value(df, i)
            return stoch_rsi is not None and stoch_rsi < threshold
        except Exception as e:
            logger.error(f"Ошибка проверки перепроданности Stoch RSI: {e}")
            return False
    
    def get_signal(self, df: pd.DataFrame, i: int) -> Optional[str]:
        """
        Определяет сигнал на основе Stoch RSI
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            
        Returns:
            'long' если перепроданность, 'short' если перекупленность, None если нейтрально
        """
        try:
            if self.is_oversold(df, i, threshold=20.0):
                return 'long'
            elif self.is_overbought(df, i, threshold=80.0):
                return 'short'
            return None
        except Exception as e:
            logger.error(f"Ошибка определения сигнала Stoch RSI: {e}")
            return None


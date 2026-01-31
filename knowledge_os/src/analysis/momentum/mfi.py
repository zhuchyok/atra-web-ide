"""
Money Flow Index (MFI) - индекс денежного потока

Комбинация цены и объема, показывает давление денег.
Более точный чем RSI, так как учитывает объем.
Используется для определения перекупленности/перепроданности.
"""

import logging
from typing import Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class MoneyFlowIndex:
    """
    Money Flow Index (MFI) - индекс денежного потока
    
    MFI = 100 - (100 / (1 + Money Ratio))
    где Money Ratio = Positive Money Flow / Negative Money Flow
    
    Positive Money Flow = сумма (Typical Price * Volume) для свечей с ростом
    Negative Money Flow = сумма (Typical Price * Volume) для свечей с падением
    """
    
    def __init__(self, period: int = 14):
        """
        Args:
            period: Период для расчета MFI (по умолчанию 14)
        """
        self.period = period
    
    def calculate(self, df: pd.DataFrame) -> pd.Series:
        """
        Рассчитывает Money Flow Index
        
        Args:
            df: DataFrame с OHLCV данными
            
        Returns:
            Series с MFI значениями (0-100)
        """
        try:
            if len(df) < self.period + 1:
                return pd.Series(index=df.index, dtype=float)
            
            # Проверяем наличие необходимых колонок
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                logger.error("Отсутствуют необходимые колонки для расчета MFI")
                return pd.Series(index=df.index, dtype=float)
            
            # Рассчитываем Typical Price
            typical_price = (df['high'] + df['low'] + df['close']) / 3.0
            
            # Рассчитываем Raw Money Flow
            raw_money_flow = typical_price * df['volume']
            
            # Определяем направление движения
            price_change = typical_price.diff()
            
            # Positive Money Flow (рост цены)
            positive_flow = raw_money_flow.where(price_change > 0, 0)
            
            # Negative Money Flow (падение цены)
            negative_flow = raw_money_flow.where(price_change < 0, 0)
            
            # Скользящие средние за период
            positive_flow_ma = positive_flow.rolling(window=self.period, min_periods=1).sum()
            negative_flow_ma = negative_flow.rolling(window=self.period, min_periods=1).sum()
            
            # Рассчитываем Money Ratio
            # Избегаем деления на ноль
            negative_flow_ma = negative_flow_ma.replace(0, 1e-10)
            money_ratio = positive_flow_ma / negative_flow_ma
            
            # Рассчитываем MFI
            mfi = 100 - (100 / (1 + money_ratio))
            
            return pd.Series(mfi, index=df.index)
            
        except Exception as e:
            logger.error(f"Ошибка расчета Money Flow Index: {e}")
            return pd.Series(index=df.index, dtype=float)
    
    def get_value(self, df: pd.DataFrame, i: int) -> Optional[float]:
        """
        Получает текущее значение MFI
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            
        Returns:
            Значение MFI или None
        """
        try:
            mfi = self.calculate(df)
            if len(mfi) > i:
                value = mfi.iloc[i]
                return float(value) if not pd.isna(value) else None
            return None
        except Exception as e:
            logger.error(f"Ошибка получения значения MFI: {e}")
            return None
    
    def is_overbought(self, df: pd.DataFrame, i: int, threshold: float = 80.0) -> bool:
        """
        Проверяет, находится ли MFI в зоне перекупленности
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            threshold: Порог перекупленности (по умолчанию 80)
            
        Returns:
            True если перекупленность
        """
        try:
            mfi = self.get_value(df, i)
            return mfi is not None and mfi > threshold
        except Exception as e:
            logger.error(f"Ошибка проверки перекупленности MFI: {e}")
            return False
    
    def is_oversold(self, df: pd.DataFrame, i: int, threshold: float = 20.0) -> bool:
        """
        Проверяет, находится ли MFI в зоне перепроданности
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            threshold: Порог перепроданности (по умолчанию 20)
            
        Returns:
            True если перепроданность
        """
        try:
            mfi = self.get_value(df, i)
            return mfi is not None and mfi < threshold
        except Exception as e:
            logger.error(f"Ошибка проверки перепроданности MFI: {e}")
            return False
    
    def get_signal(self, df: pd.DataFrame, i: int) -> Optional[str]:
        """
        Определяет сигнал на основе MFI
        
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
            logger.error(f"Ошибка определения сигнала MFI: {e}")
            return None


"""
True Strength Index (TSI) - индекс истинной силы

Более чувствительный индикатор тренда, показывает силу и направление тренда.
Используется для фильтрации входов и определения разворотов.
"""

import logging
from typing import Optional
import pandas as pd

logger = logging.getLogger(__name__)


class TrueStrengthIndex:
    """
    True Strength Index (TSI) - индекс истинной силы
    
    TSI = (EMA(EMA(Price Change, r), s) / EMA(EMA(Abs(Price Change), r), s)) * 100
    
    Где:
    - Price Change = Close - Close[1]
    - r = длинный период (обычно 25)
    - s = короткий период (обычно 13)
    """
    
    def __init__(
        self,
        long_period: int = 25,  # Длинный период EMA
        short_period: int = 13,  # Короткий период EMA
    ):
        """
        Args:
            long_period: Длинный период для первой EMA
            short_period: Короткий период для второй EMA
        """
        self.long_period = long_period
        self.short_period = short_period
    
    def calculate(self, df: pd.DataFrame) -> pd.Series:
        """
        Рассчитывает True Strength Index
        
        Args:
            df: DataFrame с OHLCV данными
            
        Returns:
            Series с TSI значениями
        """
        try:
            if len(df) < self.long_period + self.short_period:
                return pd.Series(index=df.index, dtype=float)
            
            # Проверяем наличие необходимых колонок
            if 'close' not in df.columns:
                logger.error("Отсутствует колонка 'close' для расчета TSI")
                return pd.Series(index=df.index, dtype=float)
            
            # Рассчитываем изменение цены
            price_change = df['close'].diff()
            price_change_abs = price_change.abs()
            
            # Первая EMA (длинный период)
            ema1_change = price_change.ewm(span=self.long_period, adjust=False).mean()
            ema1_abs = price_change_abs.ewm(span=self.long_period, adjust=False).mean()
            
            # Вторая EMA (короткий период)
            ema2_change = ema1_change.ewm(span=self.short_period, adjust=False).mean()
            ema2_abs = ema1_abs.ewm(span=self.short_period, adjust=False).mean()
            
            # Рассчитываем TSI
            # Избегаем деления на ноль
            ema2_abs = ema2_abs.replace(0, 1e-10)
            tsi = (ema2_change / ema2_abs) * 100
            
            return pd.Series(tsi, index=df.index)
            
        except Exception as e:
            logger.error("Ошибка расчета True Strength Index: %s", e)
            return pd.Series(index=df.index, dtype=float)
    
    def get_value(self, df: pd.DataFrame, i: int) -> Optional[float]:
        """
        Получает текущее значение TSI
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            
        Returns:
            Значение TSI или None
        """
        try:
            tsi = self.calculate(df)
            if len(tsi) > i:
                value = tsi.iloc[i]
                return float(value) if not pd.isna(value) else None
            return None
        except Exception as e:
            logger.error("Ошибка получения значения TSI: %s", e)
            return None
    
    def get_signal(self, df: pd.DataFrame, i: int) -> Optional[str]:
        """
        Определяет сигнал на основе TSI
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            
        Returns:
            'long' если восходящий тренд, 'short' если нисходящий, None если нейтрально
        """
        try:
            tsi = self.get_value(df, i)
            
            if tsi is None:
                return None
            
            # Положительный TSI = восходящий тренд
            # Отрицательный TSI = нисходящий тренд
            if tsi > 5:  # Порог для восходящего тренда
                return 'long'
            elif tsi < -5:  # Порог для нисходящего тренда
                return 'short'
            
            return None
            
        except Exception as e:
            logger.error("Ошибка определения сигнала TSI: %s", e)
            return None
    
    def is_bullish(self, df: pd.DataFrame, i: int, threshold: float = 5.0) -> bool:
        """
        Проверяет, восходящий ли тренд
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            threshold: Порог для восходящего тренда
            
        Returns:
            True если восходящий тренд
        """
        try:
            tsi = self.get_value(df, i)
            return tsi is not None and tsi > threshold
        except Exception as e:
            logger.error("Ошибка проверки бычьего тренда TSI: %s", e)
            return False
    
    def is_bearish(self, df: pd.DataFrame, i: int, threshold: float = -5.0) -> bool:
        """
        Проверяет, нисходящий ли тренд
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            threshold: Порог для нисходящего тренда
            
        Returns:
            True если нисходящий тренд
        """
        try:
            tsi = self.get_value(df, i)
            return tsi is not None and tsi < threshold
        except Exception as e:
            logger.error("Ошибка проверки медвежьего тренда TSI: %s", e)
            return False


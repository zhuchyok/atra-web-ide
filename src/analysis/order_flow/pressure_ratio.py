"""
Buy/Sell Pressure Ratio - соотношение давления покупок к продажам

Показывает направление агрессии и баланс между покупателями и продавцами.
Используется для фильтрации входов и определения разворотов.
"""

import logging
from typing import Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class PressureRatio:
    """
    Buy/Sell Pressure Ratio - соотношение давления покупок к продажам
    
    Рассчитывается на основе анализа нескольких свечей для определения
    общего направления давления.
    """
    
    def __init__(self, lookback: int = 5):
        """
        Args:
            lookback: Количество свечей для анализа давления (по умолчанию 5)
        """
        self.lookback = lookback
    
    def calculate(self, df: pd.DataFrame) -> pd.Series:
        """
        Рассчитывает Buy/Sell Pressure Ratio
        
        Args:
            df: DataFrame с OHLCV данными
            
        Returns:
            Series с Pressure Ratio значениями:
            - > 1.0: преобладают покупки
            - < 1.0: преобладают продажи
            - = 1.0: баланс
        """
        try:
            if len(df) == 0:
                return pd.Series(dtype=float)
            
            # Проверяем наличие необходимых колонок
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                logger.error("Отсутствуют необходимые колонки для расчета Pressure Ratio")
                return pd.Series(index=df.index, dtype=float)
            
            price_range = df['high'] - df['low']
            price_range = price_range.replace(0, 1e-10)
            
            # Вычисляем долю объема, идущую в покупки
            buy_ratio = np.where(
                df['close'] > df['open'],
                0.5 + (df['close'] - df['open']) / price_range * 0.4,
                np.where(
                    df['close'] < df['open'],
                    (df['close'] - df['low']) / price_range * 0.4,
                    0.5
                )
            )
            buy_ratio = np.clip(buy_ratio, 0.0, 1.0)
            
            # Вычисляем объемы покупок и продаж
            buy_volume = df['volume'] * buy_ratio
            sell_volume = df['volume'] * (1 - buy_ratio)
            
            # Скользящее среднее для сглаживания
            buy_volume_ma = buy_volume.rolling(window=self.lookback, min_periods=1).sum()
            sell_volume_ma = sell_volume.rolling(window=self.lookback, min_periods=1).sum()
            
            # Соотношение давления
            # Избегаем деления на ноль
            sell_volume_ma = sell_volume_ma.replace(0, 1e-10)
            pressure_ratio = buy_volume_ma / sell_volume_ma
            
            return pd.Series(pressure_ratio, index=df.index)
            
        except Exception as e:
            logger.error(f"Ошибка расчета Pressure Ratio: {e}")
            return pd.Series(index=df.index, dtype=float)
    
    def get_signal(self, df: pd.DataFrame, i: int) -> Optional[str]:
        """
        Определяет сигнал на основе Pressure Ratio
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            
        Returns:
            'long' если преобладают покупки, 'short' если продажи, None если нейтрально
        """
        try:
            if i >= len(df):
                return None
            
            pr = self.calculate(df)
            
            if len(pr) <= i:
                return None
            
            current_ratio = pr.iloc[i]
            
            # Пороги для определения сигнала
            if current_ratio > 1.2:  # Покупки преобладают на 20%+
                return 'long'
            elif current_ratio < 0.8:  # Продажи преобладают на 20%+
                return 'short'
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка определения сигнала Pressure Ratio: {e}")
            return None
    
    def get_value(self, df: pd.DataFrame, i: int) -> Optional[float]:
        """
        Получает текущее значение Pressure Ratio
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            
        Returns:
            Значение Pressure Ratio или None
        """
        try:
            pr = self.calculate(df)
            if len(pr) > i:
                return float(pr.iloc[i])
            return None
        except Exception as e:
            logger.error(f"Ошибка получения значения Pressure Ratio: {e}")
            return None
    
    def is_bullish(self, df: pd.DataFrame, i: int, threshold: float = 1.1) -> bool:
        """
        Проверяет, преобладают ли покупки
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            threshold: Порог для определения преобладания (по умолчанию 1.1)
            
        Returns:
            True если покупки преобладают
        """
        try:
            pr = self.get_value(df, i)
            return pr is not None and pr > threshold
        except Exception as e:
            logger.error(f"Ошибка проверки бычьего давления: {e}")
            return False
    
    def is_bearish(self, df: pd.DataFrame, i: int, threshold: float = 0.9) -> bool:
        """
        Проверяет, преобладают ли продажи
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            threshold: Порог для определения преобладания (по умолчанию 0.9)
            
        Returns:
            True если продажи преобладают
        """
        try:
            pr = self.get_value(df, i)
            return pr is not None and pr < threshold
        except Exception as e:
            logger.error(f"Ошибка проверки медвежьего давления: {e}")
            return False


"""
Volume Delta - разница между покупками и продажами на свече

Показывает агрессивность покупок/продаж на текущей свече.
Используется для фильтрации входов и подтверждения пробоев.
"""

import logging
from typing import Optional
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class VolumeDelta:
    """
    Volume Delta - разница между объемом покупок и продаж на свече
    
    Аппроксимация на основе OHLCV:
    - Анализирует каждую свечу отдельно
    - Показывает направление агрессии на текущей свече
    """
    
    def __init__(self):
        """Инициализация Volume Delta"""
        pass
    
    def calculate(self, df: pd.DataFrame) -> pd.Series:
        """
        Рассчитывает Volume Delta для каждой свечи
        
        Args:
            df: DataFrame с OHLCV данными
            
        Returns:
            Series с Volume Delta значениями (положительные = покупки, отрицательные = продажи)
        """
        try:
            if len(df) == 0:
                return pd.Series(dtype=float)
            
            # Проверяем наличие необходимых колонок
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                logger.error("Отсутствуют необходимые колонки для расчета Volume Delta")
                return pd.Series(index=df.index, dtype=float)
            
            price_range = df['high'] - df['low']
            price_range = price_range.replace(0, 1e-10)  # Избегаем деления на ноль
            
            # Вычисляем долю объема, идущую в покупки
            # Более точная аппроксимация на основе положения close относительно диапазона
            buy_ratio = np.where(
                df['close'] > df['open'],
                # Бычья свеча: больше объема в покупки
                0.5 + (df['close'] - df['open']) / price_range * 0.4,
                np.where(
                    df['close'] < df['open'],
                    # Медвежья свеча: меньше объема в покупки
                    (df['close'] - df['low']) / price_range * 0.4,
                    # Нейтральная свеча: равномерное распределение
                    0.5
                )
            )
            
            # Ограничиваем значения от 0 до 1
            buy_ratio = np.clip(buy_ratio, 0.0, 1.0)
            
            # Вычисляем объемы покупок и продаж
            buy_volume = df['volume'] * buy_ratio
            sell_volume = df['volume'] * (1 - buy_ratio)
            
            # Разница (Delta) на свече
            volume_delta = buy_volume - sell_volume
            
            return pd.Series(volume_delta, index=df.index)
            
        except Exception as e:
            logger.error(f"Ошибка расчета Volume Delta: {e}")
            return pd.Series(index=df.index, dtype=float)
    
    def get_signal(self, df: pd.DataFrame, i: int) -> Optional[str]:
        """
        Определяет сигнал на основе Volume Delta текущей свечи
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            
        Returns:
            'long' если преобладают покупки, 'short' если продажи, None если нейтрально
        """
        try:
            if i >= len(df):
                return None
            
            vd = self.calculate(df)
            
            if len(vd) <= i:
                return None
            
            current_delta = vd.iloc[i]
            current_volume = df['volume'].iloc[i] if 'volume' in df.columns else 0
            
            # Если объем слишком мал, сигнал недействителен
            if current_volume == 0:
                return None
            
            # Пороги: если delta составляет более 20% от объема свечи
            threshold = current_volume * 0.2
            
            if current_delta > threshold:
                return 'long'
            elif current_delta < -threshold:
                return 'short'
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка определения сигнала Volume Delta: {e}")
            return None
    
    def get_value(self, df: pd.DataFrame, i: int) -> Optional[float]:
        """
        Получает текущее значение Volume Delta
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            
        Returns:
            Значение Volume Delta или None
        """
        try:
            vd = self.calculate(df)
            if len(vd) > i:
                return float(vd.iloc[i])
            return None
        except Exception as e:
            logger.error(f"Ошибка получения значения Volume Delta: {e}")
            return None
    
    def get_ratio(self, df: pd.DataFrame, i: int) -> Optional[float]:
        """
        Получает соотношение Volume Delta к объему свечи
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            
        Returns:
            Соотношение от -1 до 1 (1 = все покупки, -1 = все продажи)
        """
        try:
            vd = self.get_value(df, i)
            if vd is None:
                return None
            
            current_volume = df['volume'].iloc[i] if 'volume' in df.columns else 0
            if current_volume == 0:
                return None
            
            return float(vd / current_volume)
            
        except Exception as e:
            logger.error(f"Ошибка получения соотношения Volume Delta: {e}")
            return None


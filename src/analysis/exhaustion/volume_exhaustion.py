"""
Volume Exhaustion - анализ исчерпания объема при движении

Показывает, когда движение теряет силу из-за снижения объема.
Используется для раннего выхода и частичного выхода.
"""

import logging
from typing import Optional, Dict, Any
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class VolumeExhaustion:
    """
    Volume Exhaustion - анализ исчерпания объема при движении
    
    Определяет ситуации, когда:
    - Цена продолжает двигаться, но объем падает
    - Это указывает на исчерпание движения
    """
    
    def __init__(
        self,
        lookback: int = 10,  # Период для сравнения объема
        volume_decline_threshold: float = 0.3,  # Порог снижения объема (30%)
        price_movement_threshold: float = 0.5,  # Минимальное движение цены (%)
    ):
        """
        Args:
            lookback: Количество свечей для сравнения объема
            volume_decline_threshold: Порог снижения объема (0.3 = 30%)
            price_movement_threshold: Минимальное движение цены для анализа (%)
        """
        self.lookback = lookback
        self.volume_decline_threshold = volume_decline_threshold
        self.price_movement_threshold = price_movement_threshold
    
    def calculate(
        self,
        df: pd.DataFrame,
        side: Optional[str] = None
    ) -> pd.Series:
        """
        Рассчитывает индикатор Volume Exhaustion
        
        Args:
            df: DataFrame с OHLCV данными
            side: 'long' или 'short' для направления анализа
            
        Returns:
            Series с значениями exhaustion (0-1, где 1 = полное исчерпание)
        """
        try:
            if len(df) < self.lookback + 1:
                return pd.Series(index=df.index, dtype=float)
            
            # Проверяем наличие необходимых колонок
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                logger.error("Отсутствуют необходимые колонки для расчета Volume Exhaustion")
                return pd.Series(index=df.index, dtype=float)
            
            exhaustion_values = pd.Series(index=df.index, dtype=float)
            
            for i in range(self.lookback, len(df)):
                # Рассчитываем средний объем за период
                avg_volume = df['volume'].iloc[i - self.lookback:i].mean()
                current_volume = df['volume'].iloc[i]
                
                # Рассчитываем движение цены
                if side == 'long':
                    # Для LONG: движение вверх
                    price_movement = (df['close'].iloc[i] - df['close'].iloc[i - self.lookback]) / df['close'].iloc[i - self.lookback] * 100
                elif side == 'short':
                    # Для SHORT: движение вниз
                    price_movement = (df['close'].iloc[i - self.lookback] - df['close'].iloc[i]) / df['close'].iloc[i - self.lookback] * 100
                else:
                    # Для общего случая: абсолютное движение
                    price_movement = abs(df['close'].iloc[i] - df['close'].iloc[i - self.lookback]) / df['close'].iloc[i - self.lookback] * 100
                
                # Если движение достаточно большое
                if price_movement >= self.price_movement_threshold:
                    # Проверяем снижение объема
                    volume_decline = (avg_volume - current_volume) / avg_volume if avg_volume > 0 else 0
                    
                    # Если объем упал значительно, это исчерпание
                    if volume_decline >= self.volume_decline_threshold:
                        # Нормализуем значение (0-1)
                        exhaustion = min(1.0, volume_decline / self.volume_decline_threshold)
                        exhaustion_values.iloc[i] = exhaustion
                    else:
                        exhaustion_values.iloc[i] = 0.0
                else:
                    exhaustion_values.iloc[i] = 0.0
            
            return exhaustion_values
            
        except Exception as e:
            logger.error(f"Ошибка расчета Volume Exhaustion: {e}")
            return pd.Series(index=df.index, dtype=float)
    
    def is_exhausted(
        self,
        df: pd.DataFrame,
        i: int,
        side: Optional[str] = None,
        threshold: float = 0.7
    ) -> bool:
        """
        Проверяет, исчерпано ли движение
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            side: 'long' или 'short'
            threshold: Порог исчерпания (0.7 = 70%)
            
        Returns:
            True если движение исчерпано
        """
        try:
            if i < self.lookback:
                return False
            
            exhaustion = self.calculate(df, side=side)
            
            if len(exhaustion) > i:
                return exhaustion.iloc[i] >= threshold
            
            return False
            
        except Exception as e:
            logger.error(f"Ошибка проверки исчерпания: {e}")
            return False
    
    def get_exhaustion_level(
        self,
        df: pd.DataFrame,
        i: int,
        side: Optional[str] = None
    ) -> Optional[float]:
        """
        Получает уровень исчерпания (0-1)
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            side: 'long' или 'short'
            
        Returns:
            Уровень исчерпания или None
        """
        try:
            if i < self.lookback:
                return None
            
            exhaustion = self.calculate(df, side=side)
            
            if len(exhaustion) > i:
                return float(exhaustion.iloc[i])
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения уровня исчерпания: {e}")
            return None
    
    def get_signal(
        self,
        df: pd.DataFrame,
        i: int,
        side: Optional[str] = None
    ) -> Optional[str]:
        """
        Определяет сигнал на основе исчерпания
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            side: 'long' или 'short'
            
        Returns:
            'exit' если исчерпание, None если нет
        """
        try:
            if self.is_exhausted(df, i, side=side):
                return 'exit'
            return None
            
        except Exception as e:
            logger.error(f"Ошибка определения сигнала исчерпания: {e}")
            return None


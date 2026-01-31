"""
Liquidity Exhaustion - анализ исчерпания ликвидности

Показывает, когда крупные игроки завершают позиции.
Используется для раннего выхода и определения разворотов.
"""

import logging
from typing import Optional, Dict, Any
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class LiquidityExhaustion:
    """
    Liquidity Exhaustion - анализ исчерпания ликвидности
    
    Анализирует:
    - Снижение объема при движении
    - Узкие диапазоны цен (low volatility)
    - Снижение активности торгов
    """
    
    def __init__(
        self,
        lookback: int = 20,  # Период для сравнения
        volume_decline_threshold: float = 0.4,  # Порог снижения объема
        volatility_decline_threshold: float = 0.3,  # Порог снижения волатильности
    ):
        """
        Args:
            lookback: Количество свечей для сравнения
            volume_decline_threshold: Порог снижения объема (0.4 = 40%)
            volatility_decline_threshold: Порог снижения волатильности (0.3 = 30%)
        """
        self.lookback = lookback
        self.volume_decline_threshold = volume_decline_threshold
        self.volatility_decline_threshold = volatility_decline_threshold
    
    def calculate(
        self,
        df: pd.DataFrame,
        side: Optional[str] = None
    ) -> pd.Series:
        """
        Рассчитывает индикатор Liquidity Exhaustion
        
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
                logger.error("Отсутствуют необходимые колонки для расчета Liquidity Exhaustion")
                return pd.Series(index=df.index, dtype=float)
            
            exhaustion_values = pd.Series(index=df.index, dtype=float)
            
            for i in range(self.lookback, len(df)):
                # Рассчитываем средние значения за период
                avg_volume = df['volume'].iloc[i - self.lookback:i].mean()
                current_volume = df['volume'].iloc[i]
                
                # Рассчитываем волатильность (ATR-like)
                price_ranges = df['high'].iloc[i - self.lookback:i] - df['low'].iloc[i - self.lookback:i]
                avg_volatility = price_ranges.mean()
                current_volatility = df['high'].iloc[i] - df['low'].iloc[i]
                
                # Рассчитываем снижение объема
                volume_decline = (avg_volume - current_volume) / avg_volume if avg_volume > 0 else 0
                
                # Рассчитываем снижение волатильности
                volatility_decline = (avg_volatility - current_volatility) / avg_volatility if avg_volatility > 0 else 0
                
                # Комбинируем факторы
                volume_exhaustion = min(1.0, volume_decline / self.volume_decline_threshold) if volume_decline > 0 else 0.0
                volatility_exhaustion = min(1.0, volatility_decline / self.volatility_decline_threshold) if volatility_decline > 0 else 0.0
                
                # Общий exhaustion (взвешенное среднее)
                total_exhaustion = (volume_exhaustion * 0.6 + volatility_exhaustion * 0.4)
                exhaustion_values.iloc[i] = total_exhaustion
            
            return exhaustion_values
            
        except Exception as e:
            logger.error(f"Ошибка расчета Liquidity Exhaustion: {e}")
            return pd.Series(index=df.index, dtype=float)
    
    def is_exhausted(
        self,
        df: pd.DataFrame,
        i: int,
        side: Optional[str] = None,
        threshold: float = 0.6
    ) -> bool:
        """
        Проверяет, исчерпана ли ликвидность
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            side: 'long' или 'short'
            threshold: Порог исчерпания (0.6 = 60%)
            
        Returns:
            True если ликвидность исчерпана
        """
        try:
            if i < self.lookback:
                return False
            
            exhaustion = self.calculate(df, side=side)
            
            if len(exhaustion) > i:
                return exhaustion.iloc[i] >= threshold
            
            return False
            
        except Exception as e:
            logger.error(f"Ошибка проверки исчерпания ликвидности: {e}")
            return False
    
    def get_exhaustion_level(
        self,
        df: pd.DataFrame,
        i: int,
        side: Optional[str] = None
    ) -> Optional[float]:
        """
        Получает уровень исчерпания ликвидности (0-1)
        
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
        Определяет сигнал на основе исчерпания ликвидности
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            side: 'long' или 'short'
            
        Returns:
            'exit' если ликвидность исчерпана, None если нет
        """
        try:
            if self.is_exhausted(df, i, side=side):
                return 'exit'
            return None
            
        except Exception as e:
            logger.error(f"Ошибка определения сигнала исчерпания: {e}")
            return None


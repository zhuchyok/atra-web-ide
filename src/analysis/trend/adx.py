"""
ADX (Average Directional Index) - обертка над ta-lib

ADX измеряет силу тренда (не направление).
Показывает, стоит ли торговать по тренду.
"""

import logging
from typing import Optional, Tuple
import pandas as pd

logger = logging.getLogger(__name__)

# Импорт ta-lib
try:
    import ta
    TA_AVAILABLE = True
except ImportError:
    TA_AVAILABLE = False
    logger.warning("ta-lib недоступен для ADX")


class ADXAnalyzer:
    """
    ADX (Average Directional Index) - обертка над ta-lib
    
    ADX измеряет силу тренда:
    - ADX < 20: слабый тренд (боковик)
    - ADX 20-25: умеренный тренд
    - ADX > 25: сильный тренд
    """
    
    def __init__(self, period: int = 14):
        """
        Args:
            period: Период для расчета ADX (по умолчанию 14)
        """
        self.period = period
    
    def calculate(self, df: pd.DataFrame) -> pd.Series:
        """
        Рассчитывает ADX
        
        Args:
            df: DataFrame с OHLCV данными
            
        Returns:
            Series с ADX значениями
        """
        try:
            if not TA_AVAILABLE:
                return pd.Series(index=df.index, dtype=float)
            
            if len(df) < self.period + 1:
                return pd.Series(index=df.index, dtype=float)
            
            # Проверяем наличие необходимых колонок
            required_cols = ['high', 'low', 'close']
            if not all(col in df.columns for col in required_cols):
                logger.error("Отсутствуют необходимые колонки для расчета ADX")
                return pd.Series(index=df.index, dtype=float)
            
            # Используем ta-lib
            adx_indicator = ta.trend.ADXIndicator(
                df['high'], df['low'], df['close'], window=self.period
            )
            
            return adx_indicator.adx()
            
        except Exception as e:
            logger.error(f"Ошибка расчета ADX: {e}")
            return pd.Series(index=df.index, dtype=float)
    
    def get_value(self, df: pd.DataFrame, i: int) -> Optional[float]:
        """
        Получает текущее значение ADX
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            
        Returns:
            Значение ADX или None
        """
        try:
            adx = self.calculate(df)
            if len(adx) > i:
                value = adx.iloc[i]
                return float(value) if not pd.isna(value) else None
            return None
        except Exception as e:
            logger.error(f"Ошибка получения значения ADX: {e}")
            return None
    
    def is_strong_trend(self, df: pd.DataFrame, i: int, threshold: float = 25.0) -> bool:
        """
        Проверяет, есть ли сильный тренд
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            threshold: Порог силы тренда (по умолчанию 25)
            
        Returns:
            True если сильный тренд
        """
        try:
            adx = self.get_value(df, i)
            return adx is not None and adx > threshold
        except Exception as e:
            logger.error(f"Ошибка проверки силы тренда ADX: {e}")
            return False
    
    def is_weak_trend(self, df: pd.DataFrame, i: int, threshold: float = 20.0) -> bool:
        """
        Проверяет, слабый ли тренд (боковик)
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            threshold: Порог слабого тренда (по умолчанию 20)
            
        Returns:
            True если слабый тренд
        """
        try:
            adx = self.get_value(df, i)
            return adx is not None and adx < threshold
        except Exception as e:
            logger.error(f"Ошибка проверки слабого тренда ADX: {e}")
            return False
    
    def get_trend_direction(
        self,
        df: pd.DataFrame,
        i: int
    ) -> Optional[str]:
        """
        Определяет направление тренда (используя +DI и -DI)
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            
        Returns:
            'up' если восходящий, 'down' если нисходящий, None если неопределенно
        """
        try:
            if not TA_AVAILABLE:
                return None
            
            if len(df) < self.period + 1:
                return None
            
            # Используем ta-lib для получения +DI и -DI
            adx_indicator = ta.trend.ADXIndicator(
                df['high'], df['low'], df['close'], window=self.period
            )
            
            plus_di = adx_indicator.adx_pos()
            minus_di = adx_indicator.adx_neg()
            
            if len(plus_di) > i and len(minus_di) > i:
                plus_di_val = plus_di.iloc[i]
                minus_di_val = minus_di.iloc[i]
                
                if pd.isna(plus_di_val) or pd.isna(minus_di_val):
                    return None
                
                if plus_di_val > minus_di_val:
                    return 'up'
                elif minus_di_val > plus_di_val:
                    return 'down'
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка определения направления тренда ADX: {e}")
            return None


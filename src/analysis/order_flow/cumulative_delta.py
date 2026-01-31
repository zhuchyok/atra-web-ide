"""
Cumulative Delta Volume (CDV) - накопленная разница объемов покупок/продаж

Анализирует дисбаланс объема покупателей/продавцов, показывая реальное давление.
Используется для фильтрации входов, подтверждения тренда и раннего выхода.
"""

import logging
from typing import Optional, Dict, Any
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class CumulativeDeltaVolume:
    """
    Cumulative Delta Volume - накопленная разница объемов покупок/продаж
    
    Аппроксимация на основе OHLCV данных:
    - Если close > open: большая часть объема идет в покупки
    - Если close < open: большая часть объема идет в продажи
    - Если close ≈ open: объем распределяется по диапазону свечи
    """
    
    def __init__(self, lookback: int = 20, use_time_weighting: bool = True, time_decay: float = 0.95):
        """
        Args:
            lookback: Период для сравнения CDV (по умолчанию 20 свечей)
            use_time_weighting: Использовать временную взвешенность (недавние сделки важнее)
            time_decay: Коэффициент затухания для временной взвешенности (0.9-0.99)
        """
        self.lookback = lookback
        self.use_time_weighting = use_time_weighting
        self.time_decay = time_decay
    
    def calculate(self, df: pd.DataFrame) -> pd.Series:
        """
        Рассчитывает Cumulative Delta Volume
        
        Args:
            df: DataFrame с OHLCV данными (обязательные колонки: open, high, low, close, volume)
            
        Returns:
            Series с CDV значениями (накопленная разница объемов)
        """
        try:
            if len(df) == 0:
                return pd.Series(dtype=float)
            
            # Проверяем наличие необходимых колонок
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in df.columns for col in required_cols):
                logger.error("Отсутствуют необходимые колонки для расчета CDV")
                return pd.Series(index=df.index, dtype=float)
            
            # Определяем направление объема на каждой свече
            # Если свеча бычья (close > open) - большая часть объема в покупки
            # Если свеча медвежья (close < open) - большая часть объема в продажи
            # Если свеча нейтральная - распределяем по диапазону
            
            price_range = df['high'] - df['low']
            price_range = price_range.replace(0, 1e-10)  # Избегаем деления на ноль
            
            # Вычисляем долю объема, идущую в покупки
            # Если close > open: большая часть объема в покупки
            # Если close < open: большая часть объема в продажи
            buy_ratio = np.where(
                df['close'] > df['open'],
                # Бычья свеча: больше объема в покупки
                0.5 + (df['close'] - df['open']) / price_range * 0.5,
                np.where(
                    df['close'] < df['open'],
                    # Медвежья свеча: меньше объема в покупки
                    (df['close'] - df['low']) / price_range * 0.5,
                    # Нейтральная свеча: равномерное распределение
                    0.5
                )
            )
            
            # Ограничиваем значения от 0 до 1
            buy_ratio = np.clip(buy_ratio, 0.0, 1.0)
            
            # Вычисляем объемы покупок и продаж
            buy_volume = df['volume'] * buy_ratio
            sell_volume = df['volume'] * (1 - buy_ratio)
            
            # Накопленная разница (Delta)
            delta = buy_volume - sell_volume
            
            # Применяем временную взвешенность если включена
            if self.use_time_weighting:
                # Создаем веса: недавние свечи важнее
                weights = np.array([self.time_decay ** (len(delta) - 1 - i) for i in range(len(delta))])
                # Нормализуем веса
                weights = weights / weights.sum() * len(weights)
                # Применяем веса к дельте
                weighted_delta = delta * weights
                cdv = weighted_delta.cumsum()
            else:
                cdv = delta.cumsum()
            
            return pd.Series(cdv, index=df.index)
            
        except Exception as e:
            logger.error(f"Ошибка расчета Cumulative Delta Volume: {e}")
            return pd.Series(index=df.index, dtype=float)
    
    def get_signal(self, df: pd.DataFrame, i: int) -> Optional[str]:
        """
        Определяет сигнал на основе CDV
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            
        Returns:
            'long' если давление покупателей, 'short' если продавцов, None если нейтрально
        """
        try:
            if i < self.lookback:
                return None
            
            cdv = self.calculate(df)
            
            if len(cdv) <= i:
                return None
            
            current_cdv = cdv.iloc[i]
            prev_cdv = cdv.iloc[i - self.lookback] if i >= self.lookback else cdv.iloc[0]
            
            # Если CDV сильно вырос - давление покупателей
            if prev_cdv != 0:
                change_pct = (current_cdv - prev_cdv) / abs(prev_cdv) * 100
            else:
                change_pct = 0
            
            # Пороги для определения сигнала
            if change_pct > 10:  # CDV вырос более чем на 10%
                return 'long'
            elif change_pct < -10:  # CDV упал более чем на 10%
                return 'short'
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка определения сигнала CDV: {e}")
            return None
    
    def get_value(self, df: pd.DataFrame, i: int) -> Optional[float]:
        """
        Получает текущее значение CDV
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            
        Returns:
            Значение CDV или None
        """
        try:
            cdv = self.calculate(df)
            if len(cdv) > i:
                return float(cdv.iloc[i])
            return None
        except Exception as e:
            logger.error(f"Ошибка получения значения CDV: {e}")
            return None
    
    def detect_divergence(
        self,
        df: pd.DataFrame,
        i: int,
    ) -> Optional[Dict[str, Any]]:
        """
        Обнаруживает дивергенцию между CDV и ценой
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
        
        Returns:
            Dict с информацией о дивергенции или None
        """
        try:
            from src.analysis.order_flow.divergence_analyzer import DivergenceAnalyzer
            
            if i < self.lookback or i >= len(df):
                return None
            
            cdv = self.calculate(df)
            price_series = df['close']
            
            analyzer = DivergenceAnalyzer(lookback=self.lookback)
            divergence = analyzer.detect_divergence(price_series, cdv, i)
            
            if divergence is None:
                return None
            
            return {
                'divergence_type': divergence.divergence_type.value,
                'confidence': divergence.confidence,
                'price_trend': divergence.price_trend,
                'indicator_trend': divergence.indicator_trend,
                'start_index': divergence.start_index,
                'end_index': divergence.end_index,
            }
            
        except ImportError:
            logger.warning("DivergenceAnalyzer недоступен, дивергенции не анализируются")
            return None
        except Exception as e:
            logger.error(f"Ошибка обнаружения дивергенции CDV: {e}")
            return None


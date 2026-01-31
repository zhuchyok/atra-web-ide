"""
Institutional VWAP Calculator - расчет Volume Weighted Average Price с полосами стандартного отклонения
Аналог Premium VWAP индикатора TradingView
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, time

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class VWAPCalculator:
    """
    Калькулятор VWAP (Volume Weighted Average Price)
    
    Поддерживает:
    - Daily VWAP (сброс каждый день в 00:00 UTC)
    - Полосы стандартного отклонения (±1SD, ±2SD)
    - Определение зон перекупленности/перепроданности
    """
    
    def __init__(
        self,
        reset_time: str = "00:00:00",  # Время сброса для Daily VWAP (UTC)
        sd_multipliers: List[float] = None,  # Множители для полос стандартного отклонения
    ):
        """
        Args:
            reset_time: Время сброса VWAP в формате "HH:MM:SS" (UTC)
            sd_multipliers: Список множителей для полос SD (по умолчанию [1.0, 2.0])
        """
        self.reset_time = reset_time
        self.sd_multipliers = sd_multipliers or [1.0, 2.0]
        
        # Парсим время сброса
        try:
            hour, minute, second = map(int, reset_time.split(":"))
            self.reset_hour = hour
            self.reset_minute = minute
            self.reset_second = second
        except (ValueError, AttributeError):
            logger.warning("Неверный формат reset_time, используем 00:00:00")
            self.reset_hour = 0
            self.reset_minute = 0
            self.reset_second = 0
    
    def is_new_period(
        self,
        current_timestamp: pd.Timestamp,
        previous_timestamp: Optional[pd.Timestamp] = None,
    ) -> bool:
        """
        Проверяет, начался ли новый период (для Daily VWAP - новый день)
        
        Args:
            current_timestamp: Текущий timestamp
            previous_timestamp: Предыдущий timestamp (опционально)
        
        Returns:
            True если начался новый период
        """
        try:
            current_time = current_timestamp.time()
            reset_time_obj = time(self.reset_hour, self.reset_minute, self.reset_second)
            
            # Проверяем, прошло ли время сброса
            if current_time >= reset_time_obj:
                if previous_timestamp is None:
                    return True
                
                prev_time = previous_timestamp.time()
                # Если текущее время >= reset_time, а предыдущее < reset_time, то новый период
                if prev_time < reset_time_obj:
                    return True
            
            return False
            
        except Exception as e:
            logger.error("Ошибка проверки нового периода: %s", e)
            return False
    
    def calculate_daily_vwap(
        self,
        df: pd.DataFrame,
        price_col: str = "close",
        volume_col: str = "volume",
        high_col: str = "high",
        low_col: str = "low",
    ) -> pd.Series:
        """
        Рассчитывает Daily VWAP с автоматическим сбросом каждый день
        
        Args:
            df: DataFrame с OHLCV данными и индексом datetime
            price_col: Название колонки с ценой (используется typical price = (high+low+close)/3)
            volume_col: Название колонки с объемом
            high_col: Название колонки с high
            low_col: Название колонки с low
        
        Returns:
            Series с VWAP значениями
        """
        try:
            if len(df) == 0:
                return pd.Series(dtype=float)
            
            # Создаем копию для работы
            df_copy = df.copy()
            
            # Убеждаемся, что индекс - datetime
            if not isinstance(df_copy.index, pd.DatetimeIndex):
                logger.warning("Индекс не DatetimeIndex, пытаемся преобразовать")
                df_copy.index = pd.to_datetime(df_copy.index)
            
            # Рассчитываем typical price (среднее high, low, close)
            typical_price = (
                df_copy[high_col] + df_copy[low_col] + df_copy[price_col]
            ) / 3.0
            
            # Рассчитываем price * volume
            price_volume = typical_price * df_copy[volume_col]
            
            # Инициализируем результат
            vwap_values = pd.Series(index=df_copy.index, dtype=float)
            cumulative_price_volume = 0.0
            cumulative_volume = 0.0
            
            # Предыдущий timestamp для проверки сброса
            prev_timestamp = None
            
            for i, (timestamp, row) in enumerate(df_copy.iterrows()):
                # Проверяем, начался ли новый период
                if prev_timestamp is not None and self.is_new_period(timestamp, prev_timestamp):
                    # Сбрасываем накопленные значения
                    cumulative_price_volume = 0.0
                    cumulative_volume = 0.0
                
                # Добавляем текущие значения
                cumulative_price_volume += price_volume.iloc[i]
                cumulative_volume += df_copy[volume_col].iloc[i]
                
                # Рассчитываем VWAP
                if cumulative_volume > 0:
                    vwap_values.iloc[i] = cumulative_price_volume / cumulative_volume
                else:
                    vwap_values.iloc[i] = typical_price.iloc[i]  # Fallback на typical price
                
                prev_timestamp = timestamp
            
            return vwap_values
            
        except Exception as e:
            logger.error("Ошибка расчета Daily VWAP: %s", e)
            return pd.Series(index=df.index, dtype=float)
    
    def calculate_vwap_bands(
        self,
        vwap: pd.Series,
        df: pd.DataFrame,
        price_col: str = "close",
        volume_col: str = "volume",
        high_col: str = "high",
        low_col: str = "low",
    ) -> Dict[str, pd.Series]:
        """
        Рассчитывает полосы стандартного отклонения для VWAP
        
        Args:
            vwap: Series с VWAP значениями
            df: DataFrame с OHLCV данными
            price_col: Название колонки с ценой
            volume_col: Название колонки с объемом
            high_col: Название колонки с high
            low_col: Название колонки с low
        
        Returns:
            Dict с полосами: {
                'vwap': Series с VWAP,
                'upper_band_1': Series с верхней полосой 1SD,
                'lower_band_1': Series с нижней полосой 1SD,
                'upper_band_2': Series с верхней полосой 2SD,
                'lower_band_2': Series с нижней полосой 2SD,
            }
        """
        try:
            if len(vwap) == 0 or len(df) == 0:
                return {
                    'vwap': pd.Series(dtype=float),
                    'upper_band_1': pd.Series(dtype=float),
                    'lower_band_1': pd.Series(dtype=float),
                    'upper_band_2': pd.Series(dtype=float),
                    'lower_band_2': pd.Series(dtype=float),
                }
            
            # Рассчитываем typical price
            typical_price = (
                df[high_col] + df[low_col] + df[price_col]
            ) / 3.0
            
            # Инициализируем результат
            std_dev_values = pd.Series(index=df.index, dtype=float)
            cumulative_squared_dev = 0.0
            cumulative_volume = 0.0
            
            # Предыдущий timestamp для проверки сброса
            prev_timestamp = None
            
            for i, (timestamp, row) in enumerate(df.iterrows()):
                # Проверяем, начался ли новый период
                if prev_timestamp is not None and self.is_new_period(timestamp, prev_timestamp):
                    # Сбрасываем накопленные значения
                    cumulative_squared_dev = 0.0
                    cumulative_volume = 0.0
                
                # Добавляем текущие значения
                vwap_val = vwap.iloc[i]
                if not pd.isna(vwap_val):
                    deviation = typical_price.iloc[i] - vwap_val
                    volume = df[volume_col].iloc[i]
                    cumulative_squared_dev += (deviation ** 2) * volume
                    cumulative_volume += volume
                
                # Рассчитываем стандартное отклонение (взвешенное по объему)
                if cumulative_volume > 0 and i > 0:
                    variance = cumulative_squared_dev / cumulative_volume
                    std_dev_values.iloc[i] = np.sqrt(variance)
                else:
                    std_dev_values.iloc[i] = 0.0
                
                prev_timestamp = timestamp
            
            # Рассчитываем полосы
            sd_mult_1 = self.sd_multipliers[0] if len(self.sd_multipliers) > 0 else 1.0
            sd_mult_2 = self.sd_multipliers[1] if len(self.sd_multipliers) > 1 else 2.0
            
            upper_band_1 = vwap + (std_dev_values * sd_mult_1)
            lower_band_1 = vwap - (std_dev_values * sd_mult_1)
            upper_band_2 = vwap + (std_dev_values * sd_mult_2)
            lower_band_2 = vwap - (std_dev_values * sd_mult_2)
            
            return {
                'vwap': vwap,
                'upper_band_1': upper_band_1,
                'lower_band_1': lower_band_1,
                'upper_band_2': upper_band_2,
                'lower_band_2': lower_band_2,
                'std_dev': std_dev_values,
            }
            
        except Exception as e:
            logger.error("Ошибка расчета VWAP полос: %s", e)
            return {
                'vwap': vwap,
                'upper_band_1': pd.Series(dtype=float),
                'lower_band_1': pd.Series(dtype=float),
                'upper_band_2': pd.Series(dtype=float),
                'lower_band_2': pd.Series(dtype=float),
                'std_dev': pd.Series(dtype=float),
            }
    
    def get_vwap_zones(
        self,
        current_price: float,
        vwap: float,
        upper_band_1: float,
        lower_band_1: float,
        upper_band_2: float,
        lower_band_2: float,
    ) -> Dict[str, Any]:
        """
        Определяет зону перекупленности/перепроданности относительно VWAP
        
        Args:
            current_price: Текущая цена
            vwap: Значение VWAP
            upper_band_1: Верхняя полоса 1SD
            lower_band_1: Нижняя полоса 1SD
            upper_band_2: Верхняя полоса 2SD
            lower_band_2: Нижняя полоса 2SD
        
        Returns:
            Dict с информацией о зоне:
            {
                'zone': 'extreme_overbought' | 'overbought' | 'neutral' | 'oversold' | 'extreme_oversold',
                'distance_from_vwap_pct': процент отклонения от VWAP,
                'distance_from_vwap': абсолютное отклонение от VWAP,
            }
        """
        try:
            if pd.isna(vwap) or vwap == 0:
                return {
                    'zone': 'neutral',
                    'distance_from_vwap_pct': 0.0,
                    'distance_from_vwap': 0.0,
                }
            
            distance = current_price - vwap
            distance_pct = (distance / vwap) * 100
            
            # Определяем зону
            if current_price >= upper_band_2:
                zone = 'extreme_overbought'
            elif current_price >= upper_band_1:
                zone = 'overbought'
            elif current_price <= lower_band_2:
                zone = 'extreme_oversold'
            elif current_price <= lower_band_1:
                zone = 'oversold'
            else:
                zone = 'neutral'
            
            return {
                'zone': zone,
                'distance_from_vwap_pct': distance_pct,
                'distance_from_vwap': distance,
            }
            
        except Exception as e:
            logger.error("Ошибка определения зоны VWAP: %s", e)
            return {
                'zone': 'neutral',
                'distance_from_vwap_pct': 0.0,
                'distance_from_vwap': 0.0,
            }


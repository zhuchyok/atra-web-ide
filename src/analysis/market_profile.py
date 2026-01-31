"""
Market Profile (TPO - Time Price Opportunity) - анализ распределения времени по ценам

Показывает, где цена проводила больше времени, определяет более точные POC и value area
на основе временной компоненты в дополнение к Volume Profile.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from functools import lru_cache

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Попытка импорта кэша
try:
    from src.core.cache import TTLCache
    CACHE_AVAILABLE = True
    # Кэш для TPO профилей (TTL 120 секунд)
    _tpo_cache = TTLCache(default_ttl=120)
except ImportError:
    CACHE_AVAILABLE = False
    _tpo_cache = None


class TimePriceOpportunity:
    """
    Time Price Opportunity (TPO) - анализ времени на каждом уровне цены
    
    Определяет:
    - TPO Profile - распределение времени по ценам
    - TPO POC - Point of Control на основе времени
    - TPO Value Area - зоны высокой стоимости на основе времени
    """
    
    def __init__(
        self,
        bins: int = 50,
        value_area_pct: float = 0.70,
        default_lookback: int = 100,
    ):
        """
        Args:
            bins: Количество бинов для TPO профиля
            value_area_pct: Процент времени для Value Area (по умолчанию 70%)
            default_lookback: Дефолтный lookback период
        """
        self.bins = bins
        self.value_area_pct = value_area_pct
        self.default_lookback = default_lookback
    
    def calculate_tpo_profile(
        self,
        df: pd.DataFrame,
        lookback_periods: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Рассчитывает TPO профиль для заданного периода
        
        TPO профиль показывает, где цена проводила больше времени
        
        Args:
            df: DataFrame с OHLCV данными (должен иметь индекс datetime)
            lookback_periods: Количество свечей для анализа
        
        Returns:
            Dict с информацией о TPO профиле
        """
        try:
            if lookback_periods is None:
                lookback_periods = self.default_lookback
            
            if len(df) < lookback_periods:
                lookback_periods = len(df)
            
            # Попытка получить из кэша
            if CACHE_AVAILABLE and _tpo_cache is not None:
                cache_key = f"tpo_{lookback_periods}_{len(df)}_{hash(tuple(df.tail(lookback_periods).values.tobytes()))}"
                cached_result = _tpo_cache.get(cache_key)
                if cached_result is not None:
                    return cached_result
            
            recent_df = df.tail(lookback_periods).copy()
            
            if len(recent_df) == 0:
                return {
                    "tpo_poc": None,
                    "tpo_value_area_high": None,
                    "tpo_value_area_low": None,
                    "tpo_profile": {},
                }
            
            # Собираем все цены с их временными весами
            # Время на каждом уровне цены пропорционально диапазону свечи
            price_time_pairs = []
            
            for _, row in recent_df.iterrows():
                price_range = row['high'] - row['low']
                if price_range == 0:
                    # Если свеча без движения, все время на close
                    price_time_pairs.append((row['close'], 1.0))
                else:
                    # Распределяем время равномерно по диапазону свечи
                    # Используем несколько точек внутри свечи
                    num_points = max(5, int(price_range / (row['close'] * 0.001)))
                    time_per_point = 1.0 / num_points
                    
                    for i in range(num_points):
                        price = row['low'] + (row['high'] - row['low']) * (i / (num_points - 1)) if num_points > 1 else row['close']
                        price_time_pairs.append((price, time_per_point))
            
            if not price_time_pairs:
                return {
                    "tpo_poc": None,
                    "tpo_value_area_high": None,
                    "tpo_value_area_low": None,
                    "tpo_profile": {},
                }
            
            # Создаем гистограмму времени по ценам
            prices = [p[0] for p in price_time_pairs]
            times = [p[1] for p in price_time_pairs]
            
            # Определяем диапазон цен
            min_price = min(prices)
            max_price = max(prices)
            
            if min_price == max_price:
                return {
                    "tpo_poc": min_price,
                    "tpo_value_area_high": min_price,
                    "tpo_value_area_low": min_price,
                    "tpo_profile": {min_price: sum(times)},
                }
            
            # Создаем бины
            bin_edges = np.linspace(min_price, max_price, self.bins + 1)
            bin_times, _ = np.histogram(prices, bins=bin_edges, weights=times)
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
            
            # Находим TPO POC (Point of Control) - бин с максимальным временем
            poc_idx = np.argmax(bin_times)
            tpo_poc = bin_centers[poc_idx]
            poc_time = bin_times[poc_idx]
            
            # Рассчитываем TPO Value Area (70% времени)
            total_time = sum(bin_times)
            target_time = total_time * self.value_area_pct
            
            # Находим бины, которые входят в Value Area
            sorted_indices = np.argsort(bin_times)[::-1]  # От большего к меньшему
            cumulative_time = 0
            value_area_indices = []
            
            for idx in sorted_indices:
                cumulative_time += bin_times[idx]
                value_area_indices.append(idx)
                if cumulative_time >= target_time:
                    break
            
            value_area_indices.sort()
            tpo_value_area_low = bin_centers[value_area_indices[0]]
            tpo_value_area_high = bin_centers[value_area_indices[-1]]
            
            # Создаем TPO профиль
            tpo_profile = {
                float(center): float(time) for center, time in zip(bin_centers, bin_times) if time > 0
            }
            
            result = {
                "tpo_poc": float(tpo_poc),
                "tpo_poc_time": float(poc_time),
                "tpo_value_area_high": float(tpo_value_area_high),
                "tpo_value_area_low": float(tpo_value_area_low),
                "tpo_profile": tpo_profile,
                "total_time": float(total_time),
            }
            
            # Сохранение в кэш
            if CACHE_AVAILABLE and _tpo_cache is not None:
                cache_key = f"tpo_{lookback_periods}_{len(df)}_{hash(tuple(df.tail(lookback_periods).values.tobytes()))}"
                _tpo_cache.set(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка расчета TPO профиля: {e}")
            return {
                "tpo_poc": None,
                "tpo_value_area_high": None,
                "tpo_value_area_low": None,
                "tpo_profile": {},
            }
    
    def get_tpo_poc(
        self,
        df: pd.DataFrame,
        lookback_periods: Optional[int] = None,
    ) -> Optional[float]:
        """
        Получает TPO POC (Point of Control на основе времени)
        
        Args:
            df: DataFrame с OHLCV данными
            lookback_periods: Количество свечей для анализа
        
        Returns:
            TPO POC цена или None
        """
        try:
            profile = self.calculate_tpo_profile(df, lookback_periods)
            return profile.get("tpo_poc")
        except Exception as e:
            logger.error(f"Ошибка получения TPO POC: {e}")
            return None
    
    def combine_with_volume_profile(
        self,
        volume_profile: Dict[str, Any],
        tpo_profile: Dict[str, Any],
        weight_volume: float = 0.6,
        weight_time: float = 0.4,
    ) -> Dict[str, Any]:
        """
        Комбинирует Volume Profile и TPO Profile для более точного POC
        
        Args:
            volume_profile: Результат Volume Profile
            tpo_profile: Результат TPO Profile
            weight_volume: Вес Volume Profile (по умолчанию 0.6)
            weight_time: Вес TPO Profile (по умолчанию 0.4)
        
        Returns:
            Комбинированный профиль с улучшенным POC
        """
        try:
            volume_poc = volume_profile.get("poc")
            tpo_poc = tpo_profile.get("tpo_poc")
            
            if volume_poc is None and tpo_poc is None:
                return {
                    "combined_poc": None,
                    "volume_poc": None,
                    "tpo_poc": None,
                }
            
            if volume_poc is None:
                return {
                    "combined_poc": tpo_poc,
                    "volume_poc": None,
                    "tpo_poc": tpo_poc,
                }
            
            if tpo_poc is None:
                return {
                    "combined_poc": volume_poc,
                    "volume_poc": volume_poc,
                    "tpo_poc": None,
                }
            
            # Взвешенное среднее
            combined_poc = (volume_poc * weight_volume + tpo_poc * weight_time) / (weight_volume + weight_time)
            
            return {
                "combined_poc": float(combined_poc),
                "volume_poc": float(volume_poc),
                "tpo_poc": float(tpo_poc),
                "weight_volume": weight_volume,
                "weight_time": weight_time,
            }
            
        except Exception as e:
            logger.error(f"Ошибка комбинирования профилей: {e}")
            return {
                "combined_poc": None,
                "volume_poc": volume_profile.get("poc"),
                "tpo_poc": tpo_profile.get("tpo_poc"),
            }


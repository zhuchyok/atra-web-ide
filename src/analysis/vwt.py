"""
Volume-Weighted Time (VWT) - взвешивание времени по объему

Комбинирует Volume Profile с временной компонентой для более точного определения POC.
Показывает, где цена проводила больше времени при большом объеме.
"""

import logging
from typing import Dict, List, Optional, Any
from functools import lru_cache

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Попытка импорта кэша
try:
    from src.core.cache import TTLCache
    CACHE_AVAILABLE = True
    # Кэш для VWT профилей (TTL 120 секунд)
    _vwt_cache = TTLCache(default_ttl=120)
except ImportError:
    CACHE_AVAILABLE = False
    _vwt_cache = None


class VolumeWeightedTime:
    """
    Volume-Weighted Time (VWT) - взвешивание времени по объему
    
    Определяет:
    - VWT Profile - распределение времени взвешенное по объему
    - VWT POC - Point of Control на основе VWT
    - Комбинирование с Volume Profile для более точного POC
    """
    
    def __init__(
        self,
        bins: int = 50,
        value_area_pct: float = 0.70,
        default_lookback: int = 100,
    ):
        """
        Args:
            bins: Количество бинов для VWT профиля
            value_area_pct: Процент для Value Area
            default_lookback: Дефолтный lookback период
        """
        self.bins = bins
        self.value_area_pct = value_area_pct
        self.default_lookback = default_lookback
    
    def calculate_vwt(
        self,
        df: pd.DataFrame,
        lookback_periods: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Рассчитывает Volume-Weighted Time профиль
        
        VWT = время на уровне цены × объем на этом уровне
        
        Args:
            df: DataFrame с OHLCV данными
            lookback_periods: Количество свечей для анализа
        
        Returns:
            Dict с информацией о VWT профиле
        """
        try:
            if lookback_periods is None:
                lookback_periods = self.default_lookback
            
            if len(df) < lookback_periods:
                lookback_periods = len(df)
            
            # Попытка получить из кэша
            if CACHE_AVAILABLE and _vwt_cache is not None:
                cache_key = f"vwt_{lookback_periods}_{len(df)}_{hash(tuple(df.tail(lookback_periods).values.tobytes()))}"
                cached_result = _vwt_cache.get(cache_key)
                if cached_result is not None:
                    return cached_result
            
            recent_df = df.tail(lookback_periods).copy()
            
            if len(recent_df) == 0:
                return {
                    "vwt_poc": None,
                    "vwt_value_area_high": None,
                    "vwt_value_area_low": None,
                    "vwt_profile": {},
                }
            
            # Собираем все цены с их временными весами, взвешенными по объему
            price_vwt_pairs = []
            
            for _, row in recent_df.iterrows():
                price_range = row['high'] - row['low']
                volume = row.get('volume', 1.0)
                
                if price_range == 0:
                    # Если свеча без движения, все время на close
                    price_vwt_pairs.append((row['close'], 1.0 * volume))
                else:
                    # Распределяем время равномерно по диапазону свечи
                    # Взвешиваем по объему
                    num_points = max(5, int(price_range / (row['close'] * 0.001)))
                    time_per_point = 1.0 / num_points
                    vwt_per_point = time_per_point * volume  # Взвешиваем время по объему
                    
                    for i in range(num_points):
                        price = row['low'] + (row['high'] - row['low']) * (i / (num_points - 1)) if num_points > 1 else row['close']
                        price_vwt_pairs.append((price, vwt_per_point))
            
            if not price_vwt_pairs:
                return {
                    "vwt_poc": None,
                    "vwt_value_area_high": None,
                    "vwt_value_area_low": None,
                    "vwt_profile": {},
                }
            
            # Создаем гистограмму VWT по ценам
            prices = [p[0] for p in price_vwt_pairs]
            vwt_values = [p[1] for p in price_vwt_pairs]
            
            # Определяем диапазон цен
            min_price = min(prices)
            max_price = max(prices)
            
            if min_price == max_price:
                return {
                    "vwt_poc": min_price,
                    "vwt_value_area_high": min_price,
                    "vwt_value_area_low": min_price,
                    "vwt_profile": {min_price: sum(vwt_values)},
                }
            
            # Создаем бины
            bin_edges = np.linspace(min_price, max_price, self.bins + 1)
            bin_vwt, _ = np.histogram(prices, bins=bin_edges, weights=vwt_values)
            bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
            
            # Находим VWT POC (Point of Control) - бин с максимальным VWT
            poc_idx = np.argmax(bin_vwt)
            vwt_poc = bin_centers[poc_idx]
            poc_vwt = bin_vwt[poc_idx]
            
            # Рассчитываем VWT Value Area (70% VWT)
            total_vwt = sum(bin_vwt)
            target_vwt = total_vwt * self.value_area_pct
            
            # Находим бины, которые входят в Value Area
            sorted_indices = np.argsort(bin_vwt)[::-1]  # От большего к меньшему
            cumulative_vwt = 0
            value_area_indices = []
            
            for idx in sorted_indices:
                cumulative_vwt += bin_vwt[idx]
                value_area_indices.append(idx)
                if cumulative_vwt >= target_vwt:
                    break
            
            value_area_indices.sort()
            vwt_value_area_low = bin_centers[value_area_indices[0]]
            vwt_value_area_high = bin_centers[value_area_indices[-1]]
            
            # Создаем VWT профиль
            vwt_profile = {
                float(center): float(vwt) for center, vwt in zip(bin_centers, bin_vwt) if vwt > 0
            }
            
            result = {
                "vwt_poc": float(vwt_poc),
                "vwt_poc_value": float(poc_vwt),
                "vwt_value_area_high": float(vwt_value_area_high),
                "vwt_value_area_low": float(vwt_value_area_low),
                "vwt_profile": vwt_profile,
                "total_vwt": float(total_vwt),
            }
            
            # Сохранение в кэш
            if CACHE_AVAILABLE and _vwt_cache is not None:
                cache_key = f"vwt_{lookback_periods}_{len(df)}_{hash(tuple(df.tail(lookback_periods).values.tobytes()))}"
                _vwt_cache.set(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка расчета VWT: {e}")
            return {
                "vwt_poc": None,
                "vwt_value_area_high": None,
                "vwt_value_area_low": None,
                "vwt_profile": {},
            }
    
    def combine_with_volume_profile(
        self,
        volume_profile: Dict[str, Any],
        vwt_profile: Dict[str, Any],
        weight_volume: float = 0.5,
        weight_vwt: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Комбинирует Volume Profile и VWT Profile для более точного POC
        
        Args:
            volume_profile: Результат Volume Profile
            vwt_profile: Результат VWT Profile
            weight_volume: Вес Volume Profile
            weight_vwt: Вес VWT Profile
        
        Returns:
            Комбинированный профиль с улучшенным POC
        """
        try:
            volume_poc = volume_profile.get("poc")
            vwt_poc = vwt_profile.get("vwt_poc")
            
            if volume_poc is None and vwt_poc is None:
                return {
                    "combined_poc": None,
                    "volume_poc": None,
                    "vwt_poc": None,
                }
            
            if volume_poc is None:
                return {
                    "combined_poc": vwt_poc,
                    "volume_poc": None,
                    "vwt_poc": vwt_poc,
                }
            
            if vwt_poc is None:
                return {
                    "combined_poc": volume_poc,
                    "volume_poc": volume_poc,
                    "vwt_poc": None,
                }
            
            # Взвешенное среднее
            total_weight = weight_volume + weight_vwt
            combined_poc = (volume_poc * weight_volume + vwt_poc * weight_vwt) / total_weight
            
            return {
                "combined_poc": float(combined_poc),
                "volume_poc": float(volume_poc),
                "vwt_poc": float(vwt_poc),
                "weight_volume": weight_volume,
                "weight_vwt": weight_vwt,
            }
            
        except Exception as e:
            logger.error(f"Ошибка комбинирования Volume Profile с VWT: {e}")
            return {
                "combined_poc": None,
                "volume_poc": volume_profile.get("poc"),
                "vwt_poc": vwt_profile.get("vwt_poc"),
            }


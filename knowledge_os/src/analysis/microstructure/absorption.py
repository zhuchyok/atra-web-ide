"""
Absorption Levels - уровни поглощения институционалов

Определяет уровни, где крупные игроки поглощают продажи/покупки.
Показывает сильные уровни поддержки/сопротивления институционалов.
"""

import logging
from typing import Optional, List, Dict, Any
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class AbsorptionLevels:
    """
    Absorption Levels - уровни поглощения институционалов
    
    Определяет уровни, где:
    - Крупные игроки поглощают продажи/покупки
    - Объем высокий, но цена не двигается
    - Это указывает на сильную поддержку/сопротивление
    """
    
    def __init__(
        self,
        lookback: int = 50,  # Период для анализа
        min_volume_ratio: float = 1.5,  # Минимальное соотношение объема
        price_stability_threshold: float = 0.3,  # Порог стабильности цены (%)
    ):
        """
        Args:
            lookback: Количество свечей для анализа
            min_volume_ratio: Минимальное соотношение объема к среднему
            price_stability_threshold: Порог стабильности цены (%)
        """
        self.lookback = lookback
        self.min_volume_ratio = min_volume_ratio
        self.price_stability_threshold = price_stability_threshold
    
    def detect_absorption_levels(
        self,
        df: pd.DataFrame,
        i: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """
        Определяет уровни поглощения
        
        Args:
            df: DataFrame с OHLCV данными
            i: Индекс текущей свечи (если None, использует последнюю)
        
        Returns:
            List уровней поглощения:
            [
                {
                    'price': float,
                    'type': 'support' | 'resistance',
                    'strength': float (0-1),
                    'volume_ratio': float,
                    'absorption_score': float (0-1)
                }
            ]
        """
        try:
            if i is None:
                i = len(df) - 1
            
            if i < self.lookback:
                return []
            
            # Берем окно для анализа
            window_df = df.iloc[i - self.lookback:i + 1].copy()
            
            # Рассчитываем средний объем
            avg_volume = window_df['volume'].mean()
            
            absorption_levels = []
            
            # Анализируем каждую свечу в окне
            for idx in range(len(window_df)):
                candle = window_df.iloc[idx]
                
                # Проверяем высокий объем
                volume_ratio = candle['volume'] / avg_volume if avg_volume > 0 else 0
                
                if volume_ratio < self.min_volume_ratio:
                    continue
                
                # Проверяем стабильность цены (маленькое тело свечи)
                body_size = abs(candle['close'] - candle['open'])
                price_range = candle['high'] - candle['low']
                
                if price_range == 0:
                    continue
                
                body_ratio = body_size / price_range
                
                # Если объем высокий, но тело маленькое - это поглощение
                if body_ratio < self.price_stability_threshold:
                    # Определяем тип поглощения
                    # Если цена в нижней части диапазона - поддержка (поглощение продаж)
                    # Если цена в верхней части диапазона - сопротивление (поглощение покупок)
                    
                    price_position = (candle['close'] - candle['low']) / price_range
                    
                    if price_position < 0.4:
                        # Поддержка - поглощение продаж
                        absorption_type = 'support'
                    elif price_position > 0.6:
                        # Сопротивление - поглощение покупок
                        absorption_type = 'resistance'
                    else:
                        # Нейтральная зона
                        continue
                    
                    # Рассчитываем силу поглощения
                    absorption_score = min(1.0, volume_ratio / 3.0) * (1 - body_ratio)
                    strength = min(1.0, absorption_score * 2.0)
                    
                    absorption_levels.append({
                        'price': float(candle['close']),
                        'type': absorption_type,
                        'strength': float(strength),
                        'volume_ratio': float(volume_ratio),
                        'absorption_score': float(absorption_score),
                        'timestamp': window_df.index[idx] if hasattr(window_df.index[idx], 'timestamp') else idx
                    })
            
            # Кластеризуем близкие уровни
            clustered_levels = self._cluster_absorption_levels(absorption_levels)
            
            # Сортируем по силе
            clustered_levels.sort(key=lambda x: x['strength'], reverse=True)
            
            return clustered_levels[:10]  # Топ-10 уровней
            
        except Exception as e:
            logger.error(f"Ошибка определения уровней поглощения: {e}")
            return []
    
    def _cluster_absorption_levels(
        self,
        levels: List[Dict[str, Any]],
        tolerance_pct: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Кластеризует близкие уровни поглощения
        
        Args:
            levels: List уровней
            tolerance_pct: Толерантность для кластеризации (%)
        
        Returns:
            List кластеризованных уровней
        """
        try:
            if len(levels) == 0:
                return []
            
            # Группируем по типу
            support_levels = [l for l in levels if l['type'] == 'support']
            resistance_levels = [l for l in levels if l['type'] == 'resistance']
            
            clustered = []
            
            # Кластеризуем поддержку
            if support_levels:
                clustered.extend(self._cluster_by_type(support_levels, tolerance_pct))
            
            # Кластеризуем сопротивление
            if resistance_levels:
                clustered.extend(self._cluster_by_type(resistance_levels, tolerance_pct))
            
            return clustered
            
        except Exception as e:
            logger.error(f"Ошибка кластеризации уровней поглощения: {e}")
            return levels
    
    def _cluster_by_type(
        self,
        levels: List[Dict[str, Any]],
        tolerance_pct: float
    ) -> List[Dict[str, Any]]:
        """Кластеризует уровни одного типа"""
        try:
            if len(levels) == 0:
                return []
            
            # Сортируем по цене
            sorted_levels = sorted(levels, key=lambda x: x['price'])
            
            clusters = []
            current_cluster = {
                'prices': [sorted_levels[0]['price']],
                'strengths': [sorted_levels[0]['strength']],
                'volume_ratios': [sorted_levels[0]['volume_ratio']],
                'scores': [sorted_levels[0]['absorption_score']],
                'type': sorted_levels[0]['type']
            }
            
            base_price = sorted_levels[0]['price']
            
            for level in sorted_levels[1:]:
                price_diff_pct = abs(level['price'] - base_price) / base_price * 100
                
                if price_diff_pct <= tolerance_pct:
                    # Добавляем в текущий кластер
                    current_cluster['prices'].append(level['price'])
                    current_cluster['strengths'].append(level['strength'])
                    current_cluster['volume_ratios'].append(level['volume_ratio'])
                    current_cluster['scores'].append(level['absorption_score'])
                else:
                    # Сохраняем кластер и начинаем новый
                    cluster_price = np.mean(current_cluster['prices'])
                    cluster_strength = np.mean(current_cluster['strengths'])
                    cluster_volume_ratio = np.mean(current_cluster['volume_ratios'])
                    cluster_score = np.mean(current_cluster['scores'])
                    
                    clusters.append({
                        'price': float(cluster_price),
                        'type': current_cluster['type'],
                        'strength': float(cluster_strength),
                        'volume_ratio': float(cluster_volume_ratio),
                        'absorption_score': float(cluster_score),
                        'touches': len(current_cluster['prices'])
                    })
                    
                    current_cluster = {
                        'prices': [level['price']],
                        'strengths': [level['strength']],
                        'volume_ratios': [level['volume_ratio']],
                        'scores': [level['absorption_score']],
                        'type': level['type']
                    }
                    base_price = level['price']
            
            # Добавляем последний кластер
            if len(current_cluster['prices']) > 0:
                cluster_price = np.mean(current_cluster['prices'])
                cluster_strength = np.mean(current_cluster['strengths'])
                cluster_volume_ratio = np.mean(current_cluster['volume_ratios'])
                cluster_score = np.mean(current_cluster['scores'])
                
                clusters.append({
                    'price': float(cluster_price),
                    'type': current_cluster['type'],
                    'strength': float(cluster_strength),
                    'volume_ratio': float(cluster_volume_ratio),
                    'absorption_score': float(cluster_score),
                    'touches': len(current_cluster['prices'])
                })
            
            return clusters
            
        except Exception as e:
            logger.error(f"Ошибка кластеризации по типу: {e}")
            return levels
    
    def is_near_absorption_level(
        self,
        current_price: float,
        absorption_levels: List[Dict[str, Any]],
        tolerance_pct: float = 1.0
    ) -> Optional[Dict[str, Any]]:
        """
        Проверяет, находится ли цена вблизи уровня поглощения
        
        Args:
            current_price: Текущая цена
            absorption_levels: List уровней поглощения
            tolerance_pct: Допустимое отклонение (%)
        
        Returns:
            Dict уровня или None
        """
        try:
            for level in absorption_levels:
                level_price = level['price']
                distance_pct = abs(current_price - level_price) / current_price * 100
                
                if distance_pct <= tolerance_pct:
                    return level
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка проверки близости к уровню поглощения: {e}")
            return None


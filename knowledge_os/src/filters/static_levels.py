#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Система определения статических уровней поддержки и сопротивления
Использует локальные экстремумы и кластеризацию для поиска значимых уровней
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


class StaticLevelsDetector:
    """Детектор статических уровней поддержки/сопротивления"""
    
    def __init__(self):
        self.cache = {}  # Кэш уровней для символов
        
    def find_levels(
        self, 
        df: pd.DataFrame, 
        lookback_period: int = 100,
        window: int = 5,
        min_touches: int = 2,
        tolerance_pct: float = 0.5
    ) -> Dict[str, List[Dict]]:
        """
        Находит статические уровни поддержки и сопротивления
        
        Args:
            df: DataFrame с OHLC данными
            lookback_period: Количество свечей для анализа
            window: Окно для поиска локальных экстремумов
            min_touches: Минимальное количество касаний уровня
            tolerance_pct: Процент толерантности для группировки уровней
        
        Returns:
            Dict с 'support' и 'resistance' уровнями
        """
        try:
            if len(df) < lookback_period:
                return {'support': [], 'resistance': []}
            
            # Берем последние N свечей
            recent_data = df.tail(lookback_period).copy()
            
            # Находим локальные экстремумы
            highs = self._find_local_highs(recent_data, window)
            lows = self._find_local_lows(recent_data, window)
            
            # Группируем близкие экстремумы в уровни
            resistance_levels = self._cluster_levels(highs, tolerance_pct, min_touches)
            support_levels = self._cluster_levels(lows, tolerance_pct, min_touches)
            
            return {
                'support': support_levels,
                'resistance': resistance_levels
            }
            
        except Exception as e:
            logger.error(f"❌ Ошибка поиска уровней: {e}")
            return {'support': [], 'resistance': []}
    
    def _find_local_highs(self, df: pd.DataFrame, window: int = 5) -> List[Dict]:
        """Находит локальные максимумы"""
        highs = []
        
        for i in range(window, len(df) - window):
            current_high = df['high'].iloc[i]
            
            # Проверяем, что это локальный максимум
            is_local_high = True
            for j in range(i - window, i + window + 1):
                if j != i and df['high'].iloc[j] >= current_high:
                    is_local_high = False
                    break
            
            if is_local_high:
                highs.append({
                    'price': current_high,
                    'index': i,
                    'timestamp': df.index[i] if hasattr(df.index[i], 'timestamp') else i,
                    'strength': 1
                })
        
        return highs
    
    def _find_local_lows(self, df: pd.DataFrame, window: int = 5) -> List[Dict]:
        """Находит локальные минимумы"""
        lows = []
        
        for i in range(window, len(df) - window):
            current_low = df['low'].iloc[i]
            
            # Проверяем, что это локальный минимум
            is_local_low = True
            for j in range(i - window, i + window + 1):
                if j != i and df['low'].iloc[j] <= current_low:
                    is_local_low = False
                    break
            
            if is_local_low:
                lows.append({
                    'price': current_low,
                    'index': i,
                    'timestamp': df.index[i] if hasattr(df.index[i], 'timestamp') else i,
                    'strength': 1
                })
        
        return lows
    
    def _cluster_levels(
        self, 
        extremes: List[Dict], 
        tolerance_pct: float = 0.5,
        min_touches: int = 2
    ) -> List[Dict]:
        """
        Группирует близкие экстремумы в значимые уровни
        """
        if not extremes:
            return []
        
        # Сортируем по цене
        extremes.sort(key=lambda x: x['price'])
        
        clusters = []
        current_cluster = [extremes[0]]
        
        for i in range(1, len(extremes)):
            current_price = extremes[i]['price']
            cluster_avg = np.mean([e['price'] for e in current_cluster])
            
            # Проверяем, близко ли к текущему кластеру
            if abs(current_price - cluster_avg) / cluster_avg * 100 <= tolerance_pct:
                current_cluster.append(extremes[i])
            else:
                # Сохраняем кластер если достаточно касаний
                if len(current_cluster) >= min_touches:
                    clusters.append({
                        'price': np.mean([e['price'] for e in current_cluster]),
                        'strength': len(current_cluster),
                        'touches': len(current_cluster),
                        'range': max(e['price'] for e in current_cluster) - min(e['price'] for e in current_cluster)
                    })
                
                # Начинаем новый кластер
                current_cluster = [extremes[i]]
        
        # Добавляем последний кластер
        if len(current_cluster) >= min_touches:
            clusters.append({
                'price': np.mean([e['price'] for e in current_cluster]),
                'strength': len(current_cluster),
                'touches': len(current_cluster),
                'range': max(e['price'] for e in current_cluster) - min(e['price'] for e in current_cluster)
            })
        
        # Сортируем по силе (количество касаний)
        clusters.sort(key=lambda x: x['strength'], reverse=True)
        
        return clusters
    
    def is_near_level(
        self, 
        price: float, 
        levels: List[Dict], 
        tolerance_pct: float = 1.0
    ) -> Tuple[bool, Optional[Dict]]:
        """
        Проверяет, находится ли цена близко к уровню
        
        Returns:
            (is_near, level_info) или (False, None)
        """
        for level in levels:
            distance_pct = abs(price - level['price']) / level['price'] * 100
            if distance_pct <= tolerance_pct:
                return True, level
        
        return False, None
    
    def get_nearest_support(self, price: float, levels: List[Dict]) -> Optional[float]:
        """Находит ближайший уровень поддержки (ниже текущей цены)"""
        supports = [l['price'] for l in levels if l['price'] < price]
        if not supports:
            return None
        # Ближайший уровень поддержки - это максимальный из тех, что ниже цены
        return max(supports)

    def get_nearest_resistance(self, price: float, levels: List[Dict]) -> Optional[float]:
        """Находит ближайший уровень сопротивления (выше текущей цены)"""
        resistances = [l['price'] for l in levels if l['price'] > price]
        if not resistances:
            return None
        # Ближайший уровень сопротивления - это минимальный из тех, что выше цены
        return min(resistances)

    def get_levels_quality_bonus(
        self,
        price: float,
        side: str,
        levels: Dict[str, List[Dict]],
        max_bonus: float = 0.15
    ) -> float:
        """
        Рассчитывает бонус к качеству сигнала на основе близости к уровням
        
        Args:
            price: Текущая цена
            side: "BUY" или "SELL"
            levels: Словарь с 'support' и 'resistance' уровнями
            max_bonus: Максимальный бонус (0.15 = +15%)
        
        Returns:
            Бонус к качеству (0.0 - max_bonus)
        """
        try:
            if side.upper() == "BUY":
                # Для LONG: ищем близость к поддержке
                is_near, support = self.is_near_level(price, levels.get('support', []), tolerance_pct=1.0)
                if is_near and support:
                    # Бонус пропорционален силе уровня
                    strength_bonus = min(support['strength'] * 0.02, max_bonus)
                    logger.debug(f"✅ Бонус к LONG: близость к поддержке (сила: {support['strength']}, бонус: {strength_bonus:.2%})")
                    return strength_bonus
                    
            elif side.upper() == "SELL":
                # Для SHORT: ищем близость к сопротивлению
                is_near, resistance = self.is_near_level(price, levels.get('resistance', []), tolerance_pct=1.0)
                if is_near and resistance:
                    # Бонус пропорционален силе уровня
                    strength_bonus = min(resistance['strength'] * 0.02, max_bonus)
                    logger.debug(f"✅ Бонус к SHORT: близость к сопротивлению (сила: {resistance['strength']}, бонус: {strength_bonus:.2%})")
                    return strength_bonus
            
            return 0.0
            
        except Exception as e:
            logger.error(f"❌ Ошибка расчета бонуса уровней: {e}")
            return 0.0


# Глобальный экземпляр детектора
_levels_detector = None

def get_levels_detector() -> StaticLevelsDetector:
    """Получение глобального экземпляра детектора"""
    global _levels_detector
    if _levels_detector is None:
        _levels_detector = StaticLevelsDetector()
    return _levels_detector

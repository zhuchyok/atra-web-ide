"""
Price Level Imbalance - анализ дисбаланса Order Flow по уровням цены

Анализирует дисбаланс покупок/продаж на каждом уровне цены внутри свечи,
определяет зоны максимального дисбаланса.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class PriceLevelImbalance:
    """
    Анализатор дисбаланса Order Flow по уровням цены
    
    Определяет:
    - Дисбаланс на каждом уровне цены внутри свечи
    - Зоны максимального дисбаланса
    - Направление дисбаланса (покупки/продажи)
    """
    
    def __init__(
        self,
        price_levels: int = 10,  # Количество уровней цены для анализа внутри свечи
        min_imbalance_threshold: float = 0.3,  # Минимальный порог дисбаланса
    ):
        """
        Args:
            price_levels: Количество уровней цены для анализа внутри свечи
            min_imbalance_threshold: Минимальный порог дисбаланса для определения зон
        """
        self.price_levels = price_levels
        self.min_imbalance_threshold = min_imbalance_threshold
    
    def calculate_imbalance_by_levels(
        self,
        df: pd.DataFrame,
        i: int,
    ) -> Dict[str, Any]:
        """
        Рассчитывает дисбаланс Order Flow по уровням цены
        
        Args:
            df: DataFrame с OHLCV данными
            i: Индекс текущей свечи
        
        Returns:
            Dict с информацией о дисбалансе по уровням
        """
        try:
            if i >= len(df):
                return {
                    'imbalance_by_levels': {},
                    'max_imbalance_zones': [],
                    'overall_imbalance': 0.0,
                }
            
            row = df.iloc[i]
            
            # Проверяем наличие необходимых колонок
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in row.index for col in required_cols):
                logger.error("Отсутствуют необходимые колонки для расчета дисбаланса по уровням")
                return {
                    'imbalance_by_levels': {},
                    'max_imbalance_zones': [],
                    'overall_imbalance': 0.0,
                }
            
            open_price = row['open']
            high_price = row['high']
            low_price = row['low']
            close_price = row['close']
            volume = row['volume']
            
            price_range = high_price - low_price
            if price_range == 0:
                # Если нет движения, весь объем на одной цене
                return {
                    'imbalance_by_levels': {float(close_price): 0.0},
                    'max_imbalance_zones': [],
                    'overall_imbalance': 0.0,
                }
            
            # Создаем уровни цены внутри свечи
            price_levels_list = np.linspace(low_price, high_price, self.price_levels)
            
            # Определяем направление объема на каждом уровне
            # Если close > open: больше объема в верхней части свечи
            # Если close < open: больше объема в нижней части свечи
            
            imbalance_by_levels = {}
            volume_per_level = volume / self.price_levels
            
            for level_price in price_levels_list:
                # Определяем долю объема на этом уровне
                # Близко к close - больше объема
                distance_from_close = abs(level_price - close_price) / price_range
                distance_from_open = abs(level_price - open_price) / price_range
                
                # Объем распределяется в зависимости от близости к close
                # (предполагаем, что close показывает, где была активность)
                if close_price > open_price:
                    # Бычья свеча: больше объема в верхней части
                    level_weight = 1.0 - distance_from_close * 0.5
                elif close_price < open_price:
                    # Медвежья свеча: больше объема в нижней части
                    level_weight = 1.0 - distance_from_close * 0.5
                else:
                    # Нейтральная свеча: равномерное распределение
                    level_weight = 1.0
                
                level_volume = volume_per_level * level_weight
                
                # Определяем дисбаланс на этом уровне
                # Если уровень выше close - больше продаж, ниже - больше покупок
                if level_price > close_price:
                    # Уровень выше close - больше продаж
                    imbalance = -level_volume * (level_price - close_price) / price_range
                elif level_price < close_price:
                    # Уровень ниже close - больше покупок
                    imbalance = level_volume * (close_price - level_price) / price_range
                else:
                    # Уровень на close - нейтрально
                    imbalance = 0.0
                
                imbalance_by_levels[float(level_price)] = float(imbalance)
            
            # Находим зоны максимального дисбаланса
            max_imbalance_zones = self._get_max_imbalance_zones(imbalance_by_levels)
            
            # Рассчитываем общий дисбаланс
            overall_imbalance = sum(imbalance_by_levels.values()) / len(imbalance_by_levels) if imbalance_by_levels else 0.0
            
            return {
                'imbalance_by_levels': imbalance_by_levels,
                'max_imbalance_zones': max_imbalance_zones,
                'overall_imbalance': float(overall_imbalance),
            }
            
        except Exception as e:
            logger.error(f"Ошибка расчета дисбаланса по уровням: {e}")
            return {
                'imbalance_by_levels': {},
                'max_imbalance_zones': [],
                'overall_imbalance': 0.0,
            }
    
    def _get_max_imbalance_zones(
        self,
        imbalance_by_levels: Dict[float, float],
    ) -> List[Dict[str, Any]]:
        """
        Определяет зоны максимального дисбаланса
        
        Args:
            imbalance_by_levels: Dict с дисбалансом по уровням
        
        Returns:
            List зон максимального дисбаланса
        """
        try:
            if not imbalance_by_levels:
                return []
            
            # Находим максимальный и минимальный дисбаланс
            max_imbalance = max(imbalance_by_levels.values())
            min_imbalance = min(imbalance_by_levels.values())
            
            max_abs_imbalance = max(abs(max_imbalance), abs(min_imbalance))
            
            if max_abs_imbalance < self.min_imbalance_threshold:
                return []
            
            zones = []
            
            # Находим уровни с максимальным дисбалансом
            for price, imbalance in imbalance_by_levels.items():
                if abs(imbalance) >= max_abs_imbalance * 0.7:  # 70% от максимума
                    zones.append({
                        'price': price,
                        'imbalance': imbalance,
                        'imbalance_pct': imbalance / max_abs_imbalance if max_abs_imbalance > 0 else 0.0,
                        'type': 'buy' if imbalance > 0 else 'sell',
                    })
            
            # Сортируем по абсолютному значению дисбаланса
            zones.sort(key=lambda x: abs(x['imbalance']), reverse=True)
            
            return zones[:5]  # Топ-5 зон
        
        except Exception as e:
            logger.error(f"Ошибка определения зон максимального дисбаланса: {e}")
            return []


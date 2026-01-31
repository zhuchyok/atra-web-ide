"""
Price Exhaustion Patterns - паттерны исчерпания движения

Определяет свечные паттерны, указывающие на исчерпание движения.
Используется для раннего выхода и flip сигналов.
"""

import logging
from typing import Optional, List, Dict, Any
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class PriceExhaustionPatterns:
    """
    Price Exhaustion Patterns - паттерны исчерпания движения
    
    Определяет паттерны:
    - Doji (неопределенность)
    - Shooting Star / Hammer (разворот)
    - Engulfing (поглощение)
    - Spinning Top (неопределенность)
    """
    
    def __init__(
        self,
        doji_threshold: float = 0.1,  # Порог для Doji (% от диапазона)
        wick_ratio: float = 2.0,  # Соотношение фитиля к телу
    ):
        """
        Args:
            doji_threshold: Порог для определения Doji (% от диапазона свечи)
            wick_ratio: Минимальное соотношение фитиля к телу для разворотных паттернов
        """
        self.doji_threshold = doji_threshold
        self.wick_ratio = wick_ratio
    
    def detect_patterns(
        self,
        df: pd.DataFrame,
        i: int
    ) -> Dict[str, Any]:
        """
        Определяет паттерны исчерпания на свече
        
        Args:
            df: DataFrame с OHLCV данными
            i: Индекс текущей свечи
            
        Returns:
            Dict с информацией о паттернах:
            {
                'doji': bool,
                'shooting_star': bool,
                'hammer': bool,
                'bearish_engulfing': bool,
                'bullish_engulfing': bool,
                'spinning_top': bool,
                'exhaustion_score': float (0-1)
            }
        """
        try:
            if i < 1 or i >= len(df):
                return self._empty_pattern_result()
            
            current = df.iloc[i]
            prev = df.iloc[i - 1]
            
            # Рассчитываем размеры свечи
            body_size = abs(current['close'] - current['open'])
            total_range = current['high'] - current['low']
            upper_wick = current['high'] - max(current['open'], current['close'])
            lower_wick = min(current['open'], current['close']) - current['low']
            
            # Избегаем деления на ноль
            if total_range == 0:
                return self._empty_pattern_result()
            
            patterns = {
                'doji': False,
                'shooting_star': False,
                'hammer': False,
                'bearish_engulfing': False,
                'bullish_engulfing': False,
                'spinning_top': False,
                'exhaustion_score': 0.0
            }
            
            # 1. Doji (неопределенность)
            if body_size / total_range <= self.doji_threshold:
                patterns['doji'] = True
                patterns['exhaustion_score'] += 0.3
            
            # 2. Shooting Star (медвежий разворот)
            is_bullish = current['close'] > current['open']
            if is_bullish and upper_wick >= body_size * self.wick_ratio and lower_wick < body_size * 0.5:
                patterns['shooting_star'] = True
                patterns['exhaustion_score'] += 0.4
            
            # 3. Hammer (бычий разворот)
            is_bearish = current['close'] < current['open']
            if is_bearish and lower_wick >= body_size * self.wick_ratio and upper_wick < body_size * 0.5:
                patterns['hammer'] = True
                patterns['exhaustion_score'] += 0.3
            
            # 4. Bearish Engulfing (медвежье поглощение)
            if (is_bearish and 
                prev['close'] > prev['open'] and  # Предыдущая бычья
                current['open'] > prev['close'] and  # Текущая открывается выше
                current['close'] < prev['open']):  # Текущая закрывается ниже
                patterns['bearish_engulfing'] = True
                patterns['exhaustion_score'] += 0.5
            
            # 5. Bullish Engulfing (бычье поглощение)
            if (is_bullish and 
                prev['close'] < prev['open'] and  # Предыдущая медвежья
                current['open'] < prev['close'] and  # Текущая открывается ниже
                current['close'] > prev['open']):  # Текущая закрывается выше
                patterns['bullish_engulfing'] = True
                patterns['exhaustion_score'] += 0.5
            
            # 6. Spinning Top (неопределенность)
            if (body_size / total_range < 0.3 and 
                upper_wick > body_size and 
                lower_wick > body_size):
                patterns['spinning_top'] = True
                patterns['exhaustion_score'] += 0.2
            
            # Ограничиваем exhaustion_score от 0 до 1
            patterns['exhaustion_score'] = min(1.0, patterns['exhaustion_score'])
            
            return patterns
            
        except Exception as e:
            logger.error(f"Ошибка определения паттернов исчерпания: {e}")
            return self._empty_pattern_result()
    
    def is_exhausted(
        self,
        df: pd.DataFrame,
        i: int,
        side: Optional[str] = None,
        threshold: float = 0.5
    ) -> bool:
        """
        Проверяет, есть ли паттерны исчерпания
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            side: 'long' или 'short' (для проверки противоположных паттернов)
            threshold: Порог exhaustion_score
            
        Returns:
            True если обнаружены паттерны исчерпания
        """
        try:
            patterns = self.detect_patterns(df, i)
            
            # Для LONG: ищем медвежьи паттерны
            if side == 'long':
                bearish_patterns = (
                    patterns['shooting_star'] or
                    patterns['bearish_engulfing'] or
                    patterns['doji']
                )
                return bearish_patterns or patterns['exhaustion_score'] >= threshold
            
            # Для SHORT: ищем бычьи паттерны
            elif side == 'short':
                bullish_patterns = (
                    patterns['hammer'] or
                    patterns['bullish_engulfing'] or
                    patterns['doji']
                )
                return bullish_patterns or patterns['exhaustion_score'] >= threshold
            
            # Общий случай: любой паттерн
            return patterns['exhaustion_score'] >= threshold
            
        except Exception as e:
            logger.error(f"Ошибка проверки исчерпания: {e}")
            return False
    
    def get_exhaustion_score(
        self,
        df: pd.DataFrame,
        i: int
    ) -> float:
        """
        Получает общий score исчерпания (0-1)
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            
        Returns:
            Score исчерпания (0-1)
        """
        try:
            patterns = self.detect_patterns(df, i)
            return patterns['exhaustion_score']
        except Exception as e:
            logger.error(f"Ошибка получения exhaustion score: {e}")
            return 0.0
    
    def _empty_pattern_result(self) -> Dict[str, Any]:
        """Возвращает пустой результат паттернов"""
        return {
            'doji': False,
            'shooting_star': False,
            'hammer': False,
            'bearish_engulfing': False,
            'bullish_engulfing': False,
            'spinning_top': False,
            'exhaustion_score': 0.0
        }


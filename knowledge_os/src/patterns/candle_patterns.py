"""
Candle Pattern Detector - обнаружение свечных паттернов для подтверждения входа
"""

import logging
from typing import Dict, Any, List, Optional

import pandas as pd
import numpy as np
import talib

logger = logging.getLogger(__name__)


class CandlePatternDetector:
    """
    Детектор свечных паттернов
    
    Обнаруживает:
    - Бычьи паттерны (для LONG)
    - Медвежьи паттерны (для SHORT)
    - Паттерны разворота
    """
    
    def __init__(self):
        pass
    
    def is_bullish_engulfing(self, df: pd.DataFrame, index: int = -1) -> bool:
        """
        Определяет бычье поглощение (Bullish Engulfing)
        
        Args:
            df: DataFrame с OHLCV данными
            index: Индекс свечи для проверки (по умолчанию последняя)
        
        Returns:
            True если обнаружено бычье поглощение
        """
        try:
            if len(df) < 2 or abs(index) > len(df):
                return False
            
            prev_candle = df.iloc[index - 1]
            current_candle = df.iloc[index]
            
            # Предыдущая свеча медвежья
            if prev_candle['close'] >= prev_candle['open']:
                return False
            
            # Текущая свеча бычья
            if current_candle['close'] <= current_candle['open']:
                return False
            
            # Текущая свеча поглощает предыдущую
            if (current_candle['open'] < prev_candle['close'] and
                current_candle['close'] > prev_candle['open']):
                return True
            
            return False
        except Exception as e:
            logger.debug("Ошибка проверки бычьего поглощения: %s", e)
            return False
    
    def is_bearish_engulfing(self, df: pd.DataFrame, index: int = -1) -> bool:
        """
        Определяет медвежье поглощение (Bearish Engulfing)
        
        Args:
            df: DataFrame с OHLCV данными
            index: Индекс свечи для проверки (по умолчанию последняя)
        
        Returns:
            True если обнаружено медвежье поглощение
        """
        try:
            if len(df) < 2 or abs(index) > len(df):
                return False
            
            prev_candle = df.iloc[index - 1]
            current_candle = df.iloc[index]
            
            # Предыдущая свеча бычья
            if prev_candle['close'] <= prev_candle['open']:
                return False
            
            # Текущая свеча медвежья
            if current_candle['close'] >= current_candle['open']:
                return False
            
            # Текущая свеча поглощает предыдущую
            if (current_candle['open'] > prev_candle['close'] and
                current_candle['close'] < prev_candle['open']):
                return True
            
            return False
        except Exception as e:
            logger.debug("Ошибка проверки медвежьего поглощения: %s", e)
            return False
    
    def is_hammer(self, df: pd.DataFrame, index: int = -1, body_ratio: float = 0.3) -> bool:
        """
        Определяет хаммер (Hammer) - бычий паттерн
        
        Args:
            df: DataFrame с OHLCV данными
            index: Индекс свечи для проверки
            body_ratio: Максимальное отношение тела к диапазону
        
        Returns:
            True если обнаружен хаммер
        """
        try:
            if len(df) < 1 or abs(index) > len(df):
                return False
            
            candle = df.iloc[index]
            body = abs(candle['close'] - candle['open'])
            range_size = candle['high'] - candle['low']
            
            if range_size == 0:
                return False
            
            # Маленькое тело
            if body / range_size > body_ratio:
                return False
            
            # Длинная нижняя тень (минимум 2x тела)
            lower_shadow = min(candle['open'], candle['close']) - candle['low']
            if lower_shadow < body * 2:
                return False
            
            # Короткая верхняя тень (меньше тела)
            upper_shadow = candle['high'] - max(candle['open'], candle['close'])
            if upper_shadow > body:
                return False
            
            return True
        except Exception as e:
            logger.debug("Ошибка проверки хаммера: %s", e)
            return False
    
    def is_shooting_star(self, df: pd.DataFrame, index: int = -1, body_ratio: float = 0.3) -> bool:
        """
        Определяет падающую звезду (Shooting Star) - медвежий паттерн
        
        Args:
            df: DataFrame с OHLCV данными
            index: Индекс свечи для проверки
            body_ratio: Максимальное отношение тела к диапазону
        
        Returns:
            True если обнаружена падающая звезда
        """
        try:
            if len(df) < 1 or abs(index) > len(df):
                return False
            
            candle = df.iloc[index]
            body = abs(candle['close'] - candle['open'])
            range_size = candle['high'] - candle['low']
            
            if range_size == 0:
                return False
            
            # Маленькое тело
            if body / range_size > body_ratio:
                return False
            
            # Длинная верхняя тень (минимум 2x тела)
            upper_shadow = candle['high'] - max(candle['open'], candle['close'])
            if upper_shadow < body * 2:
                return False
            
            # Короткая нижняя тень (меньше тела)
            lower_shadow = min(candle['open'], candle['close']) - candle['low']
            if lower_shadow > body:
                return False
            
            return True
        except Exception as e:
            logger.debug("Ошибка проверки падающей звезды: %s", e)
            return False
    
    def is_piercing_line(self, df: pd.DataFrame, index: int = -1) -> bool:
        """
        Определяет пронзающую линию (Piercing Line) - бычий паттерн
        
        Args:
            df: DataFrame с OHLCV данными
            index: Индекс свечи для проверки
        
        Returns:
            True если обнаружена пронзающая линия
        """
        try:
            if len(df) < 2 or abs(index) > len(df):
                return False
            
            prev_candle = df.iloc[index - 1]
            current_candle = df.iloc[index]
            
            # Предыдущая свеча медвежья
            if prev_candle['close'] >= prev_candle['open']:
                return False
            
            # Текущая свеча бычья
            if current_candle['close'] <= current_candle['open']:
                return False
            
            # Текущая свеча открывается ниже минимума предыдущей
            if current_candle['open'] >= prev_candle['low']:
                return False
            
            # Текущая свеча закрывается выше середины предыдущей
            prev_mid = (prev_candle['open'] + prev_candle['close']) / 2
            if current_candle['close'] > prev_mid:
                return True
            
            return False
        except Exception as e:
            logger.debug("Ошибка проверки пронзающей линии: %s", e)
            return False
    
    def detect_bullish_patterns(self, df: pd.DataFrame) -> Dict[str, bool]:
        """
        Обнаруживает все бычьи паттерны
        
        Args:
            df: DataFrame с OHLCV данными
        
        Returns:
            Dict с результатами обнаружения паттернов
        """
        try:
            return {
                "bullish_engulfing": self.is_bullish_engulfing(df),
                "hammer": self.is_hammer(df),
                "piercing_line": self.is_piercing_line(df),
            }
        except Exception as e:
            logger.error("❌ Ошибка обнаружения бычьих паттернов: %s", e)
            return {
                "bullish_engulfing": False,
                "hammer": False,
                "piercing_line": False,
            }
    
    def detect_bearish_patterns(self, df: pd.DataFrame) -> Dict[str, bool]:
        """
        Обнаруживает все медвежьи паттерны
        
        Args:
            df: DataFrame с OHLCV данными
        
        Returns:
            Dict с результатами обнаружения паттернов
        """
        try:
            return {
                "bearish_engulfing": self.is_bearish_engulfing(df),
                "shooting_star": self.is_shooting_star(df),
            }
        except Exception as e:
            logger.error("❌ Ошибка обнаружения медвежьих паттернов: %s", e)
            return {
                "bearish_engulfing": False,
                "shooting_star": False,
            }
    
    def has_bullish_pattern(self, df: pd.DataFrame) -> bool:
        """
        Проверяет наличие любого бычьего паттерна
        
        Args:
            df: DataFrame с OHLCV данными
        
        Returns:
            True если обнаружен хотя бы один бычий паттерн
        """
        patterns = self.detect_bullish_patterns(df)
        return any(patterns.values())
    
    def has_bearish_pattern(self, df: pd.DataFrame) -> bool:
        """
        Проверяет наличие любого медвежьего паттерна
        
        Args:
            df: DataFrame с OHLCV данными
        
        Returns:
            True если обнаружен хотя бы один медвежий паттерн
        """
        patterns = self.detect_bearish_patterns(df)
        return any(patterns.values())
    
    def get_pattern_score(self, df: pd.DataFrame, direction: str) -> float:
        """
        Рассчитывает оценку свечных паттернов (0.0 - 1.0)
        
        Args:
            df: DataFrame с OHLCV данными
            direction: "LONG" или "SHORT"
        
        Returns:
            Оценка паттернов (0.0 - 1.0)
        """
        try:
            if direction.upper() == "LONG":
                patterns = self.detect_bullish_patterns(df)
                # Каждый паттерн добавляет 0.33 к оценке
                score = sum(patterns.values()) * 0.33
                return min(1.0, score)
            elif direction.upper() == "SHORT":
                patterns = self.detect_bearish_patterns(df)
                score = sum(patterns.values()) * 0.5
                return min(1.0, score)
            else:
                return 0.0
        except Exception as e:
            logger.error("❌ Ошибка расчета оценки паттернов: %s", e)
            return 0.0

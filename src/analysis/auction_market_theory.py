"""
Auction Market Theory (AMT) - теория аукционного рынка

Анализирует баланс между покупателями и продавцами, определяет фазы рынка:
- Auction - активный аукцион, движение цены
- Balance - баланс, консолидация
- Imbalance - дисбаланс, готовность к движению

Используется для фильтрации входов и определения оптимальных точек входа.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
from functools import lru_cache

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Попытка импорта кэша
try:
    from src.core.cache import TTLCache
    CACHE_AVAILABLE = True
    # Кэш для AMT расчетов (TTL 60 секунд)
    _amt_cache = TTLCache(default_ttl=60)
except ImportError:
    CACHE_AVAILABLE = False
    _amt_cache = None


class MarketPhase(Enum):
    """Фазы рынка по Auction Market Theory"""
    AUCTION = "auction"  # Активный аукцион, движение цены
    BALANCE = "balance"  # Баланс, консолидация
    IMBALANCE = "imbalance"  # Дисбаланс, готовность к движению


class AuctionMarketTheory:
    """
    Auction Market Theory - анализ баланса и дисбаланса рынка
    
    Определяет:
    - Фазу рынка (auction/balance/imbalance)
    - Баланс между покупателями и продавцами
    - Уровни аукциона (точки контроля)
    """
    
    def __init__(
        self,
        lookback: int = 20,
        balance_threshold: float = 0.3,
        imbalance_threshold: float = 0.6,
    ):
        """
        Args:
            lookback: Период для анализа (по умолчанию 20 свечей)
            balance_threshold: Порог для определения баланса (0-1, чем меньше, тем строже)
            imbalance_threshold: Порог для определения дисбаланса (0-1, чем больше, тем строже)
        """
        self.lookback = lookback
        self.balance_threshold = balance_threshold
        self.imbalance_threshold = imbalance_threshold
    
    def calculate_balance_score(
        self,
        df: pd.DataFrame,
        i: int,
    ) -> Optional[float]:
        """
        Рассчитывает баланс между покупателями и продавцами
        
        Баланс = 0.5 означает равновесие
        Баланс > 0.5 означает преобладание покупателей
        Баланс < 0.5 означает преобладание продавцов
        
        Args:
            df: DataFrame с OHLCV данными
            i: Индекс текущей свечи
            
        Returns:
            Баланс от 0 до 1 (0.5 = равновесие) или None
        """
        try:
            # Попытка получить из кэша
            if CACHE_AVAILABLE and _amt_cache is not None:
                cache_key = f"balance_{i}_{len(df)}_{hash(tuple(df.iloc[i-self.lookback+1:i+1].values.tobytes()))}"
                cached_result = _amt_cache.get(cache_key)
                if cached_result is not None:
                    return cached_result
            if i < self.lookback or i >= len(df):
                return None
            
            # Берем последние lookback свечей
            window_df = df.iloc[i - self.lookback + 1:i + 1]
            
            if len(window_df) == 0:
                return None
            
            # Проверяем наличие необходимых колонок
            required_cols = ['open', 'high', 'low', 'close', 'volume']
            if not all(col in window_df.columns for col in required_cols):
                logger.error("Отсутствуют необходимые колонки для расчета баланса")
                return None
            
            # Рассчитываем объем покупок и продаж
            price_range = window_df['high'] - window_df['low']
            price_range = price_range.replace(0, 1e-10)
            
            # Определяем долю объема, идущую в покупки
            buy_ratio = np.where(
                window_df['close'] > window_df['open'],
                0.5 + (window_df['close'] - window_df['open']) / price_range * 0.5,
                np.where(
                    window_df['close'] < window_df['open'],
                    (window_df['close'] - window_df['low']) / price_range * 0.5,
                    0.5
                )
            )
            buy_ratio = np.clip(buy_ratio, 0.0, 1.0)
            
            # Взвешиваем по объему
            total_volume = window_df['volume'].sum()
            if total_volume == 0:
                result = 0.5  # Нейтральный баланс при отсутствии объема
            else:
                result = float((window_df['volume'] * buy_ratio).sum() / total_volume)
            
            # Сохранение в кэш
            if CACHE_AVAILABLE and _amt_cache is not None:
                cache_key = f"balance_{i}_{len(df)}_{hash(tuple(df.iloc[i-self.lookback+1:i+1].values.tobytes()))}"
                _amt_cache.set(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка расчета баланса: {e}")
            return None
    
    def _log_metrics(self, phase: Optional[MarketPhase], balance_score: Optional[float]):
        """Логирование метрик для мониторинга"""
        try:
            from src.metrics.decorators import record_filter_metrics, FilterType
            
            # Логируем метрики AMT
            if phase:
                logger.debug(
                    f"AMT Metrics: phase={phase.value}, balance_score={balance_score:.3f}"
                )
                
                # Запись метрик через систему метрик (если доступна)
                try:
                    # Можно добавить специальный FilterType для AMT или использовать существующий
                    record_filter_metrics(
                        filter_type=FilterType.ORDER_FLOW,  # Используем ближайший тип
                        passed=phase != MarketPhase.BALANCE,  # Balance блокирует сигналы
                        processing_time=0.0,  # Время будет измерено в фильтре
                    )
                except Exception:
                    pass  # Игнорируем ошибки метрик
        except ImportError:
            pass  # Метрики недоступны
    
    def detect_market_phase(
        self,
        df: pd.DataFrame,
        i: int,
    ) -> Tuple[Optional[MarketPhase], Optional[Dict[str, Any]]]:
        """
        Определяет фазу рынка (auction/balance/imbalance)
        
        Args:
            df: DataFrame с OHLCV данными
            i: Индекс текущей свечи
            
        Returns:
            Tuple[фаза, детали]
        """
        try:
            if i < self.lookback or i >= len(df):
                return None, None
            
            # Рассчитываем баланс
            balance_score = self.calculate_balance_score(df, i)
            if balance_score is None:
                return None, None
            
            # Рассчитываем волатильность (ATR как прокси)
            window_df = df.iloc[i - self.lookback + 1:i + 1]
            
            # Простая волатильность на основе диапазона свечей
            price_range = (window_df['high'] - window_df['low']) / window_df['close']
            volatility = price_range.mean()
            
            # Рассчитываем движение цены
            price_change = abs((df['close'].iloc[i] - df['close'].iloc[i - self.lookback]) / df['close'].iloc[i - self.lookback])
            
            # Определяем фазу на основе баланса, волатильности и движения
            # Balance: баланс близок к 0.5, низкая волатильность, малое движение
            # Auction: активное движение, высокая волатильность
            # Imbalance: сильный дисбаланс, готовность к движению
            
            balance_deviation = abs(balance_score - 0.5)
            
            # Определение фазы
            if balance_deviation < self.balance_threshold and volatility < 0.02 and price_change < 0.01:
                # Баланс: баланс близок к 0.5, низкая волатильность, малое движение
                phase = MarketPhase.BALANCE
            elif balance_deviation > self.imbalance_threshold:
                # Дисбаланс: сильное отклонение от баланса
                phase = MarketPhase.IMBALANCE
            else:
                # Аукцион: активное движение или средний дисбаланс
                phase = MarketPhase.AUCTION
            
            details = {
                'balance_score': balance_score,
                'balance_deviation': balance_deviation,
                'volatility': volatility,
                'price_change': price_change,
                'phase': phase.value,
            }
            
            # Логирование метрик
            self._log_metrics(phase, balance_score)
            
            return phase, details
            
        except Exception as e:
            logger.error(f"Ошибка определения фазы рынка: {e}")
            return None, None
    
    def get_auction_levels(
        self,
        df: pd.DataFrame,
        i: int,
    ) -> Dict[str, Optional[float]]:
        """
        Определяет уровни аукциона (точки контроля)
        
        Args:
            df: DataFrame с OHLCV данными
            i: Индекс текущей свечи
            
        Returns:
            Dict с уровнями: high, low, mid, value_area_high, value_area_low
        """
        try:
            if i < self.lookback or i >= len(df):
                return {
                    'high': None,
                    'low': None,
                    'mid': None,
                    'value_area_high': None,
                    'value_area_low': None,
                }
            
            # Берем последние lookback свечей
            window_df = df.iloc[i - self.lookback + 1:i + 1]
            
            if len(window_df) == 0:
                return {
                    'high': None,
                    'low': None,
                    'mid': None,
                    'value_area_high': None,
                    'value_area_low': None,
                }
            
            # Базовые уровни
            high = float(window_df['high'].max())
            low = float(window_df['low'].min())
            mid = (high + low) / 2
            
            # Value Area (70% объема) - упрощенная версия
            # Используем среднюю цену взвешенную по объему как прокси
            if 'volume' in window_df.columns:
                typical_price = (window_df['high'] + window_df['low'] + window_df['close']) / 3
                volume_weighted_price = (typical_price * window_df['volume']).sum() / window_df['volume'].sum()
                
                # Value Area как ±15% от volume weighted price
                value_area_range = (high - low) * 0.15
                value_area_high = volume_weighted_price + value_area_range
                value_area_low = volume_weighted_price - value_area_range
            else:
                # Fallback без объема
                value_area_range = (high - low) * 0.15
                value_area_high = mid + value_area_range
                value_area_low = mid - value_area_range
            
            return {
                'high': high,
                'low': low,
                'mid': mid,
                'value_area_high': float(value_area_high),
                'value_area_low': float(value_area_low),
            }
            
        except Exception as e:
            logger.error(f"Ошибка определения уровней аукциона: {e}")
            return {
                'high': None,
                'low': None,
                'mid': None,
                'value_area_high': None,
                'value_area_low': None,
            }
    
    def get_signal(
        self,
        df: pd.DataFrame,
        i: int,
    ) -> Optional[str]:
        """
        Определяет торговый сигнал на основе AMT
        
        Логика:
        - Imbalance + преобладание покупателей → LONG
        - Imbalance + преобладание продавцов → SHORT
        - Balance → None (не торгуем)
        - Auction → None (нейтрально)
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            
        Returns:
            'long', 'short' или None
        """
        try:
            phase, details = self.detect_market_phase(df, i)
            
            if phase is None or details is None:
                return None
            
            balance_score = details.get('balance_score')
            if balance_score is None:
                return None
            
            # Торгуем только в фазе дисбаланса
            if phase == MarketPhase.IMBALANCE:
                if balance_score > 0.5 + self.imbalance_threshold:
                    return 'long'  # Сильное преобладание покупателей
                elif balance_score < 0.5 - self.imbalance_threshold:
                    return 'short'  # Сильное преобладание продавцов
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка определения сигнала AMT: {e}")
            return None


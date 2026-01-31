"""
Institutional Order Flow Patterns - обнаружение паттернов поведения институционалов

Детектирует:
- Iceberg Orders (скрытые крупные ордера)
- Spoofing (ложные заявки)
- Другие паттерны институциональной торговли
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from functools import lru_cache

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# Попытка импорта кэша
try:
    from src.core.cache import TTLCache
    CACHE_AVAILABLE = True
    # Кэш для паттернов (TTL 30 секунд, так как паттерны могут быстро меняться)
    _patterns_cache = TTLCache(default_ttl=30)
except ImportError:
    CACHE_AVAILABLE = False
    _patterns_cache = None


@dataclass
class PatternDetection:
    """Результат обнаружения паттерна"""
    pattern_type: str  # 'iceberg', 'spoofing', etc.
    confidence: float  # 0.0 - 1.0
    details: Dict[str, Any]
    timestamp: Optional[int] = None


class IcebergOrderDetector:
    """
    Детектор Iceberg Orders - скрытых крупных ордеров
    
    Iceberg Orders - это крупные ордера, разбитые на множество мелких,
    чтобы скрыть истинный размер позиции.
    
    Признаки:
    - Большие сделки среди маленьких
    - Постоянный объем на определенных уровнях
    - Аномалии в распределении размера сделок
    """
    
    def __init__(
        self,
        large_trade_threshold: float = 2.0,  # Порог для "большой" сделки (в стандартных отклонениях)
        min_iceberg_size: int = 5,  # Минимальное количество "больших" сделок для паттерна
        lookback: int = 20,  # Период для анализа
    ):
        """
        Args:
            large_trade_threshold: Порог для определения большой сделки (в стандартных отклонениях)
            min_iceberg_size: Минимальное количество больших сделок для паттерна
            lookback: Период для анализа
        """
        self.large_trade_threshold = large_trade_threshold
        self.min_iceberg_size = min_iceberg_size
        self.lookback = lookback
    
    def detect_iceberg_pattern(
        self,
        df: pd.DataFrame,
        i: int,
    ) -> Optional[PatternDetection]:
        """
        Обнаруживает паттерн Iceberg Order
        
        Args:
            df: DataFrame с OHLCV данными
            i: Индекс текущей свечи
        
        Returns:
            PatternDetection или None
        """
        try:
            if i < self.lookback or i >= len(df):
                return None
            
            window_df = df.iloc[i - self.lookback + 1:i + 1]
            
            if len(window_df) == 0 or 'volume' not in window_df.columns:
                return None
            
            # Анализируем распределение объемов
            volumes = window_df['volume'].values
            
            if len(volumes) < self.min_iceberg_size:
                return None
            
            # Рассчитываем статистику объемов
            mean_volume = np.mean(volumes)
            std_volume = np.std(volumes)
            
            if std_volume == 0:
                return None  # Нет вариации в объемах
            
            # Находим "большие" сделки (выше порога)
            large_trades = volumes[volumes > mean_volume + self.large_trade_threshold * std_volume]
            
            if len(large_trades) < self.min_iceberg_size:
                return None
            
            # Проверяем паттерн: большие сделки должны быть на похожих уровнях цены
            # (упрощенная проверка - анализируем свечи с большим объемом)
            large_volume_indices = np.where(volumes > mean_volume + self.large_trade_threshold * std_volume)[0]
            
            if len(large_volume_indices) < self.min_iceberg_size:
                return None
            
            # Анализируем цены на свечах с большим объемом
            large_volume_prices = window_df.iloc[large_volume_indices]['close'].values
            price_std = np.std(large_volume_prices)
            price_range = window_df['close'].max() - window_df['close'].min()
            
            # Если большие сделки на похожих уровнях (низкая вариация цен)
            # и это составляет значительную часть диапазона - возможен Iceberg
            price_concentration = 1.0 - (price_std / price_range) if price_range > 0 else 0.0
            
            # Рассчитываем уверенность
            confidence = min(1.0, (
                len(large_trades) / self.min_iceberg_size * 0.3 +
                price_concentration * 0.4 +
                (len(large_trades) / len(volumes)) * 0.3
            ))
            
            if confidence < 0.5:
                return None
            
            result = PatternDetection(
                pattern_type='iceberg',
                confidence=confidence,
                details={
                    'large_trades_count': len(large_trades),
                    'mean_volume': float(mean_volume),
                    'large_trade_mean': float(np.mean(large_trades)),
                    'price_concentration': float(price_concentration),
                    'price_level': float(np.mean(large_volume_prices)),
                },
                timestamp=i,
            )
            
            # Сохранение в кэш
            if CACHE_AVAILABLE and _patterns_cache is not None:
                cache_key = f"iceberg_{i}_{len(df)}_{hash(tuple(df.iloc[i-self.lookback+1:i+1].values.tobytes()))}"
                _patterns_cache.set(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка обнаружения Iceberg Order: {e}")
            return None


class SpoofingDetector:
    """
    Детектор Spoofing - ложных заявок
    
    Spoofing - это размещение крупных заявок с намерением их отменить,
    чтобы создать ложное впечатление о давлении покупателей/продавцов.
    
    Признаки:
    - Большие заявки, которые быстро отменяются
    - Аномалии в объеме без соответствующего движения цены
    - Паттерны "ложных пробоев"
    """
    
    def __init__(
        self,
        volume_price_divergence_threshold: float = 0.5,  # Порог расхождения объема и цены
        lookback: int = 10,  # Период для анализа
    ):
        """
        Args:
            volume_price_divergence_threshold: Порог расхождения объема и движения цены
            lookback: Период для анализа
        """
        self.volume_price_divergence_threshold = volume_price_divergence_threshold
        self.lookback = lookback
    
    def detect_spoofing_pattern(
        self,
        df: pd.DataFrame,
        i: int,
    ) -> Optional[PatternDetection]:
        """
        Обнаруживает паттерн Spoofing
        
        Args:
            df: DataFrame с OHLCV данными
            i: Индекс текущей свечи
        
        Returns:
            PatternDetection или None
        """
        try:
            if i < self.lookback or i >= len(df):
                return None
            
            window_df = df.iloc[i - self.lookback + 1:i + 1]
            
            if len(window_df) == 0 or 'volume' not in window_df.columns:
                return None
            
            # Анализируем расхождение между объемом и движением цены
            volumes = window_df['volume'].values
            price_changes = np.abs(window_df['close'].pct_change().fillna(0).values)
            
            # Нормализуем
            if len(volumes) < 2:
                return None
            
            mean_volume = np.mean(volumes)
            mean_price_change = np.mean(price_changes[price_changes > 0]) if np.any(price_changes > 0) else 0
            
            if mean_volume == 0 or mean_price_change == 0:
                return None
            
            # Рассчитываем соотношение объема к движению цены
            volume_price_ratios = []
            for j in range(1, len(volumes)):
                if price_changes[j] > 0:
                    ratio = volumes[j] / (price_changes[j] * mean_volume / mean_price_change) if mean_price_change > 0 else 0
                    volume_price_ratios.append(ratio)
            
            if len(volume_price_ratios) == 0:
                return None
            
            # Высокое соотношение объема к движению цены может указывать на спуфинг
            # (большой объем, но малое движение цены)
            high_ratio_count = sum(1 for r in volume_price_ratios if r > 1.0 + self.volume_price_divergence_threshold)
            high_ratio_pct = high_ratio_count / len(volume_price_ratios)
            
            # Проверяем на аномалии: большой объем без движения
            current_volume = volumes[-1]
            current_price_change = price_changes[-1] if len(price_changes) > 0 else 0
            
            volume_anomaly = current_volume > mean_volume * 1.5
            price_anomaly = current_price_change < mean_price_change * 0.5
            
            # Рассчитываем уверенность
            confidence = min(1.0, (
                high_ratio_pct * 0.4 +
                (1.0 if volume_anomaly and price_anomaly else 0.0) * 0.4 +
                (current_volume / mean_volume - 1.0) * 0.2 if mean_volume > 0 else 0.0
            ))
            
            if confidence < 0.5:
                return None
            
            result = PatternDetection(
                pattern_type='spoofing',
                confidence=confidence,
                details={
                    'volume_price_divergence': float(np.mean(volume_price_ratios)),
                    'high_ratio_count': high_ratio_count,
                    'high_ratio_pct': float(high_ratio_pct),
                    'volume_anomaly': volume_anomaly,
                    'price_anomaly': price_anomaly,
                    'current_volume': float(current_volume),
                    'mean_volume': float(mean_volume),
                },
                timestamp=i,
            )
            
            # Сохранение в кэш
            if CACHE_AVAILABLE and _patterns_cache is not None:
                cache_key = f"spoofing_{i}_{len(df)}_{hash(tuple(df.iloc[i-self.lookback+1:i+1].values.tobytes()))}"
                _patterns_cache.set(cache_key, result)
            
            return result
            
        except Exception as e:
            logger.error(f"Ошибка обнаружения Spoofing: {e}")
            return None


class InstitutionalPatternDetector:
    """
    Общий детектор институциональных паттернов
    
    Объединяет все детекторы паттернов для комплексного анализа
    """
    
    def __init__(
        self,
        iceberg_detector: Optional[IcebergOrderDetector] = None,
        spoofing_detector: Optional[SpoofingDetector] = None,
    ):
        """
        Args:
            iceberg_detector: Детектор Iceberg Orders (опционально)
            spoofing_detector: Детектор Spoofing (опционально)
        """
        self.iceberg_detector = iceberg_detector or IcebergOrderDetector()
        self.spoofing_detector = spoofing_detector or SpoofingDetector()
    
    def detect_patterns(
        self,
        df: pd.DataFrame,
        i: int,
    ) -> List[PatternDetection]:
        """
        Обнаруживает все институциональные паттерны
        
        Args:
            df: DataFrame с OHLCV данными
            i: Индекс текущей свечи
        
        Returns:
            Список обнаруженных паттернов
        """
        try:
            patterns = []
            
            # Обнаруживаем Iceberg Orders
            iceberg = self.iceberg_detector.detect_iceberg_pattern(df, i)
            if iceberg:
                patterns.append(iceberg)
            
            # Обнаруживаем Spoofing
            spoofing = self.spoofing_detector.detect_spoofing_pattern(df, i)
            if spoofing:
                patterns.append(spoofing)
            
            return patterns
            
        except Exception as e:
            logger.error(f"Ошибка обнаружения паттернов: {e}")
            return []
    
    def get_signal_quality(
        self,
        df: pd.DataFrame,
        i: int,
        side: str,
    ) -> Dict[str, Any]:
        """
        Оценивает качество сигнала на основе обнаруженных паттернов
        
        Args:
            df: DataFrame с данными
            i: Индекс текущей свечи
            side: "long" или "short"
        
        Returns:
            Dict с оценкой качества сигнала
        """
        try:
            patterns = self.detect_patterns(df, i)
            
            if not patterns:
                return {
                    'quality_score': 1.0,  # Нет паттернов - нейтрально
                    'patterns_detected': [],
                    'recommendation': 'neutral',
                }
            
            # Анализируем влияние паттернов на качество сигнала
            quality_score = 1.0
            pattern_impacts = []
            
            for pattern in patterns:
                if pattern.pattern_type == 'iceberg':
                    # Iceberg может подтверждать или противоречить сигналу
                    # Упрощенная логика: если Iceberg на уровне входа - подтверждение
                    impact = pattern.confidence * 0.3  # Небольшое влияние
                    quality_score += impact
                    pattern_impacts.append({
                        'type': 'iceberg',
                        'confidence': pattern.confidence,
                        'impact': impact,
                    })
                
                elif pattern.pattern_type == 'spoofing':
                    # Spoofing снижает качество сигнала (ложные заявки)
                    impact = -pattern.confidence * 0.5  # Отрицательное влияние
                    quality_score += impact
                    pattern_impacts.append({
                        'type': 'spoofing',
                        'confidence': pattern.confidence,
                        'impact': impact,
                    })
            
            # Нормализуем качество
            quality_score = max(0.0, min(1.0, quality_score))
            
            # Определяем рекомендацию
            if quality_score < 0.4:
                recommendation = 'reject'
            elif quality_score < 0.6:
                recommendation = 'weak'
            elif quality_score < 0.8:
                recommendation = 'moderate'
            else:
                recommendation = 'strong'
            
            return {
                'quality_score': float(quality_score),
                'patterns_detected': [p.pattern_type for p in patterns],
                'pattern_impacts': pattern_impacts,
                'recommendation': recommendation,
            }
            
        except Exception as e:
            logger.error(f"Ошибка оценки качества сигнала: {e}")
            return {
                'quality_score': 1.0,
                'patterns_detected': [],
                'recommendation': 'neutral',
            }


"""
Divergence Analyzer - анализ дивергенций между индикаторами и ценой

Обнаруживает:
- Бычьи дивергенции (цена падает, индикатор растет)
- Медвежьи дивергенции (цена растет, индикатор падает)
"""

import logging
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass

import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


class DivergenceType(Enum):
    """Тип дивергенции"""
    BULLISH = "bullish"  # Бычья дивергенция
    BEARISH = "bearish"  # Медвежья дивергенция
    NONE = "none"  # Нет дивергенции


@dataclass
class Divergence:
    """Результат обнаружения дивергенции"""
    divergence_type: DivergenceType
    confidence: float  # 0.0 - 1.0
    price_trend: str  # 'up', 'down', 'sideways'
    indicator_trend: str  # 'up', 'down', 'sideways'
    start_index: int
    end_index: int


class DivergenceAnalyzer:
    """
    Анализатор дивергенций
    
    Обнаруживает дивергенции между ценой и индикатором (например, CDV)
    """
    
    def __init__(
        self,
        lookback: int = 20,
        min_divergence_strength: float = 0.3,
    ):
        """
        Args:
            lookback: Период для анализа дивергенции
            min_divergence_strength: Минимальная сила дивергенции для обнаружения
        """
        self.lookback = lookback
        self.min_divergence_strength = min_divergence_strength
    
    def detect_divergence(
        self,
        price_series: pd.Series,
        indicator_series: pd.Series,
        i: int,
    ) -> Optional[Divergence]:
        """
        Обнаруживает дивергенцию между ценой и индикатором
        
        Args:
            price_series: Series с ценами
            indicator_series: Series с индикатором (например, CDV)
            i: Индекс текущей точки
        
        Returns:
            Divergence или None
        """
        try:
            if i < self.lookback or i >= len(price_series) or i >= len(indicator_series):
                return None
            
            # Берем окно для анализа
            price_window = price_series.iloc[i - self.lookback + 1:i + 1]
            indicator_window = indicator_series.iloc[i - self.lookback + 1:i + 1]
            
            if len(price_window) < 2 or len(indicator_window) < 2:
                return None
            
            # Определяем тренды
            price_start = price_window.iloc[0]
            price_end = price_window.iloc[-1]
            price_change = (price_end - price_start) / price_start if price_start != 0 else 0
            
            indicator_start = indicator_window.iloc[0]
            indicator_end = indicator_window.iloc[-1]
            indicator_change = (indicator_end - indicator_start) / abs(indicator_start) if indicator_start != 0 else 0
            
            # Определяем направление трендов
            price_trend = 'up' if price_change > 0.01 else ('down' if price_change < -0.01 else 'sideways')
            indicator_trend = 'up' if indicator_change > 0.01 else ('down' if indicator_change < -0.01 else 'sideways')
            
            # Ищем локальные экстремумы
            price_peaks = self._find_peaks(price_window)
            price_troughs = self._find_troughs(price_window)
            indicator_peaks = self._find_peaks(indicator_window)
            indicator_troughs = self._find_troughs(indicator_window)
            
            # Проверяем на бычью дивергенцию (цена падает, индикатор растет)
            bullish_divergence = self._check_bullish_divergence(
                price_troughs, indicator_troughs, price_window, indicator_window
            )
            
            # Проверяем на медвежью дивергенцию (цена растет, индикатор падает)
            bearish_divergence = self._check_bearish_divergence(
                price_peaks, indicator_peaks, price_window, indicator_window
            )
            
            # Определяем тип дивергенции
            if bullish_divergence['found']:
                confidence = min(1.0, bullish_divergence['strength'])
                return Divergence(
                    divergence_type=DivergenceType.BULLISH,
                    confidence=confidence,
                    price_trend=price_trend,
                    indicator_trend=indicator_trend,
                    start_index=i - self.lookback + 1,
                    end_index=i,
                )
            
            if bearish_divergence['found']:
                confidence = min(1.0, bearish_divergence['strength'])
                return Divergence(
                    divergence_type=DivergenceType.BEARISH,
                    confidence=confidence,
                    price_trend=price_trend,
                    indicator_trend=indicator_trend,
                    start_index=i - self.lookback + 1,
                    end_index=i,
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Ошибка обнаружения дивергенции: {e}")
            return None
    
    def _find_peaks(self, series: pd.Series) -> List[int]:
        """Находит локальные максимумы"""
        peaks = []
        for i in range(1, len(series) - 1):
            if series.iloc[i] > series.iloc[i - 1] and series.iloc[i] > series.iloc[i + 1]:
                peaks.append(i)
        return peaks
    
    def _find_troughs(self, series: pd.Series) -> List[int]:
        """Находит локальные минимумы"""
        troughs = []
        for i in range(1, len(series) - 1):
            if series.iloc[i] < series.iloc[i - 1] and series.iloc[i] < series.iloc[i + 1]:
                troughs.append(i)
        return troughs
    
    def _check_bullish_divergence(
        self,
        price_troughs: List[int],
        indicator_troughs: List[int],
        price_series: pd.Series,
        indicator_series: pd.Series,
    ) -> Dict[str, Any]:
        """Проверяет на бычью дивергенцию"""
        if len(price_troughs) < 2 or len(indicator_troughs) < 2:
            return {'found': False, 'strength': 0.0}
        
        # Берем последние два минимума
        price_trough1_idx = price_troughs[-2] if len(price_troughs) >= 2 else price_troughs[-1]
        price_trough2_idx = price_troughs[-1]
        indicator_trough1_idx = indicator_troughs[-2] if len(indicator_troughs) >= 2 else indicator_troughs[-1]
        indicator_trough2_idx = indicator_troughs[-1]
        
        price_trough1 = price_series.iloc[price_trough1_idx]
        price_trough2 = price_series.iloc[price_trough2_idx]
        indicator_trough1 = indicator_series.iloc[indicator_trough1_idx]
        indicator_trough2 = indicator_series.iloc[indicator_trough2_idx]
        
        # Бычья дивергенция: цена падает (trough2 < trough1), индикатор растет (trough2 > trough1)
        price_falling = price_trough2 < price_trough1
        indicator_rising = indicator_trough2 > indicator_trough1
        
        if price_falling and indicator_rising:
            # Рассчитываем силу дивергенции
            price_change_pct = abs((price_trough2 - price_trough1) / price_trough1) if price_trough1 != 0 else 0
            indicator_change_pct = abs((indicator_trough2 - indicator_trough1) / abs(indicator_trough1)) if indicator_trough1 != 0 else 0
            strength = min(1.0, (price_change_pct + indicator_change_pct) / 2)
            
            if strength >= self.min_divergence_strength:
                return {'found': True, 'strength': strength}
        
        return {'found': False, 'strength': 0.0}
    
    def _check_bearish_divergence(
        self,
        price_peaks: List[int],
        indicator_peaks: List[int],
        price_series: pd.Series,
        indicator_series: pd.Series,
    ) -> Dict[str, Any]:
        """Проверяет на медвежью дивергенцию"""
        if len(price_peaks) < 2 or len(indicator_peaks) < 2:
            return {'found': False, 'strength': 0.0}
        
        # Берем последние два максимума
        price_peak1_idx = price_peaks[-2] if len(price_peaks) >= 2 else price_peaks[-1]
        price_peak2_idx = price_peaks[-1]
        indicator_peak1_idx = indicator_peaks[-2] if len(indicator_peaks) >= 2 else indicator_peaks[-1]
        indicator_peak2_idx = indicator_peaks[-1]
        
        price_peak1 = price_series.iloc[price_peak1_idx]
        price_peak2 = price_series.iloc[price_peak2_idx]
        indicator_peak1 = indicator_series.iloc[indicator_peak1_idx]
        indicator_peak2 = indicator_series.iloc[indicator_peak2_idx]
        
        # Медвежья дивергенция: цена растет (peak2 > peak1), индикатор падает (peak2 < peak1)
        price_rising = price_peak2 > price_peak1
        indicator_falling = indicator_peak2 < indicator_peak1
        
        if price_rising and indicator_falling:
            # Рассчитываем силу дивергенции
            price_change_pct = abs((price_peak2 - price_peak1) / price_peak1) if price_peak1 != 0 else 0
            indicator_change_pct = abs((indicator_peak2 - indicator_peak1) / abs(indicator_peak1)) if indicator_peak1 != 0 else 0
            strength = min(1.0, (price_change_pct + indicator_change_pct) / 2)
            
            if strength >= self.min_divergence_strength:
                return {'found': True, 'strength': strength}
        
        return {'found': False, 'strength': 0.0}


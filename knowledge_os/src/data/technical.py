"""
Технические индикаторы для ATRA
Централизованный модуль для всех технических расчетов
Оптимизировано с NumPy векторизацией и Numba JIT компиляцией
"""

import logging
import math
import statistics
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timedelta
from src.shared.utils.datetime_utils import get_utc_now
from dataclasses import dataclass

import numpy as np

# Попытка импорта Numba для JIT компиляции
try:
    from numba import jit
    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False
    # Заглушка для декоратора jit
    def jit(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

logger = logging.getLogger(__name__)


@dataclass
class TechnicalIndicators:
    """Класс для расчета технических индикаторов"""

    @staticmethod
    @jit(nopython=True, cache=True) if NUMBA_AVAILABLE else lambda f: f
    def _calculate_rsi_core(prices_arr: np.ndarray, period: int) -> float:
        """
        Ядро расчета RSI с Numba JIT компиляцией
        Ускорение на 10-50x для больших массивов
        """
        deltas = np.diff(prices_arr)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = np.mean(gains[-period:])
        avg_loss = np.mean(losses[-period:])
        if avg_loss == 0:
            return 100.0
        rs = avg_gain / avg_loss
        return 100.0 - (100.0 / (1.0 + rs))

    @staticmethod
    def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
        """
        Расчет RSI (Relative Strength Index)
        Оптимизировано с NumPy векторизацией и Numba JIT

        Args:
            prices: Список цен (обычно закрытия)
            period: Период для расчета (по умолчанию 14)

        Returns:
            Значение RSI (0-100) или None при ошибке
        """
        try:
            if len(prices) < period + 1:
                logger.warning("Недостаточно данных для RSI: %d < %d", len(prices), period + 1)
                return None

            # Конвертируем в numpy array для векторизации
            prices_arr = np.array(prices, dtype=np.float64)
            
            # Используем JIT-компилированное ядро если доступно
            if NUMBA_AVAILABLE:
                rsi = TechnicalIndicators._calculate_rsi_core(prices_arr, period)
            else:
                # Fallback на векторизованный расчет
                deltas = np.diff(prices_arr)
                gains = np.where(deltas > 0, deltas, 0.0)
                losses = np.where(deltas < 0, -deltas, 0.0)
                avg_gain = np.mean(gains[-period:])
                avg_loss = np.mean(losses[-period:])
                if avg_loss == 0:
                    return 100.0
                rs = avg_gain / avg_loss
                rsi = 100.0 - (100.0 / (1.0 + rs))

            return round(float(rsi), 2)

        except Exception as e:
            logger.error("Ошибка расчета RSI: %s", e)
            return None

    @staticmethod
    @jit(nopython=True, cache=True) if NUMBA_AVAILABLE else lambda f: f
    def _calculate_momentum_core(prices_arr: np.ndarray, period: int) -> float:
        """
        Ядро расчета Momentum с Numba JIT компиляцией
        """
        current = prices_arr[-1]
        previous = prices_arr[-period-1]
        if previous == 0:
            return 0.0
        return ((current - previous) / previous) * 100.0

    @staticmethod
    def calculate_momentum(prices: List[float], period: int = 10) -> Optional[float]:
        """
        Расчет Momentum
        Оптимизировано с NumPy и Numba JIT

        Args:
            prices: Список цен
            period: Период для расчета

        Returns:
            Значение Momentum или None
        """
        try:
            if len(prices) < period + 1:
                return None

            # Используем NumPy для быстрого доступа
            prices_arr = np.array(prices, dtype=np.float64)
            
            # Используем JIT-компилированное ядро если доступно
            if NUMBA_AVAILABLE:
                momentum = TechnicalIndicators._calculate_momentum_core(prices_arr, period)
            else:
                current = prices_arr[-1]
                previous = prices_arr[-period-1]
                if previous == 0:
                    return None
                momentum = ((current - previous) / previous) * 100.0

            if momentum == 0.0:
                return None

            return round(float(momentum), 2)

        except Exception as e:
            logger.error("Ошибка расчета Momentum: %s", e)
            return None

    @staticmethod
    def calculate_volume_ratio(current_volume: float, avg_volume: float) -> Optional[float]:
        """
        Расчет соотношения объема к среднему

        Args:
            current_volume: Текущий объем
            avg_volume: Средний объем

        Returns:
            Соотношение объема или None
        """
        try:
            if avg_volume <= 0:
                return None

            ratio = current_volume / avg_volume
            return round(ratio, 2)

        except Exception as e:
            logger.error(f"Ошибка расчета Volume Ratio: {e}")
            return None

    @staticmethod
    def calculate_fear_greed_index(prices: List[float], volumes: List[float]) -> Optional[float]:
        """
        Расчет индекса страха/жадности на основе волатильности и объема
        Оптимизировано с NumPy векторизацией

        Args:
            prices: Список цен
            volumes: Список объемов

        Returns:
            Значение индекса (0-100) или None
        """
        try:
            if len(prices) < 14 or len(volumes) < 14:
                return None

            # Конвертируем в numpy arrays
            prices_arr = np.array(prices[-14:], dtype=np.float64)
            volumes_arr = np.array(volumes[-14:], dtype=np.float64)

            # Векторизованный расчет волатильности цен
            price_mean = np.mean(prices_arr)
            price_std = np.std(prices_arr, ddof=0)
            price_volatility = (price_std / price_mean) * 100.0 if price_mean > 0 else 0.0

            # Векторизованный расчет волатильности объемов
            volume_mean = np.mean(volumes_arr)
            volume_std = np.std(volumes_arr, ddof=0)
            volume_volatility = (volume_std / volume_mean) * 100.0 if volume_mean > 0 else 0.0

            # Нормализация значений (0-100)
            price_score = min(100.0, max(0.0, 50.0 + (price_volatility - 2.0) * 10.0))
            volume_score = min(100.0, max(0.0, 50.0 + (volume_volatility - 50.0) * 2.0))

            # Общий индекс (среднее)
            fear_greed_index = (price_score + volume_score) / 2.0

            return round(float(fear_greed_index), 2)

        except Exception as e:
            logger.error("Ошибка расчета Fear/Greed Index: %s", e)
            return None

    @staticmethod
    @jit(nopython=True, cache=True) if NUMBA_AVAILABLE else lambda f: f
    def _calculate_bollinger_core(prices_arr: np.ndarray, std_dev: float) -> Tuple[float, float, float]:
        """
        Ядро расчета Bollinger Bands с Numba JIT компиляцией
        """
        sma = np.mean(prices_arr)
        std = np.std(prices_arr)
        upper_band = sma + (std * std_dev)
        lower_band = sma - (std * std_dev)
        return upper_band, sma, lower_band

    @staticmethod
    def calculate_bollinger_bands(prices: List[float], period: int = 20,
                                std_dev: float = 2.0) -> Optional[Dict[str, float]]:
        """
        Расчет Bollinger Bands
        Оптимизировано с NumPy векторизацией и Numba JIT

        Args:
            prices: Список цен
            period: Период для SMA
            std_dev: Количество стандартных отклонений

        Returns:
            Словарь с верхней, средней и нижней полосами или None
        """
        try:
            if len(prices) < period:
                return None

            # Конвертируем в numpy array
            prices_arr = np.array(prices[-period:], dtype=np.float64)
            
            # Используем JIT-компилированное ядро если доступно
            if NUMBA_AVAILABLE:
                upper_band, sma, lower_band = TechnicalIndicators._calculate_bollinger_core(prices_arr, std_dev)
            else:
                # Fallback на векторизованный расчет
                sma = np.mean(prices_arr)
                std = np.std(prices_arr, ddof=0)
                upper_band = sma + (std * std_dev)
                lower_band = sma - (std * std_dev)

            return {
                'upper': round(float(upper_band), 8),
                'middle': round(float(sma), 8),
                'lower': round(float(lower_band), 8)
            }

        except Exception as e:
            logger.error("Ошибка расчета Bollinger Bands: %s", e)
            return None

    @staticmethod
    def calculate_moving_averages(prices: List[float], periods: List[int] = None) -> Dict[str, Optional[float]]:
        """
        Расчет скользящих средних
        Оптимизировано с NumPy векторизацией

        Args:
            prices: Список цен
            periods: Список периодов для расчета

        Returns:
            Словарь со скользящими средними
        """
        if periods is None:
            periods = [10, 20, 50, 200]

        # Конвертируем в numpy array один раз
        prices_arr = np.array(prices, dtype=np.float64)
        result = {}

        for period in periods:
            try:
                if len(prices_arr) < period:
                    result[f'sma_{period}'] = None
                    continue

                # Векторизованный расчет SMA
                sma = np.mean(prices_arr[-period:])
                result[f'sma_{period}'] = round(float(sma), 8)

            except Exception as e:
                logger.error("Ошибка расчета SMA %d: %s", period, e)
                result[f'sma_{period}'] = None

        return result

    @staticmethod
    def calculate_trend_strength(prices: List[float], sma_short: int = 20,
                               sma_long: int = 50) -> Optional[Dict[str, Any]]:
        """
        Расчет силы тренда
        Оптимизировано с NumPy векторизацией

        Args:
            prices: Список цен
            sma_short: Период короткой SMA
            sma_long: Период длинной SMA

        Returns:
            Словарь с данными о тренде или None
        """
        try:
            if len(prices) < sma_long:
                return None

            # Конвертируем в numpy array
            prices_arr = np.array(prices, dtype=np.float64)
            
            # Векторизованный расчет скользящих средних
            sma_short_value = np.mean(prices_arr[-sma_short:])
            sma_long_value = np.mean(prices_arr[-sma_long:])

            # Определение тренда
            if sma_short_value > sma_long_value * 1.02:  # 2% выше
                trend = 'bullish'
                strength = min(100.0, ((sma_short_value / sma_long_value) - 1.0) * 5000.0)
            elif sma_short_value < sma_long_value * 0.98:  # 2% ниже
                trend = 'bearish'
                strength = min(100.0, (1.0 - (sma_short_value / sma_long_value)) * 5000.0)
            else:
                trend = 'neutral'
                strength = 0.0

            return {
                'trend': trend,
                'strength': round(float(strength), 2),
                'sma_short': round(float(sma_short_value), 8),
                'sma_long': round(float(sma_long_value), 8),
                'ratio': round(float(sma_short_value / sma_long_value), 4)
            }

        except Exception as e:
            logger.error("Ошибка расчета Trend Strength: %s", e)
            return None

    @staticmethod
    def calculate_volume_profile(volumes: List[float], prices: List[float],
                               num_bins: int = 10) -> Optional[Dict[str, Any]]:
        """
        Расчет профиля объема
        Оптимизировано с NumPy векторизацией

        Args:
            volumes: Список объемов
            prices: Список цен
            num_bins: Количество бинов

        Returns:
            Словарь с профилем объема или None
        """
        try:
            if len(volumes) != len(prices) or len(volumes) < 10:
                return None

            # Конвертируем в numpy arrays
            volumes_arr = np.array(volumes, dtype=np.float64)
            prices_arr = np.array(prices, dtype=np.float64)

            # Векторизованное нахождение min/max
            price_min = np.min(prices_arr)
            price_max = np.max(prices_arr)
            price_range = price_max - price_min

            if price_range == 0:
                return None

            bin_size = price_range / num_bins
            bins = []

            # Создание ценовых бинов
            for i in range(num_bins):
                bin_start = price_min + (i * bin_size)
                bin_end = bin_start + bin_size
                bins.append({'range': [float(bin_start), float(bin_end)], 'volume': 0.0})

            # Векторизованное распределение объемов по бинам
            bin_indices = np.clip(
                ((prices_arr - price_min) / bin_size).astype(np.int32),
                0, num_bins - 1
            )
            
            # Векторизованное суммирование объемов по бинам
            for i in range(num_bins):
                mask = bin_indices == i
                bins[i]['volume'] = float(np.sum(volumes_arr[mask]))

            # Нахождение максимального объема
            volumes_list = [bin['volume'] for bin in bins]
            max_volume = max(volumes_list)
            max_volume_bin = bins[volumes_list.index(max_volume)]

            total_volume = np.sum(volumes_arr)

            return {
                'bins': bins,
                'max_volume': float(max_volume),
                'max_volume_range': max_volume_bin['range'],
                'average_volume': float(np.mean(volumes_arr)),
                'volume_concentration': float(max_volume / total_volume) if total_volume > 0 else 0.0
            }

        except Exception as e:
            logger.error("Ошибка расчета Volume Profile: %s", e)
            return None

    @staticmethod
    def get_all_technical_indicators(ohlc_data: List[Dict]) -> Optional[Dict[str, Any]]:
        """
        Расчет всех технических индикаторов

        Args:
            ohlc_data: Список OHLC данных

        Returns:
            Словарь со всеми индикаторами или None
        """
        try:
            if not ohlc_data or len(ohlc_data) < 5:  # Уменьшено требование
                return None

            # Извлечение данных
            closes = [item.get('close', 0) for item in ohlc_data]
            volumes = [item.get('volume', 0) for item in ohlc_data]

            if len([p for p in closes if p > 0]) < 5:  # Уменьшено требование
                return None

            # Расчет всех индикаторов
            rsi = TechnicalIndicators.calculate_rsi(closes)
            momentum = TechnicalIndicators.calculate_momentum(closes)
            volume_ratio = TechnicalIndicators.calculate_volume_ratio(
                volumes[-1], sum(volumes[-5:]) / 5 if volumes else 0  # Уменьшено
            )
            fear_greed = TechnicalIndicators.calculate_fear_greed_index(closes, volumes)
            bollinger = TechnicalIndicators.calculate_bollinger_bands(closes)
            moving_averages = TechnicalIndicators.calculate_moving_averages(closes)
            trend_strength = TechnicalIndicators.calculate_trend_strength(closes)
            volume_profile = TechnicalIndicators.calculate_volume_profile(volumes, closes)
            
            # Расчет VWAP (если доступен модуль)
            vwap_data = None
            try:
                from src.analysis.vwap import VWAPCalculator
                import pandas as pd
                
                # Преобразуем данные в DataFrame для VWAP
                df_vwap = pd.DataFrame(ohlc_data)
                if 'timestamp' in df_vwap.columns:
                    df_vwap['timestamp'] = pd.to_datetime(df_vwap['timestamp'])
                    df_vwap.set_index('timestamp', inplace=True)
                
                vwap_calc = VWAPCalculator()
                vwap = vwap_calc.calculate_daily_vwap(df_vwap)
                vwap_bands = vwap_calc.calculate_vwap_bands(vwap, df_vwap)
                
                if len(vwap) > 0:
                    vwap_data = {
                        'vwap': float(vwap.iloc[-1]) if hasattr(vwap, 'iloc') else float(vwap),
                        'upper_band_1': float(vwap_bands['upper_band_1'].iloc[-1]) if hasattr(vwap_bands['upper_band_1'], 'iloc') else None,
                        'lower_band_1': float(vwap_bands['lower_band_1'].iloc[-1]) if hasattr(vwap_bands['lower_band_1'], 'iloc') else None,
                        'upper_band_2': float(vwap_bands['upper_band_2'].iloc[-1]) if hasattr(vwap_bands['upper_band_2'], 'iloc') else None,
                        'lower_band_2': float(vwap_bands['lower_band_2'].iloc[-1]) if hasattr(vwap_bands['lower_band_2'], 'iloc') else None,
                    }
            except (ImportError, Exception) as e:
                logger.debug("VWAP недоступен или ошибка расчета: %s", e)

            result = {
                'timestamp': get_utc_now().isoformat(),
                'rsi': rsi,
                'momentum': momentum,
                'volume_ratio': volume_ratio,
                'fear_greed_index': fear_greed,
                'bollinger_bands': bollinger,
                'moving_averages': moving_averages,
                'trend_strength': trend_strength,
                'volume_profile': volume_profile,
                'data_points': len(ohlc_data)
            }
            
            if vwap_data:
                result['vwap'] = vwap_data
            
            return result

        except Exception as e:
            logger.error(f"Ошибка расчета всех индикаторов: {e}")
            return None


# Глобальный экземпляр для удобства использования
technical_indicators = TechnicalIndicators()

# Экспорт для обратной совместимости
def calculate_rsi(prices: List[float], period: int = 14) -> Optional[float]:
    """Обратная совместимость"""
    return technical_indicators.calculate_rsi(prices, period)

def calculate_volume_ratio(current_volume: float, avg_volume: float) -> Optional[float]:
    """Обратная совместимость"""
    return technical_indicators.calculate_volume_ratio(current_volume, avg_volume)

def get_technical_indicators(ohlc_data: List[Dict]) -> Optional[Dict[str, Any]]:
    """Обратная совместимость"""
    return technical_indicators.get_all_technical_indicators(ohlc_data)

"""
Market Profile Filter - фильтр на основе Market Profile (TPO + Volume Profile)

Использует комбинированный POC и Value Area для фильтрации сигналов:
- LONG: цена должна быть близка к Value Area Low или ниже
- SHORT: цена должна быть близка к Value Area High или выше
"""

import logging
import time
from typing import Tuple, Optional, Dict, Any

import pandas as pd

logger = logging.getLogger(__name__)

# Попытка импорта метрик
try:
    from src.metrics.decorators import record_filter_metrics
    from src.metrics.filter_metrics import FilterType
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

# Импорт Prometheus метрик
try:
    from src.monitoring.prometheus import (
        record_filter_check,
        record_tpo_poc,
        record_indicator_processing_time,
    )
    PROMETHEUS_METRICS_AVAILABLE = True
except ImportError:
    PROMETHEUS_METRICS_AVAILABLE = False

# Импорты с fallback
try:
    from src.analysis.volume_profile import VolumeProfileAnalyzer
    from src.analysis.market_profile import TimePriceOpportunity
    MARKET_PROFILE_AVAILABLE = True
except ImportError:
    MARKET_PROFILE_AVAILABLE = False
    logger.warning("Market Profile модули недоступны")


def check_market_profile_filter(
    df: pd.DataFrame,
    i: int,
    side: str,
    strict_mode: bool = True,
    tolerance_pct: float = 1.5,  # Оптимизировано: было 1.0, стало 1.5
) -> Tuple[bool, Optional[str]]:
    """
    Проверяет, соответствует ли сигнал Market Profile фильтрам
    
    Логика:
    - LONG: цена должна быть близка к Value Area Low или ниже (перепроданность)
    - SHORT: цена должна быть близка к Value Area High или выше (перекупленность)
    - Использует комбинированный POC (Volume Profile + TPO)
    
    Args:
        df: DataFrame с данными OHLCV
        i: Индекс текущей свечи
        side: "long" или "short"
        strict_mode: True для строгого режима (более жесткие фильтры)
        tolerance_pct: Допустимое отклонение от Value Area (%)
    
    Returns:
        Tuple[passed, reason]
    """
    try:
        if not MARKET_PROFILE_AVAILABLE:
            return True, None  # Если модуль недоступен, пропускаем фильтр
        
        if i >= len(df):
            return False, "Индекс выходит за границы DataFrame"
        
        start_time = time.time()
        current_price = df['close'].iloc[i]
        
        # Инициализируем анализаторы
        vp_analyzer = VolumeProfileAnalyzer(
            bins=50,
            value_area_pct=0.70,
            default_lookback=100,
        )
        
        tpo_analyzer = TimePriceOpportunity(
            bins=50,
            value_area_pct=0.70,
            default_lookback=100,
        )
        
        # Рассчитываем профили
        start_time = time.time()
        volume_profile = vp_analyzer.calculate_volume_profile(df, lookback_periods=100)
        tpo_profile = tpo_analyzer.calculate_tpo_profile(df, lookback_periods=100)
        processing_time = time.time() - start_time
        
        # Записываем метрики
        if PROMETHEUS_METRICS_AVAILABLE:
            try:
                symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                if tpo_profile and tpo_profile.get("tpo_poc"):
                    record_tpo_poc(symbol)
                record_indicator_processing_time('tpo', processing_time)
            except Exception as e:
                logger.debug(f"Ошибка записи метрик Market Profile: {e}")
        
        if not volume_profile or not tpo_profile:
            return True, None  # Если не удалось рассчитать, пропускаем
        
        # Комбинируем профили
        combined_profile = tpo_analyzer.combine_with_volume_profile(
            volume_profile,
            tpo_profile,
            weight_volume=0.6,
            weight_time=0.4,
        )
        
        combined_poc = combined_profile.get("combined_poc")
        combined_vah = combined_profile.get("combined_value_area_high")
        combined_val = combined_profile.get("combined_value_area_low")
        
        # Fallback на отдельные профили
        if combined_poc is None:
            combined_poc = volume_profile.get("poc") or tpo_profile.get("tpo_poc")
        if combined_vah is None:
            combined_vah = volume_profile.get("value_area_high") or tpo_profile.get("tpo_value_area_high")
        if combined_val is None:
            combined_val = volume_profile.get("value_area_low") or tpo_profile.get("tpo_value_area_low")
        
        if combined_poc is None or combined_vah is None or combined_val is None:
            return True, None  # Если нет данных, пропускаем
        
        # Проверяем положение цены относительно Value Area
        if side.lower() == "long":
            # LONG: цена должна быть близка к Value Area Low или ниже
            distance_from_val = abs(current_price - combined_val) / current_price * 100
            distance_from_poc = abs(current_price - combined_poc) / current_price * 100
            
            # В строгом режиме требуем более близкое положение
            max_distance = tolerance_pct * (0.8 if strict_mode else 1.2)
            
            processing_time = time.time() - start_time
            
            if current_price <= combined_val or distance_from_val <= max_distance:
                result = (True, None)
                if METRICS_AVAILABLE:
                    try:
                        record_filter_metrics(
                            filter_type=FilterType.VOLUME_PROFILE,
                            passed=True,
                            processing_time=processing_time,
                        )
                    except Exception:
                        pass
                # Prometheus метрики
                if PROMETHEUS_METRICS_AVAILABLE:
                    try:
                        symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                        record_filter_check('market_profile', symbol, True)
                    except Exception:
                        pass
                return result
            elif not strict_mode and distance_from_poc <= max_distance * 1.5:
                # В мягком режиме разрешаем близость к POC
                result = (True, None)
                if METRICS_AVAILABLE:
                    try:
                        record_filter_metrics(
                            filter_type=FilterType.VOLUME_PROFILE,
                            passed=True,
                            processing_time=processing_time,
                        )
                    except Exception:
                        pass
                # Prometheus метрики
                if PROMETHEUS_METRICS_AVAILABLE:
                    try:
                        symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                        record_filter_check('market_profile', symbol, True)
                    except Exception:
                        pass
                return result
            else:
                result = (False, (
                    f"Market Profile: цена {current_price:.2f} слишком далеко от Value Area Low "
                    f"({combined_val:.2f}, расстояние={distance_from_val:.2f}%)"
                ))
                if METRICS_AVAILABLE:
                    try:
                        record_filter_metrics(
                            filter_type=FilterType.VOLUME_PROFILE,
                            passed=False,
                            processing_time=processing_time,
                            rejection_reason="MARKET_PROFILE_TOO_FAR_FROM_VAL"
                        )
                    except Exception:
                        pass
                # Prometheus метрики
                if PROMETHEUS_METRICS_AVAILABLE:
                    try:
                        symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                        record_filter_check('market_profile', symbol, False)
                    except Exception:
                        pass
                return result
        
        elif side.lower() == "short":
            # SHORT: цена должна быть близка к Value Area High или выше
            distance_from_vah = abs(current_price - combined_vah) / current_price * 100
            distance_from_poc = abs(current_price - combined_poc) / current_price * 100
            
            # В строгом режиме требуем более близкое положение
            max_distance = tolerance_pct * (0.8 if strict_mode else 1.2)
            
            processing_time = time.time() - start_time
            
            if current_price >= combined_vah or distance_from_vah <= max_distance:
                result = (True, None)
                if METRICS_AVAILABLE:
                    try:
                        record_filter_metrics(
                            filter_type=FilterType.VOLUME_PROFILE,
                            passed=True,
                            processing_time=processing_time,
                        )
                    except Exception:
                        pass
                # Prometheus метрики
                if PROMETHEUS_METRICS_AVAILABLE:
                    try:
                        symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                        record_filter_check('market_profile', symbol, True)
                    except Exception:
                        pass
                return result
            elif not strict_mode and distance_from_poc <= max_distance * 1.5:
                # В мягком режиме разрешаем близость к POC
                result = (True, None)
                if METRICS_AVAILABLE:
                    try:
                        record_filter_metrics(
                            filter_type=FilterType.VOLUME_PROFILE,
                            passed=True,
                            processing_time=processing_time,
                        )
                    except Exception:
                        pass
                # Prometheus метрики
                if PROMETHEUS_METRICS_AVAILABLE:
                    try:
                        symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                        record_filter_check('market_profile', symbol, True)
                    except Exception:
                        pass
                return result
            else:
                result = (False, (
                    f"Market Profile: цена {current_price:.2f} слишком далеко от Value Area High "
                    f"({combined_vah:.2f}, расстояние={distance_from_vah:.2f}%)"
                ))
                if METRICS_AVAILABLE:
                    try:
                        record_filter_metrics(
                            filter_type=FilterType.VOLUME_PROFILE,
                            passed=False,
                            processing_time=processing_time,
                            rejection_reason="MARKET_PROFILE_TOO_FAR_FROM_VAH"
                        )
                    except Exception:
                        pass
                return result
        
        processing_time = time.time() - start_time
        result = (True, None)
        if METRICS_AVAILABLE:
            try:
                record_filter_metrics(
                    filter_type=FilterType.VOLUME_PROFILE,
                    passed=True,
                    processing_time=processing_time,
                )
            except Exception:
                pass
        # Prometheus метрики
        if PROMETHEUS_METRICS_AVAILABLE:
            try:
                symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                record_filter_check('market_profile', symbol, True)
            except Exception:
                pass
        return result
        
    except Exception as e:
        logger.error(f"Ошибка в check_market_profile_filter: {e}")
        return True, None  # В случае ошибки пропускаем фильтр


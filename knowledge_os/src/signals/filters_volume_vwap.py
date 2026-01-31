"""
Фильтры для Volume Profile и VWAP
Используются в strict_entry_signal и soft_entry_signal

⚠️ ВАЖНО: Volume Profile фильтр помечен как НЕЭФФЕКТИВНЫЙ
- Блокирует только 0.9% сигналов (статистика от 2025-11-29)
- Не дает преимуществ по сравнению с baseline
- Результаты идентичны baseline (+0.28% vs +0.28%)
- Отключен по умолчанию в config.py (USE_VP_FILTER = False)

📊 Статистика работы фильтра:
- Всего проверок: 228
- Пропущено: 226 (99.1%)
- Заблокировано: 2 (0.9%)

💡 Рекомендация: НЕ использовать Volume Profile фильтр
   См. docs/VOLUME_PROFILE_FILTER_DECISION.md для деталей

⚠️ MIGRATION TO STATELESS ARCHITECTURE:
This module has been migrated to stateless architecture. Module-level variables
_vp_cache and _vp_stats have been replaced with FilterState container.
"""

import logging
import os
from typing import Tuple, Optional, Dict, Any
from decimal import Decimal

import pandas as pd

# Import FilterState for stateless architecture
try:
    from src.signals.state_container import FilterState
except ImportError:
    # Fallback if state_container is not available
    FilterState = None

logger = logging.getLogger(__name__)

# Constants
VP_CACHE_MAX_SIZE = 10

# Импорты с fallback
try:
    from src.analysis.volume_profile import VolumeProfileAnalyzer
    from src.analysis.vwap import VWAPCalculator
    VP_AVAILABLE = True
    VWAP_AVAILABLE = True
except ImportError:
    VP_AVAILABLE = False
    VWAP_AVAILABLE = False
    logger.warning("Volume Profile или VWAP модули недоступны")



def check_volume_profile_filter(
    df: pd.DataFrame,
    i: int,
    side: str,
    volume_profile: Optional[Dict[str, Any]] = None,
    tolerance_pct: Optional[Decimal] = None,
    strict_mode: bool = True,
    filter_state: Optional[FilterState] = None,
) -> Tuple[bool, Optional[str], FilterState]:
    """
    Проверяет, соответствует ли сигнал Volume Profile фильтрам

    Логика:
    - LONG: цена должна быть вблизи VAL (Value Area Low) или ниже POC
    - SHORT: цена должна быть вблизи VAH (Value Area High) или выше POC
    - Исключаем сигналы слишком далеко от Value Area (>5% от VAH/VAL)
    """
    # Инициализируем состояние, если не передано
    if filter_state is None:
        if FilterState is not None:
            filter_state = FilterState()
        else:
            # Fallback: создаем простой dict для обратной совместимости
            filter_state = type('FilterState', (), {
                'cache': {},
                'stats': {
                    'total_checked': 0,
                    'blocked_count': 0,
                    'passed_count': 0,
                    'blocked_by_reason': {},
                    'last_log_time': None
                }
            })()
    
    try:
        # Получаем tolerance_pct из переменной окружения или используем значение по умолчанию
        volume_profile_threshold = Decimal(
            os.environ.get('volume_profile_threshold', '1.0')
        )

        if tolerance_pct is None:
            # Преобразуем threshold (0.3-1.0) в tolerance_pct (3%-1%)
            if volume_profile_threshold > 0:
                tolerance_pct = max(Decimal("1.0"), min(Decimal("10.0"), (Decimal("1.0") / volume_profile_threshold) * Decimal("3.0")))
            else:
                tolerance_pct = Decimal("1.0")
        
        # Также получаем value_area_pct из threshold для более гибкой настройки
        value_area_pct = float(max(Decimal("0.5"), min(Decimal("0.8"), Decimal("0.5") + volume_profile_threshold * Decimal("0.2"))))
        
        if not VP_AVAILABLE:
            return True, None, filter_state  # Если модуль недоступен, пропускаем фильтр

        if volume_profile is None:
            # Пытаемся рассчитать Volume Profile
            try:
                lookback = 50 if strict_mode else 30
                start_idx = max(0, i + 1 - lookback)
                
                # Кэширование Volume Profile (stateless)
                cache_key = str((id(df), start_idx, i + 1, value_area_pct, lookback))
                if cache_key in filter_state.cache:
                    volume_profile = filter_state.cache[cache_key]
                else:
                    vp_analyzer = VolumeProfileAnalyzer(value_area_pct=value_area_pct)
                    volume_profile = vp_analyzer.calculate_volume_profile(
                        df.iloc[start_idx:i+1], lookback_periods=lookback
                    )

                    # Очищаем кэш если он слишком большой
                    if len(filter_state.cache) >= VP_CACHE_MAX_SIZE:
                        oldest_key = next(iter(filter_state.cache))
                        del filter_state.cache[oldest_key]
                    filter_state.cache[cache_key] = volume_profile
            except Exception as e:
                logger.debug("Не удалось рассчитать Volume Profile: %s", e)
                return True, None, filter_state

        if not volume_profile or not volume_profile.get("poc"):
            _update_vp_stats(filter_state, True, "NO_DATA")
            return True, None, filter_state

        current_price = Decimal(str(df["close"].iloc[i]))
        poc = Decimal(str(volume_profile.get("poc")))
        vah = Decimal(str(volume_profile.get("value_area_high"))) if volume_profile.get("value_area_high") else None
        val = Decimal(str(volume_profile.get("value_area_low"))) if volume_profile.get("value_area_low") else None

        # Проверяем расстояние от Value Area
        if vah and val:
            # Если цена слишком далеко от Value Area (>5%), отклоняем
            if current_price > vah * Decimal("1.05"):
                reason = "Цена слишком далеко выше Value Area High"
                _update_vp_stats(filter_state, False, reason)
                return False, "%s (%.2f > %.2f)" % (reason, float(current_price), float(vah)), filter_state
            if current_price < val * Decimal("0.95"):
                reason = "Цена слишком далеко ниже Value Area Low"
                _update_vp_stats(filter_state, False, reason)
                return False, "%s (%.2f < %.2f)" % (reason, float(current_price), float(val)), filter_state

        if side.lower() == "long":
            # LONG: цена должна быть вблизи VAL или ниже POC
            if val:
                distance_from_val_pct = abs(current_price - val) / current_price * Decimal("100")
                if distance_from_val_pct <= tolerance_pct:
                    logger.debug(
                        "LONG: цена вблизи VAL (distance=%.2f%%, threshold=%.2f%%)",
                        float(distance_from_val_pct), float(tolerance_pct)
                    )
                    _update_vp_stats(filter_state, True, None)
                    return True, None, filter_state

            if current_price <= poc:
                poc_distance_pct = abs(current_price - poc) / current_price * Decimal("100")
                logger.debug(
                    "LONG: цена ниже POC (price=%.2f, POC=%.2f, distance=%.2f%%)",
                    float(current_price), float(poc), float(poc_distance_pct)
                )
                _update_vp_stats(filter_state, True, None)
                return True, None, filter_state

            if not strict_mode and vah and val:
                if val <= current_price <= vah:
                    if current_price <= poc:
                        poc_distance_pct = abs(current_price - poc) / current_price * Decimal("100")
                        if poc_distance_pct <= tolerance_pct * Decimal("2"):
                            logger.debug(
                                "LONG: цена в Value Area ниже POC (distance=%.2f%%)",
                                float(poc_distance_pct)
                            )
                            _update_vp_stats(filter_state, True, None)
                            return True, None, filter_state
                    else:
                        if val:
                            val_distance_pct = abs(current_price - val) / current_price * Decimal("100")
                            if val_distance_pct <= tolerance_pct * Decimal("1.5"):
                                logger.debug(
                                    "LONG: цена в Value Area выше POC, но близко к VAL (distance=%.2f%%)",
                                    float(val_distance_pct)
                                )
                                _update_vp_stats(filter_state, True, None)
                                return True, None, filter_state

                    reason = "LONG: цена в Value Area, но далеко от POC и VAL"
                    _update_vp_stats(filter_state, False, reason)
                    return False, "%s (price=%.2f, POC=%.2f, VAL=%.2f)" % (reason, float(current_price), float(poc), float(val)), filter_state

            val_str = "%.2f" % float(val) if val else "N/A"
            reason = "LONG: цена не вблизи VAL или ниже POC"
            _update_vp_stats(filter_state, False, reason)
            return False, "%s (price=%.2f, POC=%.2f, VAL=%s)" % (reason, float(current_price), float(poc), val_str), filter_state

        elif side.lower() == "short":
            if vah:
                distance_from_vah_pct = abs(current_price - vah) / current_price * Decimal("100")
                if distance_from_vah_pct <= tolerance_pct:
                    logger.debug(
                        "SHORT: цена вблизи VAH (distance=%.2f%%, threshold=%.2f%%)",
                        float(distance_from_vah_pct), float(tolerance_pct)
                    )
                    _update_vp_stats(filter_state, True, None)
                    return True, None, filter_state

            if current_price >= poc:
                poc_distance_pct = abs(current_price - poc) / current_price * Decimal("100")
                logger.debug(
                    "SHORT: цена выше POC (price=%.2f, POC=%.2f, distance=%.2f%%)",
                    float(current_price), float(poc), float(poc_distance_pct)
                )
                _update_vp_stats(filter_state, True, None)
                return True, None, filter_state

            if not strict_mode and vah and val:
                if val <= current_price <= vah:
                    if current_price >= poc:
                        poc_distance_pct = abs(current_price - poc) / current_price * Decimal("100")
                        if poc_distance_pct <= tolerance_pct * Decimal("2"):
                            logger.debug(
                                "SHORT: цена в Value Area выше POC (distance=%.2f%%)",
                                float(poc_distance_pct)
                            )
                            _update_vp_stats(filter_state, True, None)
                            return True, None, filter_state
                    else:
                        if vah:
                            vah_distance_pct = abs(current_price - vah) / current_price * Decimal("100")
                            if vah_distance_pct <= tolerance_pct * Decimal("1.5"):
                                logger.debug(
                                    "SHORT: цена в Value Area ниже POC, но близко к VAH (distance=%.2f%%)",
                                    float(vah_distance_pct)
                                )
                                _update_vp_stats(filter_state, True, None)
                                return True, None, filter_state

                    reason = "SHORT: цена в Value Area, но далеко от POC и VAH"
                    _update_vp_stats(filter_state, False, reason)
                    return False, "%s (price=%.2f, POC=%.2f, VAH=%.2f)" % (reason, float(current_price), float(poc), float(vah)), filter_state

            vah_str = "%.2f" % float(vah) if vah else "N/A"
            reason = "SHORT: цена не вблизи VAH или выше POC"
            _update_vp_stats(filter_state, False, reason)
            return False, "%s (price=%.2f, POC=%.2f, VAH=%s)" % (reason, float(current_price), float(poc), vah_str), filter_state

        _update_vp_stats(filter_state, True, None)
        return True, None, filter_state

    except Exception as e:
        logger.error("Ошибка в check_volume_profile_filter: %s", e)
        _update_vp_stats(filter_state, True, "ERROR")
        return True, None, filter_state


def _update_vp_stats(
    filter_state: FilterState,
    passed: bool,
    reason: Optional[str] = None
):
    """
    Обновляет статистику работы Volume Profile фильтра (stateless).
    
    Args:
        filter_state: Состояние фильтра
        passed: Прошел ли фильтр
        reason: Причина блокировки (если есть)
    """
    # Инициализируем статистику, если её нет
    if 'total_checked' not in filter_state.stats:
        filter_state.stats['total_checked'] = 0
        filter_state.stats['blocked_count'] = 0
        filter_state.stats['passed_count'] = 0
        filter_state.stats['blocked_by_reason'] = {}
        filter_state.stats['last_log_time'] = None

    filter_state.stats['total_checked'] += 1
    if passed:
        filter_state.stats['passed_count'] += 1
    else:
        filter_state.stats['blocked_count'] += 1
        if reason:
            reason_key = reason.split(':')[0] if ':' in reason else reason
            if 'blocked_by_reason' not in filter_state.stats:
                filter_state.stats['blocked_by_reason'] = {}
            filter_state.stats['blocked_by_reason'][reason_key] = \
                filter_state.stats['blocked_by_reason'].get(reason_key, 0) + 1
    
    # Логируем статистику каждые 100 проверок
    if filter_state.stats['total_checked'] % 100 == 0:
        total = filter_state.stats['total_checked']
        blocked = filter_state.stats['blocked_count']
        passed_count = filter_state.stats['passed_count']
        block_rate = (blocked / total * 100) if total > 0 else 0
        
        logger.info(
            "📊 VP Filter Stats: проверено=%d, пропущено=%d (%.1f%%), "
            "заблокировано=%d (%.1f%%)",
            total, passed_count, (passed_count / total * 100) if total > 0 else 0,
            blocked, block_rate
        )
        
        # Логируем топ-3 причины блокировок
        if filter_state.stats.get('blocked_by_reason'):
            top_reasons = sorted(
                filter_state.stats['blocked_by_reason'].items(),
                key=lambda x: x[1],
                reverse=True
            )[:3]
            logger.info(
                "   Топ причины блокировок: %s",
                ", ".join([f"{r[0]}: {r[1]}" for r in top_reasons])
            )


def get_vp_filter_stats(filter_state: Optional[FilterState] = None) -> Dict[str, Any]:
    """
    Возвращает текущую статистику работы Volume Profile фильтра (stateless).
    
    Args:
        filter_state: Состояние фильтра (опционально)
    
    Returns:
        Словарь со статистикой
    """
    if filter_state is None or 'total_checked' not in filter_state.stats:
        return {
            'total_checked': 0,
            'blocked_count': 0,
            'passed_count': 0,
            'block_rate_pct': 0.0,
            'pass_rate_pct': 0.0,
            'blocked_by_reason': {}
        }
    
    total = filter_state.stats['total_checked']
    if total == 0:
        return {
            'total_checked': 0,
            'blocked_count': 0,
            'passed_count': 0,
            'block_rate_pct': 0.0,
            'pass_rate_pct': 0.0,
            'blocked_by_reason': {}
        }
    
    return {
        'total_checked': filter_state.stats['total_checked'],
        'blocked_count': filter_state.stats['blocked_count'],
        'passed_count': filter_state.stats['passed_count'],
        'block_rate_pct': (filter_state.stats['blocked_count'] / total * 100),
        'pass_rate_pct': (filter_state.stats['passed_count'] / total * 100),
        'blocked_by_reason': filter_state.stats.get('blocked_by_reason', {}).copy()
    }


def reset_vp_filter_stats(filter_state: Optional[FilterState] = None) -> FilterState:
    """
    Сбрасывает статистику работы Volume Profile фильтра (stateless).
    
    Args:
        filter_state: Состояние фильтра (создается автоматически, если None)
    
    Returns:
        Новое состояние фильтра со сброшенной статистикой
    """
    if filter_state is None:
        if FilterState is not None:
            filter_state = FilterState()
        else:
            # Fallback
            filter_state = type('FilterState', (), {
                'cache': {},
                'stats': {}
            })()
    
    filter_state.stats = {
        'total_checked': 0,
        'blocked_count': 0,
        'passed_count': 0,
        'blocked_by_reason': {},
        'last_log_time': None
    }
    
    return filter_state


def check_vwap_filter(
    df: pd.DataFrame,
    i: int,
    side: str,
    vwap_bands: Optional[Dict[str, Any]] = None,
    strict_mode: bool = True,
    filter_state: Optional[FilterState] = None,
) -> Tuple[bool, Optional[str], FilterState]:
    """
    Проверяет, соответствует ли сигнал VWAP фильтрам

    Логика:
    - LONG: цена должна быть ниже VWAP - 1SD (перепроданность)
    - SHORT: цена должна быть выше VWAP + 1SD (перекупленность)
    - В строгом режиме: требуем экстремальные зоны (±2SD)
    """
    if filter_state is None:
        if FilterState is not None:
            filter_state = FilterState()
        else:
            filter_state = type('FilterState', (), {'cache': {}, 'stats': {}})()

    try:
        if not VWAP_AVAILABLE:
            return True, None, filter_state

        if vwap_bands is None:
            try:
                vwap_threshold = Decimal(os.environ.get('vwap_threshold', '1.0'))
                sd_mult_1 = float(Decimal("1.0") * vwap_threshold)
                sd_mult_2 = float(Decimal("2.0") * vwap_threshold)
                sd_multipliers = [sd_mult_1, sd_mult_2]
                
                vwap_calc = VWAPCalculator(sd_multipliers=sd_multipliers)
                vwap = vwap_calc.calculate_daily_vwap(df.iloc[:i+1])
                vwap_bands = vwap_calc.calculate_vwap_bands(vwap, df.iloc[:i+1])
            except Exception as e:
                logger.debug("Не удалось рассчитать VWAP: %s", e)
                return True, None, filter_state

        if not vwap_bands or i >= len(df):
            return True, None, filter_state

        current_price = Decimal(str(df["close"].iloc[i]))
        vwap_val = vwap_bands.get("vwap")
        if vwap_val is None:
            return True, None, filter_state
            
        vwap = Decimal(str(vwap_val.iloc[i] if hasattr(vwap_val, 'iloc') else vwap_val))
        
        upper_band_1 = vwap_bands.get("upper_band_1")
        lower_band_1 = vwap_bands.get("lower_band_1")
        upper_band_2 = vwap_bands.get("upper_band_2")
        lower_band_2 = vwap_bands.get("lower_band_2")

        upper_1 = Decimal(str(upper_band_1.iloc[i] if hasattr(upper_band_1, 'iloc') else upper_band_1)) if upper_band_1 is not None else None
        lower_1 = Decimal(str(lower_band_1.iloc[i] if hasattr(lower_band_1, 'iloc') else lower_band_1)) if lower_band_1 is not None else None
        upper_2 = Decimal(str(upper_band_2.iloc[i] if hasattr(upper_band_2, 'iloc') else upper_band_2)) if upper_band_2 is not None else None
        lower_2 = Decimal(str(lower_band_2.iloc[i] if hasattr(lower_band_2, 'iloc') else lower_band_2)) if lower_band_2 is not None else None

        if side.lower() == "long":
            if strict_mode:
                if lower_2 and current_price <= lower_2:
                    return True, None, filter_state
                lower_2_str = "%.2f" % float(lower_2) if lower_2 else 'N/A'
                return False, "LONG: цена не в зоне экстремальной перепроданности (price=%.2f, VWAP-2SD=%s)" % (float(current_price), lower_2_str), filter_state
            else:
                if lower_1 and current_price <= lower_1:
                    return True, None, filter_state
                lower_1_str = "%.2f" % float(lower_1) if lower_1 else 'N/A'
                return False, "LONG: цена не в зоне перепроданности (price=%.2f, VWAP-1SD=%s)" % (float(current_price), lower_1_str), filter_state

        elif side.lower() == "short":
            if strict_mode:
                if upper_2 and current_price >= upper_2:
                    return True, None, filter_state
                upper_2_str = "%.2f" % float(upper_2) if upper_2 else 'N/A'
                return False, "SHORT: цена не в зоне экстремальной перекупленности (price=%.2f, VWAP+2SD=%s)" % (float(current_price), upper_2_str), filter_state
            else:
                if upper_1 and current_price >= upper_1:
                    return True, None, filter_state
                upper_1_str = "%.2f" % float(upper_1) if upper_1 else 'N/A'
                return False, "SHORT: цена не в зоне перекупленности (price=%.2f, VWAP+1SD=%s)" % (float(current_price), upper_1_str), filter_state

        return True, None, filter_state

    except Exception as e:
        logger.error("Ошибка в check_vwap_filter: %s", e)
        return True, None, filter_state

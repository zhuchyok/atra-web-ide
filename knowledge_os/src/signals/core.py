"""
Основная логика генерации торговых сигналов
Содержит функции strict_entry_signal, soft_entry_signal и связанную логику
"""
# pylint: disable=too-many-lines
# Файл содержит основную логику генерации сигналов, что оправдывает большой размер

import logging
import os
from typing import Optional, Tuple, Any, Dict
from decimal import Decimal

import pandas as pd

logger = logging.getLogger(__name__)

# Модульный счетчик для отладки soft_entry_signal
SOFT_ENTRY_DEBUG_COUNT = 0  # pylint: disable=invalid-name

# Импорты из других модулей
try:
    from src.filters.btc_trend import bollinger_direction_filter
except ImportError:
    bollinger_direction_filter = None
    logger.warning("bollinger_direction_filter недоступен")

# Импорт BB_DIR_NEAR_MID_EPSILON_STRICT
try:
    from config import BB_DIR_NEAR_MID_EPSILON_STRICT
except ImportError:
    try:
        from src.filters.anomaly import BB_DIR_NEAR_MID_EPSILON_STRICT
    except ImportError:
        # Значение по умолчанию
        BB_DIR_NEAR_MID_EPSILON_STRICT = 0.07
        logger.warning("BB_DIR_NEAR_MID_EPSILON_STRICT не найден, используется значение по умолчанию: 0.07")

# Импорты фильтров Volume Profile и VWAP
try:
    from src.signals.filters_volume_vwap import check_volume_profile_filter, check_vwap_filter
    from src.signals.state_container import FilterState
    VP_VWAP_FILTERS_AVAILABLE = True
    FILTER_STATE_AVAILABLE = True
except ImportError:
    VP_VWAP_FILTERS_AVAILABLE = False
    FILTER_STATE_AVAILABLE = False
    FilterState = None
    logger.warning("Фильтры Volume Profile/VWAP недоступны")

# Импорт Market Profile фильтра
try:
    from src.filters.market_profile_filter import check_market_profile_filter
    MARKET_PROFILE_FILTER_AVAILABLE = True
except ImportError:
    MARKET_PROFILE_FILTER_AVAILABLE = False
    logger.warning("Market Profile фильтр недоступен")

# Импорт Order Flow фильтра
try:
    from src.filters.order_flow_filter import check_order_flow_filter
    ORDER_FLOW_FILTER_AVAILABLE = True
except ImportError:
    ORDER_FLOW_FILTER_AVAILABLE = False
    logger.warning("Order Flow фильтр недоступен")

# Импорт Microstructure фильтра
try:
    from src.filters.microstructure_filter import check_microstructure_filter
    MICROSTRUCTURE_FILTER_AVAILABLE = True
except ImportError:
    MICROSTRUCTURE_FILTER_AVAILABLE = False
    logger.warning("Microstructure фильтр недоступен")

# Импорт Momentum фильтра
try:
    from src.filters.momentum_filter import check_momentum_filter
    MOMENTUM_FILTER_AVAILABLE = True
except ImportError:
    MOMENTUM_FILTER_AVAILABLE = False
    logger.warning("Momentum фильтр недоступен")

# Импорт Trend Strength фильтра
try:
    from src.filters.trend_strength_filter import check_trend_strength_filter
    TREND_STRENGTH_FILTER_AVAILABLE = True
except ImportError:
    TREND_STRENGTH_FILTER_AVAILABLE = False
    logger.warning("Trend Strength фильтр недоступен")

# Импорт News и Whale фильтров
try:
    from src.filters.news import check_negative_news
    NEWS_FILTER_AVAILABLE = True
except ImportError:
    NEWS_FILTER_AVAILABLE = False
    check_negative_news = None

try:
    from src.filters.whale import get_whale_signal
    WHALE_FILTER_AVAILABLE = True
except ImportError:
    WHALE_FILTER_AVAILABLE = False
    get_whale_signal = None

# Импорты конфигурации
try:
    from config import (
        USE_VP_FILTER, USE_VWAP_FILTER, USE_ORDER_FLOW_FILTER,
        USE_MICROSTRUCTURE_FILTER, USE_MOMENTUM_FILTER, USE_TREND_STRENGTH_FILTER,
        USE_NEWS_FILTER, USE_WHALE_FILTER
    )
except ImportError:
    USE_VP_FILTER = False
    USE_VWAP_FILTER = False
    USE_ORDER_FLOW_FILTER = False
    USE_MICROSTRUCTURE_FILTER = False
    USE_MOMENTUM_FILTER = False
    USE_TREND_STRENGTH_FILTER = False
    USE_NEWS_FILTER = False
    USE_WHALE_FILTER = False


def _get_safe_indicator(df: pd.DataFrame, i: int, name: str, default: Any = None) -> Any:
    """Безопасное получение значения индикатора из DataFrame"""
    try:
        if name in df.columns:
            val = df[name].iloc[i]
            return val if not pd.isna(val) else default
        return default
    except Exception:
        return default


def _get_optimizer_params(mode: str, symbol: str = 'GLOBAL') -> Dict[str, Any]:
    """Получает динамические параметры из Optimizer."""
    try:
        from src.strategies.auto_optimizer import AutoOptimizer
        optimizer = AutoOptimizer()
        all_params = optimizer.get_current_params(symbol)
        return all_params.get(mode, {})
    except Exception:
        # Fallback на дефолты
        if mode == 'strict':
            return {
                'bb_touch': 1.01,
                'ema_trend': 1.001,
                'rsi_long': 35,
                'rsi_short': 65,
                'volume_ratio': 1.5,
                'volatility': 1.5,
                'momentum': 0.0,
                'trend_strength': 0.6
            }
        else:
            return {
                'bb_touch': 1.05,
                'ema_trend': 0.998,
                'rsi_long': 55,
                'rsi_short': 45,
                'volume_ratio': 0.5,
                'volatility': 0.5,
                'momentum': -0.1,
                'trend_strength': 0.05
            }


def strict_entry_signal(df: pd.DataFrame, i: int) -> Tuple[Optional[str], Optional[Decimal]]:
    """
    СТРОГИЙ режим - высокое качество сигналов.
    """
    if i < 25:
        return None, None

    try:
        current_price = Decimal(str(df["close"].iloc[i]))
        bb_upper = Decimal(str(df["bb_upper"].iloc[i]))
        bb_lower = Decimal(str(df["bb_lower"].iloc[i]))
        ema7 = Decimal(str(df["ema7"].iloc[i]))
        ema25 = Decimal(str(df["ema25"].iloc[i]))
        rsi = Decimal(str(df["rsi"].iloc[i]))
        volume_ratio = Decimal(str(df["volume_ratio"].iloc[i]))
        volatility = Decimal(str(df["volatility"].iloc[i]))
        momentum = Decimal(str(df["momentum"].iloc[i]))
        trend_strength = Decimal(str(df["trend_strength"].iloc[i]))

        symbol_name = df.attrs.get('symbol') or df.columns[0].split('_')[0] if not df.empty else 'UNKNOWN'
        dyn_params = _get_optimizer_params('strict', symbol_name)

        # Параметры из Optimizer
        bb_touch_long = Decimal(str(dyn_params.get('bb_touch', "1.01")))
        bb_touch_short = Decimal("2.0") - bb_touch_long
        ema_trend_long = Decimal(str(dyn_params.get('ema_trend', "1.001")))
        ema_trend_short = Decimal("2.0") - ema_trend_long

        # СТРОГИЕ условия для LONG (динамические)
        long_conditions = [
            current_price <= bb_lower * bb_touch_long,
            ema7 > ema25 * ema_trend_long,
            rsi < Decimal(str(dyn_params.get('rsi_long', "40"))),
            volume_ratio > Decimal(str(dyn_params.get('volume_ratio', "0.8"))),
            volatility > Decimal(str(dyn_params.get('volatility', "0.5"))),
            momentum > Decimal("0.0"),
            trend_strength > Decimal("0.5"),
        ]

        # СТРОГИЕ условия для SHORT (динамические)
        short_conditions = [
            current_price >= bb_upper * bb_touch_short,
            ema7 < ema25 * ema_trend_short,
            rsi > Decimal(str(dyn_params.get('rsi_short', "65"))),
            volume_ratio > Decimal(str(dyn_params.get('volume_ratio', "1.5"))),
            volatility > Decimal(str(dyn_params.get('volatility', "1.5"))),
            momentum < Decimal("0.0"),
            trend_strength > Decimal("0.6"),
        ]

        long_base_ok = all(long_conditions)
        short_base_ok = all(short_conditions)

        # Логирование отклонений
        if not (long_base_ok or short_base_ok):
            from src.utils.filter_logger import log_filter_check
            if not long_base_ok:
                failed = [name for j, name in enumerate(["BB", "EMA", "RSI", "VOL_R", "VOLAT", "MOM", "TREND"]) if not long_conditions[j]]
                log_filter_check(symbol_name, 'strict_base_long', False, f"Failed: {', '.join(failed)}", {"score": sum(long_conditions)})
            if not short_base_ok:
                failed = [name for j, name in enumerate(["BB", "EMA", "RSI", "VOL_R", "VOLAT", "MOM", "TREND"]) if not short_conditions[j]]
                log_filter_check(symbol_name, 'strict_base_short', False, f"Failed: {', '.join(failed)}", {"score": sum(short_conditions)})

        filter_state = FilterState() if FILTER_STATE_AVAILABLE and FilterState else None

        if long_base_ok:
            if VP_VWAP_FILTERS_AVAILABLE and USE_VP_FILTER:
                vp_ok, vp_reason, filter_state = check_volume_profile_filter(
                    df, i, "long", strict_mode=True, filter_state=filter_state
                )
                if not vp_ok:
                    log_filter_check(symbol_name, 'strict_vp_long', False, vp_reason)
                    long_base_ok = False
            
            if long_base_ok:
                return "long", current_price

        if short_base_ok:
            if VP_VWAP_FILTERS_AVAILABLE and USE_VP_FILTER:
                vp_ok, vp_reason, filter_state = check_volume_profile_filter(
                    df, i, "short", strict_mode=True, filter_state=filter_state
                )
                if not vp_ok:
                    log_filter_check(symbol_name, 'strict_vp_short', False, vp_reason)
                    short_base_ok = False
            
            if short_base_ok:
                return "short", current_price

        return None, None

    except Exception as e:
        logger.error("❌ Ошибка в strict_entry_signal: %s", e, exc_info=True)
        return None, None


def soft_entry_signal(df: pd.DataFrame, i: int) -> Tuple[Optional[str], Optional[Decimal]]:
    """
    МЯГКИЙ режим - для более частых входов.
    """
    if i < 20:
        return None, None

    try:
        current_price = Decimal(str(df["close"].iloc[i]))
        bb_upper = Decimal(str(df["bb_upper"].iloc[i]))
        bb_lower = Decimal(str(df["bb_lower"].iloc[i]))
        ema7 = Decimal(str(df["ema7"].iloc[i]))
        ema25 = Decimal(str(df["ema25"].iloc[i]))
        rsi = Decimal(str(df["rsi"].iloc[i]))
        volume_ratio = Decimal(str(df["volume_ratio"].iloc[i]))
        volatility = Decimal(str(df["volatility"].iloc[i]))
        momentum = Decimal(str(df["momentum"].iloc[i]))
        trend_strength = Decimal(str(df["trend_strength"].iloc[i]))

        symbol_name = df.attrs.get('symbol', 'GLOBAL')
        dyn_params = _get_optimizer_params('soft', symbol_name)

        # Параметры из Optimizer
        bb_touch_long = Decimal(str(dyn_params.get('bb_touch', "0.95")))
        bb_touch_short = Decimal("2.0") - bb_touch_long
        ema_trend_long = Decimal(str(dyn_params.get('ema_trend', "0.998")))
        ema_trend_short = Decimal("2.0") - ema_trend_long

        # МЯГКИЕ условия для LONG (динамические)
        long_conditions = [
            current_price <= bb_lower * bb_touch_long,
            ema7 > ema25 * ema_trend_long,
            rsi < Decimal(str(dyn_params.get('rsi_long', "55"))),
            volume_ratio > Decimal(str(dyn_params.get('volume_ratio', "0.5"))),
            volatility > Decimal(str(dyn_params.get('volatility', "0.5"))),
            momentum > Decimal(str(dyn_params.get('momentum', "-0.1"))),
            trend_strength > Decimal(str(dyn_params.get('trend_strength', "0.05"))),
        ]

        # МЯГКИЕ условия для SHORT (динамические)
        short_conditions = [
            current_price >= bb_upper * bb_touch_short,
            ema7 < ema25 * ema_trend_short,
            rsi > Decimal(str(dyn_params.get('rsi_short', "45"))),
            volume_ratio > Decimal(str(dyn_params.get('volume_ratio', "0.5"))),
            volatility > Decimal(str(dyn_params.get('volatility', "0.5"))),
            momentum < Decimal(str(dyn_params.get('momentum', "0.1"))),
            trend_strength > Decimal(str(dyn_params.get('trend_strength', "0.05"))),
        ]

        long_base_ok = all(long_conditions)
        short_base_ok = all(short_conditions)

        # Логирование отклонений
        if not (long_base_ok or short_base_ok):
            from src.utils.filter_logger import log_filter_check
            if not long_base_ok:
                failed = [name for j, name in enumerate(["BB", "EMA", "RSI", "VOL_R", "VOLAT", "MOM", "TREND"]) if not long_conditions[j]]
                log_filter_check(symbol_name, 'soft_base_long', False, f"Failed: {', '.join(failed)}", {"score": sum(long_conditions)})
            if not short_base_ok:
                failed = [name for j, name in enumerate(["BB", "EMA", "RSI", "VOL_R", "VOLAT", "MOM", "TREND"]) if not short_conditions[j]]
                log_filter_check(symbol_name, 'soft_base_short', False, f"Failed: {', '.join(failed)}", {"score": sum(short_conditions)})

        filter_state = FilterState() if FILTER_STATE_AVAILABLE and FilterState else None

        if long_base_ok:
            if VP_VWAP_FILTERS_AVAILABLE and USE_VP_FILTER:
                vp_ok, vp_reason, filter_state = check_volume_profile_filter(
                    df, i, "long", strict_mode=False, filter_state=filter_state
                )
                if not vp_ok:
                    log_filter_check(symbol_name, 'soft_vp_long', False, vp_reason)
                    long_base_ok = False
            
            if long_base_ok:
                return "long", current_price

        if short_base_ok:
            if VP_VWAP_FILTERS_AVAILABLE and USE_VP_FILTER:
                vp_ok, vp_reason, filter_state = check_volume_profile_filter(
                    df, i, "short", strict_mode=False, filter_state=filter_state
                )
                if not vp_ok:
                    log_filter_check(symbol_name, 'soft_vp_short', False, vp_reason)
                    short_base_ok = False
            
            if short_base_ok:
                return "short", current_price

        return None, None

    except Exception as e:
        logger.error("❌ Ошибка в soft_entry_signal: %s", e, exc_info=True)
        return None, None


def enhanced_entry_signal(df: pd.DataFrame, i: int) -> Tuple[Optional[str], Optional[Decimal]]:
    """
    Расширенный режим: проверяет оба режима.
    """
    if i < 25:
        return None, None

    res_strict, price_strict = strict_entry_signal(df, i)
    if res_strict:
        return res_strict, price_strict

    res_soft, price_soft = soft_entry_signal(df, i)
    return res_soft, price_soft


# =====================================================================
# Регистрация базовых функций генерации и основного цикла
# (для устранения циклических импортов с signal_live.py)
# =====================================================================
_GENERATE_SIGNAL_IMPL = None
_RUN_HYBRID_IMPL = None


def register_signal_live_functions(generate_fn, run_fn) -> None:
    """Регистрирует реальные реализации signal_live, чтобы избежать циклических импортов."""
    global _GENERATE_SIGNAL_IMPL, _RUN_HYBRID_IMPL
    _GENERATE_SIGNAL_IMPL = generate_fn
    _RUN_HYBRID_IMPL = run_fn


async def generate_signal_base(*args, **kwargs):
    """Обертка для generate_signal (реализация в signal_live)."""
    if _GENERATE_SIGNAL_IMPL is None:
        return None
    return await _GENERATE_SIGNAL_IMPL(*args, **kwargs)


async def run_hybrid_signal_system_fixed(*args, **kwargs):
    """Обертка для run_hybrid_signal_system_fixed (реализация в signal_live)."""
    if _RUN_HYBRID_IMPL is None:
        return None
    return await _RUN_HYBRID_IMPL(*args, **kwargs)


def get_entry_signal_by_mode(df: pd.DataFrame, i: int, mode: str = "strict") -> Tuple[Optional[str], Optional[Decimal]]:
    """Получает сигнал в зависимости от режима."""
    if mode == "strict":
        return strict_entry_signal(df, i)
    elif mode == "soft":
        return soft_entry_signal(df, i)
    elif mode == "enhanced":
        return enhanced_entry_signal(df, i)
    return None, None


def should_open_long(df: pd.DataFrame, i: int) -> bool:
    """Упрощенная проверка для LONG."""
    side, _ = strict_entry_signal(df, i)
    return side == "long"


def should_open_short(df: pd.DataFrame, i: int) -> bool:
    """Упрощенная проверка для SHORT."""
    side, _ = strict_entry_signal(df, i)
    return side == "short"

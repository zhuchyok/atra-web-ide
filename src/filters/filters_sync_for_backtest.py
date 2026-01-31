"""
Синхронные версии фильтров для использования в бэктестах и оптимизации
Все функции работают синхронно и принимают DataFrame напрямую
"""

import logging
import os
import pandas as pd
import numpy as np
from typing import Tuple, Optional, Dict, Any, List

logger = logging.getLogger(__name__)

# Попытка импорта технических индикаторов
try:
    import talib
    TALIB_AVAILABLE = True
except ImportError:
    TALIB_AVAILABLE = False
    try:
        import pandas_ta as ta
        TA_AVAILABLE = True
    except ImportError:
        TA_AVAILABLE = False


def check_btc_trend_filter_sync(
    df_btc: pd.DataFrame,
    i: int,
    side: str,
    strict_mode: bool = False,
    ema_soft: int = 50,
    ema_strict: int = 200,
    lookback: int = 50,
) -> Tuple[bool, Optional[str]]:
    """
    Синхронная проверка тренда BTC
    
    Args:
        df_btc: DataFrame с данными BTC
        i: Индекс текущей свечи
        side: "long" или "short"
        strict_mode: Строгий режим
        ema_soft: Период EMA для мягкого режима
        ema_strict: Период EMA для строгого режима
        lookback: Период для расчета тренда
    
    Returns:
        Tuple[bool, Optional[str]]: (прошел_фильтр, причина_отклонения)
    """
    try:
        if df_btc is None or len(df_btc) < max(ema_strict, lookback):
            return True, None
        
        if i >= len(df_btc):
            return True, None
        
        current_price = df_btc['close'].iloc[i]
        
        if strict_mode:
            # Строгий режим: цена > EMA(strict) И EMA(short) растет
            if len(df_btc) < ema_strict + 25:
                return True, None
            
            ema_long = df_btc['close'].ewm(span=ema_strict, adjust=False).mean().iloc[i]
            ema_short = df_btc['close'].ewm(span=25, adjust=False).mean()
            
            if i > 0:
                ema_short_growing = ema_short.iloc[i] > ema_short.iloc[i-1]
            else:
                ema_short_growing = True
            
            if side.lower() == "long":
                return (current_price > ema_long) and ema_short_growing, None
            else:  # short
                return (current_price < ema_long) or not ema_short_growing, None
        else:
            # Мягкий режим: цена > EMA(soft)
            if len(df_btc) < ema_soft:
                return True, None
            
            ema = df_btc['close'].ewm(span=ema_soft, adjust=False).mean().iloc[i]
            
            if side.lower() == "long":
                return current_price > ema, None
            else:  # short
                return current_price < ema, None
    except Exception as e:
        logger.debug("Ошибка в check_btc_trend_filter_sync: %s", e)
        return True, None


def check_eth_trend_filter_sync(
    df_eth: pd.DataFrame,
    i: int,
    side: str,
    strict_mode: bool = False,
    ema_soft: int = 50,
    ema_strict: int = 200,
) -> Tuple[bool, Optional[str]]:
    """Синхронная проверка тренда ETH"""
    return check_btc_trend_filter_sync(df_eth, i, side, strict_mode, ema_soft, ema_strict)


def check_sol_trend_filter_sync(
    df_sol: pd.DataFrame,
    i: int,
    side: str,
    strict_mode: bool = False,
    ema_soft: int = 50,
    ema_strict: int = 200,
) -> Tuple[bool, Optional[str]]:
    """Синхронная проверка тренда SOL"""
    return check_btc_trend_filter_sync(df_sol, i, side, strict_mode, ema_soft, ema_strict)


def check_dominance_trend_filter_sync(
    df: pd.DataFrame,
    i: int,
    side: str,
    df_btc: Optional[pd.DataFrame] = None,
    strict_mode: bool = False,
    dominance_threshold_pct: float = 1.0,
    min_days_for_trend: int = 1,
    block_long_on_rising: bool = True,
    block_short_on_falling: bool = True,
) -> Tuple[bool, Optional[str]]:
    """
    Синхронная проверка тренда доминации BTC
    
    Упрощенная версия: использует данные BTC для расчета доминации
    """
    try:
        # Пропускаем BTC и ETH (они не альты относительно BTC)
        symbol = df.get('symbol', '') if hasattr(df, 'get') else ''
        if symbol in ("BTCUSDT", "ETHUSDT"):
            return True, None
        
        if df_btc is None or len(df_btc) < 2:
            return True, None
        
        if i >= len(df) or i >= len(df_btc):
            return True, None
        
        # Упрощенный расчет: сравниваем текущую цену BTC с предыдущей
        # Если BTC растет быстрее альта - доминация растет
        if i < min_days_for_trend:
            return True, None
        
        btc_current = df_btc['close'].iloc[i]
        btc_prev = df_btc['close'].iloc[max(0, i - min_days_for_trend)]
        btc_change_pct = ((btc_current - btc_prev) / btc_prev) * 100
        
        price_current = df['close'].iloc[i]
        price_prev = df['close'].iloc[max(0, i - min_days_for_trend)]
        price_change_pct = ((price_current - price_prev) / price_prev) * 100
        
        # Доминация растет если BTC растет быстрее альта
        dominance_rising = btc_change_pct > price_change_pct + dominance_threshold_pct
        dominance_falling = price_change_pct > btc_change_pct + dominance_threshold_pct
        
        if side.lower() == "long":
            if block_long_on_rising and dominance_rising and abs(btc_change_pct - price_change_pct) >= dominance_threshold_pct:
                return False, f"BTC.D растет ({btc_change_pct:.2f}% vs {price_change_pct:.2f}%)"
            return True, None
        else:  # short
            if block_short_on_falling and dominance_falling and abs(btc_change_pct - price_change_pct) >= dominance_threshold_pct:
                return False, f"BTC.D падает ({btc_change_pct:.2f}% vs {price_change_pct:.2f}%)"
            return True, None
    except Exception as e:
        logger.debug("Ошибка в check_dominance_trend_filter_sync: %s", e)
        return True, None


def check_interest_zone_filter_sync(
    df: pd.DataFrame,
    i: int,
    side: str,
    strict_mode: bool = False,
    lookback_periods: Optional[int] = None,
    min_volume_cluster: Optional[float] = None,
    zone_width_pct: Optional[float] = None,
    min_zone_strength: Optional[float] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Синхронная проверка зон интереса
    """
    try:
        # Читаем параметры из переменных окружения, если не переданы
        if lookback_periods is None:
            lookback_periods = int(os.environ.get('IZ_LOOKBACK_PERIODS', '100'))
        if min_volume_cluster is None:
            min_volume_cluster = float(os.environ.get('IZ_MIN_VOLUME_CLUSTER', '1.5'))
        if zone_width_pct is None:
            zone_width_pct = float(os.environ.get('IZ_ZONE_WIDTH_PCT', '0.5'))
        if min_zone_strength is None:
            min_zone_strength = float(os.environ.get('IZ_MIN_ZONE_STRENGTH', '0.6'))
        
        if i < lookback_periods or len(df) < lookback_periods:
            return True, None
        
        current_price = df['close'].iloc[i]
        df_recent = df.iloc[max(0, i - lookback_periods):i+1].copy()
        
        # Рассчитываем кластеры объема
        avg_volume = df_recent['volume'].mean()
        if avg_volume == 0:
            return True, None
        
        price_min = df_recent['low'].min()
        price_max = df_recent['high'].max()
        num_bins = 20
        bins = np.linspace(price_min, price_max, num_bins + 1)
        
        volume_by_level = {}
        for _, row in df_recent.iterrows():
            for j in range(len(bins) - 1):
                if bins[j] <= row['close'] <= bins[j + 1]:
                    level = (bins[j] + bins[j + 1]) / 2
                    volume_by_level[level] = volume_by_level.get(level, 0) + row['volume']
        
        # Находим зоны с достаточным объемом
        zones = []
        for level, volume_sum in volume_by_level.items():
            volume_ratio = volume_sum / avg_volume if avg_volume > 0 else 0
            if volume_ratio >= min_volume_cluster:
                strength = min(volume_ratio / 3.0, 1.0)
                if strength >= min_zone_strength:
                    zone_width = current_price * (zone_width_pct / 100)
                    zone_low = level - zone_width / 2
                    zone_high = level + zone_width / 2
                    
                    if zone_low <= current_price <= zone_high:
                        if level < current_price:
                            zone_type = "support"
                        else:
                            zone_type = "resistance"
                        zones.append((zone_type, strength))
        
        if not zones:
            return True, None
        
        # Проверяем соответствие зоны направлению
        if side.lower() == "long":
            # LONG: разрешаем в зонах поддержки
            support_zones = [z for z in zones if z[0] == "support"]
            return len(support_zones) > 0, None
        else:  # short
            # SHORT: разрешаем в зонах сопротивления
            resistance_zones = [z for z in zones if z[0] == "resistance"]
            return len(resistance_zones) > 0, None
    except Exception as e:
        logger.debug("Ошибка в check_interest_zone_filter_sync: %s", e)
        return True, None


def check_fibonacci_zone_filter_sync(
    df: pd.DataFrame,
    i: int,
    side: str,
    strict_mode: bool = False,
    lookback_periods: Optional[int] = None,
    tolerance_pct: Optional[float] = None,
    require_strong_levels: Optional[bool] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Синхронная проверка зон Фибоначчи
    """
    try:
        # Читаем параметры из переменных окружения или config.py
        try:
            from config import FIBONACCI_ZONE_FILTER_CONFIG
            default_config = FIBONACCI_ZONE_FILTER_CONFIG
        except ImportError:
            default_config = {}
        
        if lookback_periods is None:
            lookback_periods = int(os.environ.get('FIB_LOOKBACK_PERIODS', default_config.get('lookback_periods', 50)))
        if tolerance_pct is None:
            tolerance_pct = float(os.environ.get('FIB_TOLERANCE_PCT', default_config.get('tolerance_pct', 0.3)))
        if require_strong_levels is None:
            require_strong_levels = os.environ.get('FIB_REQUIRE_STRONG_LEVELS', str(default_config.get('require_strong_levels', False))).lower() == 'true'
        
        if i < lookback_periods or len(df) < lookback_periods:
            return True, None
        
        current_price = df['close'].iloc[i]
        df_recent = df.iloc[max(0, i - lookback_periods):i+1].copy()
        
        # Находим максимум и минимум за период
        high_max = df_recent['high'].max()
        low_min = df_recent['low'].min()
        price_range = high_max - low_min
        
        if price_range == 0:
            return True, None
        
        # Уровни Фибоначчи
        fib_levels = [0.236, 0.382, 0.5, 0.618, 0.786]
        strong_levels = [0.618, 0.382] if require_strong_levels else fib_levels
        
        # Проверяем, находится ли цена на уровне
        for level in fib_levels:
            fib_price = low_min + price_range * level
            distance_pct = abs(current_price - fib_price) / current_price * 100
            
            if distance_pct <= tolerance_pct:
                if side.lower() == "long":
                    # LONG: разрешаем на уровнях поддержки (0.618, 0.786, 0.5)
                    if level in [0.618, 0.786, 0.5]:
                        return True, None
                    else:
                        return False, f"LONG на уровне сопротивления ({level})"
                else:  # short
                    # SHORT: разрешаем на уровнях сопротивления (0.236, 0.382, 0.5)
                    if level in [0.236, 0.382, 0.5]:
                        return True, None
                    else:
                        return False, f"SHORT на уровне поддержки ({level})"
        
        return True, None
    except Exception as e:
        logger.debug("Ошибка в check_fibonacci_zone_filter_sync: %s", e)
        return True, None


def check_volume_imbalance_filter_sync(
    df: pd.DataFrame,
    i: int,
    side: str,
    strict_mode: bool = False,
    lookback_periods: Optional[int] = None,
    volume_spike_threshold: Optional[float] = None,
    min_volume_ratio: Optional[float] = None,
    require_volume_confirmation: Optional[bool] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Синхронная проверка имбаланса объема
    """
    # 🔧 КРИТИЧНО: Проверяем флаг USE_VOLUME_IMBALANCE_FILTER перед проверкой
    try:
        from config import USE_VOLUME_IMBALANCE_FILTER
        if not USE_VOLUME_IMBALANCE_FILTER:
            logger.debug("🔧 [VolumeImbalance] Фильтр ОТКЛЮЧЕН в config, пропускаем проверку")
            return True, None  # Фильтр отключен, пропускаем проверку
        else:
            logger.debug("🔧 [VolumeImbalance] Фильтр ВКЛЮЧЕН в config, выполняем проверку")
    except ImportError:
        # Если config недоступен, используем значение по умолчанию
        logger.warning("⚠️ [VolumeImbalance] config недоступен, пропускаем проверку")
        return True, None
    
    try:
        # Читаем параметры из переменных окружения или config.py
        try:
            from config import VOLUME_IMBALANCE_FILTER_CONFIG
            default_config = VOLUME_IMBALANCE_FILTER_CONFIG
        except ImportError:
            default_config = {}
        
        if lookback_periods is None:
            lookback_periods = int(os.environ.get('VI_LOOKBACK_PERIODS', default_config.get('lookback_periods', 10)))
        if volume_spike_threshold is None:
            volume_spike_threshold = float(os.environ.get('VI_VOLUME_SPIKE_THRESHOLD', default_config.get('volume_spike_threshold', 1.5)))
        if min_volume_ratio is None:
            min_volume_ratio = float(os.environ.get('VI_MIN_VOLUME_RATIO', default_config.get('min_volume_ratio', 1.0)))
        if require_volume_confirmation is None:
            require_volume_confirmation = os.environ.get('VI_REQUIRE_VOLUME_CONFIRMATION', str(default_config.get('require_volume_confirmation', True))).lower() == 'true'
        
        if i < lookback_periods + 1 or len(df) < lookback_periods + 1:
            return True, None
        
        df_recent = df.iloc[max(0, i - lookback_periods):i+1].copy()
        
        current_volume = float(df_recent['volume'].iloc[-1])
        current_close = float(df_recent['close'].iloc[-1])
        prev_close = float(df_recent['close'].iloc[-2]) if len(df_recent) > 1 else current_close
        avg_volume = float(df_recent['volume'].iloc[:-1].mean()) if len(df_recent) > 1 else current_volume
        
        if avg_volume == 0:
            return True, None
        
        volume_ratio = current_volume / avg_volume
        spike_detected = volume_ratio >= volume_spike_threshold
        
        if not require_volume_confirmation:
            return True, None
        
        if not spike_detected:
            return False, f"Нет скачка объема (ratio={volume_ratio:.2f} < {volume_spike_threshold})"
        
        # Проверяем соответствие направления
        price_change_pct = ((current_close - prev_close) / prev_close) * 100 if prev_close > 0 else 0
        
        if side.lower() == "long":
            # LONG: требуется рост цены при скачке объема
            if price_change_pct > 0.5 and volume_ratio >= min_volume_ratio:
                return True, None
            else:
                return False, f"Нет подтверждения объемом для LONG (price_change={price_change_pct:.2f}%, volume_ratio={volume_ratio:.2f})"
        else:  # short
            # SHORT: требуется падение цены при скачке объема
            if price_change_pct < -0.5 and volume_ratio >= min_volume_ratio:
                return True, None
            else:
                return False, f"Нет подтверждения объемом для SHORT (price_change={price_change_pct:.2f}%, volume_ratio={volume_ratio:.2f})"
    except Exception as e:
        logger.debug("Ошибка в check_volume_imbalance_filter_sync: %s", e)
        return True, None


def check_news_filter_sync(
    symbol: str,
    side: str,
    strict_mode: bool = False,
    min_sentiment_score: float = 0.3,
    block_long_on_negative: bool = True,
    block_short_on_positive: bool = True,
) -> Tuple[bool, Optional[str]]:
    """
    Синхронная проверка новостей
    
    Упрощенная версия: в бэктесте всегда разрешаем (нет доступа к новостям)
    """
    # В бэктесте нет доступа к новостям, поэтому всегда разрешаем
    return True, None


def check_whale_filter_sync(
    symbol: str,
    side: str,
    strict_mode: bool = False,
    min_whale_size_usdt: float = 1000000,
    activity_threshold: float = 0.5,
    time_window_minutes: int = 60,
) -> Tuple[bool, Optional[str]]:
    """
    Синхронная проверка активности китов
    
    Упрощенная версия: в бэктесте всегда разрешаем (нет доступа к данным китов)
    """
    # В бэктесте нет доступа к данным китов, поэтому всегда разрешаем
    return True, None


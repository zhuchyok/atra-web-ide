#!/usr/bin/env python3
# pylint: disable=too-many-lines,invalid-name,wrong-import-position,import-outside-toplevel,line-too-long,too-many-function-args
"""
Исправленная гибридная система сигналов с ИИ-оптимизированными параметрами
"""

import asyncio
import concurrent.futures
import csv
import hashlib
import json
import logging
import os
import time
import uuid
import warnings
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import numpy as np
import pandas as pd  # type: ignore

from src.shared.utils.datetime_utils import get_utc_now  # type: ignore

logger = logging.getLogger(__name__)
if not logger.handlers:
    logger.addHandler(logging.StreamHandler())

try:
    from src.infrastructure.self_healing.manager import SelfHealingManager  # type: ignore
    from src.risk.autonomous.stuck_monitor import StuckPositionMonitor  # type: ignore

    SELF_HEALING_AVAILABLE = True
    STUCK_MONITOR_AVAILABLE = True
except ImportError:
    SELF_HEALING_AVAILABLE = False
    STUCK_MONITOR_AVAILABLE = False
    SelfHealingManager = None
    StuckPositionMonitor = None

# 🔧 ИСПРАВЛЕНО: Все observability импорты в try-except для защиты от ошибок
authorize_agent_action = None
get_guidance = None
get_lm_judge = None
get_prompt_manager = None
get_context_engine = None

try:
    from observability.agent_identity import authorize_agent_action  # type: ignore
    from observability.context_engine import get_context_engine  # type: ignore
    from observability.guidance import get_guidance  # type: ignore
    from observability.lm_judge import get_lm_judge  # type: ignore
    from observability.prompt_manager import get_prompt_manager  # type: ignore
except (ImportError, AttributeError, Exception):
    logger.warning("⚠️ Некоторые модули observability недоступны")

# Импортируем Адаптивный Регулятор Фильтров (от команды экспертов)
try:
    from src.ai.adaptive_filter_regulator import get_adaptive_regulator  # type: ignore

    ADAPTIVE_REGULATOR_AVAILABLE = True
except ImportError:
    ADAPTIVE_REGULATOR_AVAILABLE = False
    get_adaptive_regulator = None
    logger.warning("⚠️ AdaptiveFilterRegulator недоступен")

# Подавляем RuntimeWarning о необработанных корутинах (возникает при таймауте в asyncio.wait_for)
warnings.filterwarnings("ignore", category=RuntimeWarning, module="signal_live")
warnings.filterwarnings("ignore", category=RuntimeWarning, module="asyncio")

# Импортируем SourcesHub для централизованного получения данных
try:
    from src.data.sources_hub import sources_hub  # type: ignore

    SOURCES_HUB_AVAILABLE = True
    logger.info("✅ SourcesHub доступен для использования")
except ImportError as e:
    SOURCES_HUB_AVAILABLE = False
    logger.warning("⚠️ SourcesHub недоступен: %s", e)
    sources_hub = None

try:
    from src.filters.news import get_symbol_news_analysis  # type: ignore
except ImportError:
    get_symbol_news_analysis = None

try:
    from src.strategies.pair_filtering import (
        get_filtered_top_usdt_pairs_fast as _get_pairs_fast,  # type: ignore
    )
except ImportError:
    try:
        from src.execution.exchange_api import (
            get_filtered_top_usdt_pairs_fast as _get_pairs_fast,  # type: ignore
        )
    except ImportError:
        _get_pairs_fast = None


async def get_filtered_top_usdt_pairs_fast(top_n=500, final_limit=200):
    """
    Быстрое получение отфильтрованных топ пар USDT.
    """
    if _get_pairs_fast is None:
        return []
    if asyncio.iscoroutinefunction(_get_pairs_fast):
        return await _get_pairs_fast(top_n=top_n, final_limit=final_limit)
    return _get_pairs_fast(top_n=top_n, final_limit=final_limit)


# Импортируем Correlation Risk Manager
try:
    from src.risk.correlation_risk import get_correlation_manager  # type: ignore

    CORRELATION_MANAGER_AVAILABLE = True
    correlation_manager = get_correlation_manager()
    logger.info("✅ CorrelationRiskManager доступен")
except ImportError as e:
    CORRELATION_MANAGER_AVAILABLE = False
    correlation_manager = None
    logger.warning("⚠️ CorrelationRiskManager недоступен: %s", e)

try:
    from src.risk.risk_manager import risk_manager  # type: ignore

    RISK_MANAGER_AVAILABLE = True
except ImportError:
    RISK_MANAGER_AVAILABLE = False
    risk_manager = None

# Импортируем реальную функцию загрузки пользователей
try:
    from src.utils.user_utils import load_user_data_for_signals  # type: ignore
except ImportError:
    logger.warning("⚠️ src.utils.user_utils недоступен, используем fallback")

    def load_user_data_for_signals():
        """Заглушка для загрузки данных пользователей."""
        return {}


try:
    from src.utils.shared_utils import get_dynamic_tp_levels  # type: ignore
except ImportError:
    logger.warning("⚠️ src.utils.shared_utils недоступен, используем fallback")

    def get_dynamic_tp_levels(*args, **kwargs):
        """Заглушка для получения динамических TP уровней."""
        return None


try:
    from src.signals.risk import get_dynamic_sl_level  # type: ignore
except ImportError:
    logger.warning("⚠️ src.signals.risk недоступен, используем fallback")

    def get_dynamic_sl_level(*args, **kwargs):
        """Заглушка для получения динамического SL уровня."""
        return None


try:
    from src.signals.filters import check_eth_alignment, check_sol_alignment  # type: ignore
except ImportError:
    logger.warning("⚠️ src.signals.filters недоступен, используем fallback")

    def check_eth_alignment(*args, **kwargs):
        """Заглушка для проверки сонаправленности ETH."""
        return True, "fallback"

    def check_sol_alignment(*args, **kwargs):
        """Заглушка для проверки сонаправленности SOL."""
        return True, "fallback"
# USE_ETH_TREND_FILTER и USE_SOL_TREND_FILTER не используются, удалены

# Импортируем ATRA_ENV для проверки окружения (нужен для авто-исполнения)
try:
    from config import ATRA_ENV  # type: ignore
except ImportError:
    ATRA_ENV = os.getenv("ATRA_ENV", "prod")  # Fallback на переменную окружения

# Определение STABLECOIN_SYMBOLS (fallback если не определен в config)
try:
    from config import STABLECOIN_SYMBOLS  # type: ignore
except ImportError:
    STABLECOIN_SYMBOLS = [
        "USDTUSDT",
        "USDCUSDT",
        "BUSDUSDT",
        "FDUSDUSDT",
        "TUSDUSDT",
        "USDDUSDT",
        "USDEUSDT",
        "DAIUSDT",
        "FRAXUSDT",
        "LUSDUSDT",
        "USTCUSDT",
        "USTUSDT",
        "MIMUSDT",
        "ALGUSDT",
        "EURSUSDT",
        "USD1USDT",
    ]

# Кэширование списка монет из API (обновляется раз в сутки)
_api_coins_cache: Optional[List[str]] = None
_api_coins_cache_timestamp: Optional[float] = None
API_COINS_CACHE_TTL = 86400  # 24 часа в секундах

# 🔧 ДОБАВЛЕНО: Кэш символов Bitget для фильтрации листинга
_bitget_symbols_cache: Optional[List[str]] = None
_bitget_symbols_cache_timestamp: Optional[float] = None
BITGET_SYMBOLS_CACHE_TTL = 43200  # 12 часов в секундах


async def get_bitget_futures_symbols() -> List[str]:
    """Получает список всех доступных символов на фьючерсах Bitget"""
    global _bitget_symbols_cache, _bitget_symbols_cache_timestamp

    current_time = time.time()
    if (
        _bitget_symbols_cache is not None
        and _bitget_symbols_cache_timestamp is not None
        and current_time - _bitget_symbols_cache_timestamp < BITGET_SYMBOLS_CACHE_TTL
    ):
        return _bitget_symbols_cache

    try:
        logger.info("🔄 [LISTING] Обновление списка символов Bitget Futures...")
        import ccxt

        exchange = ccxt.bitget()
        markets = await asyncio.to_thread(exchange.load_markets)

        # Фильтруем только фьючерсы (swap/futures) и пары к USDT
        symbols = []
        for _, market in markets.items():
            # Проверяем что это фьючерс и котируется в USDT
            if (
                market.get("type") in ("swap", "futures", "linear")
                and market.get("settle") == "USDT"
            ):
                # Преобразуем формат ccxt (BTC/USDT:USDT) в наш формат (BTCUSDT)
                # Bitget фьючерсы обычно имеют ID типа BTCUSDT_UMCBL, но символ BTC/USDT:USDT
                base = market.get("base")
                quote = market.get("quote")
                if base and quote == "USDT":
                    clean_symbol = f"{base}{quote}"
                    symbols.append(clean_symbol)

        if symbols:
            _bitget_symbols_cache = symbols
            _bitget_symbols_cache_timestamp = current_time
            logger.info(
                "✅ [LISTING] Список символов Bitget Futures обновлен (%d монет)", len(symbols)
            )
            return symbols

    except Exception as e:
        logger.warning("⚠️ [LISTING] Не удалось получить символы Bitget: %s", e)
        if _bitget_symbols_cache:
            return _bitget_symbols_cache

    return []


# Импортируем детектор статических уровней
try:
    # pylint: disable=ungrouped-imports
    from src.filters.static_levels import get_levels_detector  # type: ignore

    LEVELS_DETECTOR_AVAILABLE = True
    levels_detector = get_levels_detector()
    logger.info("✅ StaticLevelsDetector доступен")
except ImportError as e:
    LEVELS_DETECTOR_AVAILABLE = False
    levels_detector = None
    logger.warning("⚠️ StaticLevelsDetector недоступен: %s", e)

# Импортируем детектор рыночных режимов
try:
    from src.data.market_regime import get_regime_detector  # type: ignore

    REGIME_DETECTOR_AVAILABLE = True
    regime_detector = get_regime_detector()
    logger.info("✅ MarketRegimeDetector доступен")
except ImportError as e:
    REGIME_DETECTOR_AVAILABLE = False
    regime_detector = None
    logger.warning("⚠️ MarketRegimeDetector недоступен: %s", e)

# 📊 Импортируем Prometheus метрики (Елена + Сергей)
PROMETHEUS_METRICS_AVAILABLE = False
try:
    from src.monitoring.prometheus import (  # type: ignore
        record_ml_prediction,
        record_signal_accepted,
        record_signal_generated,
        record_signal_rejected,
    )

    PROMETHEUS_METRICS_AVAILABLE = True
    logger.info("✅ Prometheus metrics available")
except ImportError:
    logger.debug("⚠️ Prometheus metrics not available")

# 🚀 Инициализация Rust-акселератора индикаторов
try:
    from src.domain.services.indicator_calculator import IndicatorCalculator  # type: ignore

    indicator_calculator = IndicatorCalculator()
    RUST_INDICATORS_AVAILABLE = True
    logger.info("✅ Rust IndicatorCalculator инициализирован")
except ImportError as e:
    RUST_INDICATORS_AVAILABLE = False
    indicator_calculator = None
    logger.warning("⚠️ Rust IndicatorCalculator недоступен: %s", e)

# Импортируем новые фильтры: Dominance Trend, Interest Zone, Fibonacci, Volume Imbalance
try:
    # pylint: disable=ungrouped-imports
    from config import (  # type: ignore # pylint: disable=ungrouped-imports
        ATRA_ENV,
        DOMINANCE_FILTER_CONFIG,
        FIBONACCI_ZONE_FILTER_CONFIG,
        INSTITUTIONAL_PATTERNS_FILTER_CONFIG,
        INTEREST_ZONE_FILTER_CONFIG,
        USE_DOMINANCE_TREND_FILTER,
        USE_FIBONACCI_ZONE_FILTER,
        USE_INSTITUTIONAL_PATTERNS_FILTER,
        USE_INTEREST_ZONE_FILTER,
        USE_VOLUME_IMBALANCE_FILTER,
        VOLUME_IMBALANCE_FILTER_CONFIG,
    )
    from src.filters.dominance_trend import DominanceTrendFilter  # type: ignore
    from src.filters.fibonacci_zone import FibonacciZoneFilter  # type: ignore
    from src.filters.interest_zone import InterestZoneFilter  # type: ignore
    from src.filters.volume_imbalance import VolumeImbalanceFilter  # type: ignore
    from src.technical.fibonacci import FibonacciCalculator  # type: ignore

    NEW_FILTERS_AVAILABLE = True

    # Инициализируем фильтры
    dominance_filter = (
        DominanceTrendFilter(enabled=USE_DOMINANCE_TREND_FILTER, **DOMINANCE_FILTER_CONFIG)
        if USE_DOMINANCE_TREND_FILTER
        else None
    )

    interest_zone_filter = (
        InterestZoneFilter(enabled=USE_INTEREST_ZONE_FILTER, **INTEREST_ZONE_FILTER_CONFIG)
        if USE_INTEREST_ZONE_FILTER
        else None
    )

    fibonacci_filter = (
        FibonacciZoneFilter(enabled=USE_FIBONACCI_ZONE_FILTER, **FIBONACCI_ZONE_FILTER_CONFIG)
        if USE_FIBONACCI_ZONE_FILTER
        else None
    )

    volume_imbalance_filter = (
        VolumeImbalanceFilter(enabled=USE_VOLUME_IMBALANCE_FILTER, **VOLUME_IMBALANCE_FILTER_CONFIG)
        if USE_VOLUME_IMBALANCE_FILTER
        else None
    )

    # Инициализируем FibonacciCalculator для динамических TP/SL
    fibonacci_calculator = FibonacciCalculator() if USE_FIBONACCI_ZONE_FILTER else None

    if dominance_filter:
        logger.info("✅ DominanceTrendFilter инициализирован")
    if interest_zone_filter:
        logger.info("✅ InterestZoneFilter инициализирован")
    if fibonacci_filter:
        logger.info("✅ FibonacciZoneFilter инициализирован")
    if volume_imbalance_filter:
        logger.info("✅ VolumeImbalanceFilter инициализирован")
except (ImportError, Exception) as e:
    NEW_FILTERS_AVAILABLE = False
    dominance_filter = None
    interest_zone_filter = None
    fibonacci_filter = None
    volume_imbalance_filter = None
    fibonacci_calculator = None
    logger.warning(
        "⚠️ Новые фильтры (Dominance/InterestZone/Fibonacci/VolumeImbalance) недоступны: %s", e
    )

# Импорт Institutional Patterns фильтра (синхронный)
try:
    # pylint: disable=ungrouped-imports
    from src.filters.institutional_patterns_filter import (
        check_institutional_patterns_filter,  # type: ignore
    )

    INSTITUTIONAL_PATTERNS_FILTER_AVAILABLE = True
    logger.info("✅ Institutional Patterns фильтр доступен")
except ImportError as e:
    INSTITUTIONAL_PATTERNS_FILTER_AVAILABLE = False
    check_institutional_patterns_filter = None
    logger.warning("⚠️ Institutional Patterns фильтр недоступен: %s", e)

# Импортируем SmartTrendFilter для умной проверки трендов
try:
    from src.filters.smart_trend_filter import (
        get_smart_trend_filter,  # type: ignore # pylint: disable=ungrouped-imports
    )

    SMART_TREND_FILTER_AVAILABLE = True
    smart_trend_filter = get_smart_trend_filter()
    logger.info("✅ SmartTrendFilter доступен для использования")
except ImportError as e:
    SMART_TREND_FILTER_AVAILABLE = False
    smart_trend_filter = None
    logger.warning("⚠️ SmartTrendFilter недоступен: %s", e)

# 🆕 ИМПОРТ НОВЫХ МОДУЛЕЙ ДЛЯ УЛУЧШЕНИЯ ТОЧЕК ВХОДА
try:
    from config import (  # type: ignore # pylint: disable=ungrouped-imports
        PULLBACK_ENTRY_CONFIG,
        USE_ADAPTIVE_STRATEGY,
        USE_PULLBACK_ENTRY,
    )
    from src.analysis.pullback_entry import (
        PullbackEntryLogic,  # type: ignore # pylint: disable=ungrouped-imports
    )

    NEW_ENTRY_LOGIC_AVAILABLE = True

    if USE_PULLBACK_ENTRY:
        pullback_entry_logic = PullbackEntryLogic(use_adaptive_strategy=USE_ADAPTIVE_STRATEGY)
        if USE_ADAPTIVE_STRATEGY:
            logger.info("✅ Новая логика входа на откате инициализирована с адаптивной стратегией")
        else:
            logger.info("✅ Новая логика входа на откате инициализирована")
    else:
        pullback_entry_logic = None
        logger.info("ℹ️ Новая логика входа на откате отключена (USE_PULLBACK_ENTRY=false)")
except (ImportError, Exception) as e:
    NEW_ENTRY_LOGIC_AVAILABLE = False
    pullback_entry_logic = None
    logger.warning("⚠️ Новая логика входа на откате недоступна: %s", e)

# Импортируем композитный движок сигналов
try:
    # pylint: disable=ungrouped-imports
    from src.strategies.composite_engine import get_composite_engine  # type: ignore

    COMPOSITE_ENGINE_AVAILABLE = True
    composite_engine = get_composite_engine()
    logger.info("✅ CompositeSignalEngine доступен")
except ImportError as e:
    COMPOSITE_ENGINE_AVAILABLE = False
    composite_engine = None
    logger.warning("⚠️ CompositeSignalEngine недоступен: %s", e)

# Импортируем MTF Confirmation
try:
    from src.filters.mtf_confirmation import check_mtf_confirmation  # type: ignore

    MTF_CONFIRMATION_AVAILABLE = True
    logger.info("✅ MTF Confirmation доступен")
except ImportError as e:
    MTF_CONFIRMATION_AVAILABLE = False
    check_mtf_confirmation = None
    logger.warning("⚠️ MTF Confirmation недоступен: %s", e)

# Импортируем Гибридную MTF систему
try:
    from src.analysis.hybrid_mtf import HybridMTFConfirmation  # type: ignore

    HYBRID_MTF_AVAILABLE = True
    logger.info("✅ HybridMTFConfirmation доступен")
except ImportError as e:
    HYBRID_MTF_AVAILABLE = False
    HybridMTFConfirmation = None
    logger.warning("⚠️ HybridMTFConfirmation недоступен: %s", e)

# Импортируем систему trailing stop
try:
    from src.execution.trailing_stop import get_trailing_manager  # type: ignore

    TRAILING_STOP_AVAILABLE = True
    trailing_manager = get_trailing_manager()
    logger.info("✅ TrailingStopManager доступен")
except ImportError as e:
    TRAILING_STOP_AVAILABLE = False
    trailing_manager = None
    logger.warning("⚠️ TrailingStopManager недоступен: %s", e)

# Импортируем систему частичного тейк-профита
try:
    from src.execution.partial_profit import get_partial_manager  # type: ignore

    PARTIAL_TP_AVAILABLE = True
    partial_manager = get_partial_manager()
    logger.info("✅ PartialProfitManager доступен")
except ImportError as e:
    PARTIAL_TP_AVAILABLE = False
    partial_manager = None
    logger.warning("⚠️ PartialProfitManager недоступен: %s", e)

# Импортируем систему адаптивного sizing
try:
    from src.adapters.position_sizer import get_adaptive_sizer  # type: ignore

    ADAPTIVE_SIZER_AVAILABLE = True
    adaptive_sizer = get_adaptive_sizer()
    logger.info("✅ AdaptivePositionSizer доступен")
except ImportError as e:
    ADAPTIVE_SIZER_AVAILABLE = False
    adaptive_sizer = None
    logger.warning("⚠️ AdaptivePositionSizer недоступен: %s", e)

# Импортируем детектор ложных пробоев
try:
    from src.filters.false_breakout import get_false_breakout_detector  # type: ignore

    FALSE_BREAKOUT_DETECTOR_AVAILABLE = True
    false_breakout_detector = get_false_breakout_detector()
    logger.info("✅ FalseBreakoutDetector доступен")
except ImportError as e:
    FALSE_BREAKOUT_DETECTOR_AVAILABLE = False
    false_breakout_detector = None
    logger.warning("⚠️ FalseBreakoutDetector недоступен: %s", e)

# Импортируем risk flags
try:
    from src.risk.flags import get_default_manager as _get_risk_flags_manager  # type: ignore

    RISK_FLAGS_AVAILABLE = True
    risk_flags_manager = _get_risk_flags_manager()
    logger.info("✅ RiskFlagsManager доступен")
except ImportError as e:
    RISK_FLAGS_AVAILABLE = False
    risk_flags_manager = None
    logger.warning("⚠️ RiskFlagsManager недоступен: %s", e)

# ========================================================================
# Вспомогательные логгеры событий (FalseBreakout/MTF) → База данных
# ========================================================================
_mtf_event_db = None
_sizing_audit_db = None


def _log_mtf_event(
    symbol: str,
    direction: str,
    confirmed: Optional[bool],
    error_text: Optional[str],
    regime_data: Optional[Dict[str, Any]],
) -> None:
    """Сохраняет результат MTF-подтверждения в БД."""
    global _mtf_event_db
    try:
        if _mtf_event_db is None:
            from src.database.db import (
                Database,  # type: ignore  # type: ignore # локальный импорт, чтобы избежать циклов
            )

            _mtf_event_db = Database()

        with _mtf_event_db.get_lock():
            _mtf_event_db.cursor.execute(
                """
                INSERT INTO mtf_confirmation_events(
                    symbol,
                    direction,
                    confirmed,
                    error,
                    regime,
                    regime_confidence
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    symbol,
                    direction.upper() if direction else None,
                    None if confirmed is None else (1 if confirmed else 0),
                    error_text,
                    (regime_data or {}).get("regime") if regime_data else None,
                    (regime_data or {}).get("confidence") if regime_data else None,
                ),
            )
            _mtf_event_db.conn.commit()
    except Exception as db_err:
        logger.debug("⚠️ Не удалось записать mtf_confirmation_events: %s", db_err)


def _log_position_sizing_event(event: Dict[str, Any]) -> None:
    """Сохраняет подробности расчёта размера позиции в БД."""
    global _sizing_audit_db
    if not event:
        return

    try:
        if _sizing_audit_db is None:
            from src.database.db import (
                Database,  # type: ignore  # type: ignore # локальный импорт для избежания циклов
            )

            _sizing_audit_db = Database()

        _sizing_audit_db.insert_position_sizing_event(event)
    except Exception as err:  # noqa: BLE001
        logger.debug("⚠️ Не удалось записать position_sizing_events: %s", err)


async def _get_data_with_fallback(symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    """
    Получение данных с fallback на другие таймфреймы и правильной агрегацией

    Args:
        symbol: Торговый символ
        timeframe: Целевой таймфрейм ('4h', '1h', '2h', etc.)

    Returns:
        pd.DataFrame или None при ошибке
    """
    try:
        # Используем функцию из exchange_api (уже импортирована в signal_live.py на строке 1620)
        # Не импортируем повторно, чтобы избежать предупреждения линтера
        from src.execution import (
            exchange_api,  # type: ignore # pylint: disable=import-outside-toplevel
        )

        _get_ohlc = exchange_api.get_ohlc_with_fallback

        # Пробуем получить данные напрямую
        ohlc_data = await _get_ohlc(symbol, interval=timeframe, limit=100)
        if ohlc_data and len(ohlc_data) >= 20:
            df = pd.DataFrame(ohlc_data)
            # Проверяем наличие необходимых колонок
            required_cols = ["open", "high", "low", "close", "volume"]
            if all(col in df.columns for col in required_cols):
                return df

        # ⚡ OPTIMIZATION (Алексей): Параллельные fallback запросы
        # Fallback логика с правильной агрегацией
        if timeframe == "4h":
            # Для 4h пробуем получить 2h и агрегировать
            # Запрос выполняется асинхронно, но это fallback - оптимизация не критична
            df_2h = await _get_ohlc(symbol, "2h", limit=200)
            if df_2h and len(df_2h) >= 40:
                df_2h_df = pd.DataFrame(df_2h)
                # Правильная агрегация 2h -> 4h через resample
                if "timestamp" in df_2h_df.columns:
                    df_2h_df["timestamp"] = pd.to_datetime(df_2h_df["timestamp"], unit="ms")
                else:
                    df_2h_df["timestamp"] = pd.date_range(
                        end=pd.Timestamp.now(), periods=len(df_2h_df), freq="2h"
                    )

                df_2h_df = df_2h_df.set_index("timestamp")
                df_4h = (
                    df_2h_df.resample("4H")
                    .agg(
                        {
                            "open": "first",
                            "high": "max",
                            "low": "min",
                            "close": "last",
                            "volume": "sum",
                        }
                    )
                    .dropna()
                )

                if len(df_4h) >= 20:
                    logger.debug(
                        "✅ %s: Используем 2h→4h агрегацию (%d свечей)", symbol, len(df_4h)
                    )
                    return df_4h.reset_index()

        elif timeframe == "1h":
            # Для H1 пробуем получить 30m
            df_30m = await _get_ohlc(symbol, "30m", limit=240)
            if df_30m and len(df_30m) >= 60:
                df_30m_df = pd.DataFrame(df_30m)
                # Правильная агрегация 30m -> 1h
                if "timestamp" in df_30m_df.columns:
                    df_30m_df["timestamp"] = pd.to_datetime(df_30m_df["timestamp"], unit="ms")
                else:
                    df_30m_df["timestamp"] = pd.date_range(
                        end=pd.Timestamp.now(), periods=len(df_30m_df), freq="30min"
                    )

                df_30m_df = df_30m_df.set_index("timestamp")
                df_1h = (
                    df_30m_df.resample("1H")
                    .agg(
                        {
                            "open": "first",
                            "high": "max",
                            "low": "min",
                            "close": "last",
                            "volume": "sum",
                        }
                    )
                    .dropna()
                )

                if len(df_1h) >= 30:
                    logger.debug(
                        "✅ %s: Используем 30m→1h агрегацию (%d свечей)", symbol, len(df_1h)
                    )
                    return df_1h.reset_index()

        logger.warning("⚠️ %s: Не удалось получить данные для %s", symbol, timeframe)
        return None

    except Exception as e:
        logger.error("❌ Ошибка получения данных %s для %s: %s", timeframe, symbol, e)
        return None


async def _get_market_context_with_sol(
    regime_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Получение рыночного контекста с данными BTC, ETH и SOL

    Args:
        regime_data: Существующие данные режима (опционально)

    Returns:
        Dict с btc_change_12h, eth_change_12h, sol_change_12h и другими данными
    """
    try:
        # Используем функцию из exchange_api (уже импортирована в signal_live.py на строке 1620)
        # Не импортируем повторно, чтобы избежать предупреждения линтера
        from src.execution import (
            exchange_api,  # type: ignore # pylint: disable=import-outside-toplevel
        )

        _get_ohlc = exchange_api.get_ohlc_with_fallback

        context = {
            "btc_change_12h": 0.0,
            "eth_change_12h": 0.0,
            "sol_change_12h": 0.0,  # ✅ ДОБАВЛЕНО
            "market_regime": "NEUTRAL",
            "overall_trend": "NEUTRAL",
        }

        # ⚡ OPTIMIZATION (Алексей): Параллельные запросы вместо последовательных
        # Ускорение в 2-3 раза для получения рыночного контекста
        btc_task = _get_ohlc("BTCUSDT", "1h", limit=13)
        eth_task = _get_ohlc("ETHUSDT", "1h", limit=13)
        sol_task = _get_ohlc("SOLUSDT", "1h", limit=13)

        # Выполняем все запросы параллельно
        btc_data, eth_data, sol_data = await asyncio.gather(
            btc_task, eth_task, sol_task, return_exceptions=True
        )

        # Обрабатываем результаты BTC
        if btc_data and not isinstance(btc_data, Exception) and len(btc_data) >= 13:
            btc_df = pd.DataFrame(btc_data)
            current_price = float(btc_df["close"].iloc[-1])
            price_12h_ago = float(btc_df["close"].iloc[-13])
            context["btc_change_12h"] = (
                (current_price - price_12h_ago) / price_12h_ago if price_12h_ago > 0 else 0.0
            )

        # Обрабатываем результаты ETH
        if eth_data and not isinstance(eth_data, Exception) and len(eth_data) >= 13:
            eth_df = pd.DataFrame(eth_data)
            current_price = float(eth_df["close"].iloc[-1])
            price_12h_ago = float(eth_df["close"].iloc[-13])
            context["eth_change_12h"] = (
                (current_price - price_12h_ago) / price_12h_ago if price_12h_ago > 0 else 0.0
            )

        # Обрабатываем результаты SOL
        if sol_data and not isinstance(sol_data, Exception) and len(sol_data) >= 13:
            sol_df = pd.DataFrame(sol_data)
            current_price = float(sol_df["close"].iloc[-1])
            price_12h_ago = float(sol_df["close"].iloc[-13])
            context["sol_change_12h"] = (
                (current_price - price_12h_ago) / price_12h_ago if price_12h_ago > 0 else 0.0
            )

        # Добавляем данные режима если есть
        if regime_data:
            context["market_regime"] = regime_data.get("regime", "NEUTRAL")
            context["overall_trend"] = (
                "BULLISH"
                if context["market_regime"] == "BULL_TREND"
                else ("BEARISH" if context["market_regime"] == "BEAR_TREND" else "NEUTRAL")
            )

        return context

    except Exception as e:
        logger.error("❌ Ошибка получения рыночного контекста: %s", e)
        return {
            "btc_change_12h": 0.0,
            "eth_change_12h": 0.0,
            "sol_change_12h": 0.0,
            "market_regime": "NEUTRAL",
            "overall_trend": "NEUTRAL",
        }


async def _run_mtf_confirmation_with_logging(
    symbol: str,
    direction: str,
    regime_data: Optional[Dict[str, Any]],
) -> Tuple[bool, Optional[str]]:
    """
    Вызывает MTF confirmation (гибридную или стандартную), логирует результат в БД и pipeline.
    """
    # Проверяем доступность гибридной MTF системы
    if HYBRID_MTF_AVAILABLE and HybridMTFConfirmation is not None:
        try:
            from config import HYBRID_MTF_CONFIG

            if HYBRID_MTF_CONFIG.get("enabled", True):
                # Используем гибридную MTF систему
                hybrid_mtf = HybridMTFConfirmation({"HYBRID_MTF_CONFIG": HYBRID_MTF_CONFIG})

                # ⚡ OPTIMIZATION (Алексей): Параллельные запросы данных
                # Получаем данные H4, H1 и рыночный контекст параллельно
                df_h4_task = _get_data_with_fallback(symbol, "4h")
                df_h1_task = _get_data_with_fallback(symbol, "1h")
                market_context_task = _get_market_context_with_sol(regime_data)

                # Выполняем все запросы параллельно
                df_h4, df_h1, market_context = await asyncio.gather(
                    df_h4_task, df_h1_task, market_context_task, return_exceptions=True
                )

                # Обрабатываем исключения
                if isinstance(df_h4, Exception):
                    df_h4 = None
                if isinstance(df_h1, Exception):
                    df_h1 = None
                if isinstance(market_context, Exception):
                    market_context = {}

                if df_h4 is not None:
                    # Проверяем гибридную MTF
                    (
                        confirmed,
                        confidence,
                        mtf_details,
                    ) = await hybrid_mtf.check_hybrid_mtf_confirmation(
                        symbol, direction, df_h4, df_h1, market_context
                    )

                    _log_mtf_event(
                        symbol=symbol,
                        direction=direction,
                        confirmed=confirmed,
                        error_text=None
                        if confirmed
                        else f"Гибридная MTF: confidence={confidence:.2f} < min (details: {mtf_details.get('reason', 'N/A')})",
                        regime_data=regime_data,
                    )

                    if confirmed:
                        logger.debug(
                            "✅ %s: Гибридная MTF подтверждена (confidence=%.2f)",
                            symbol,
                            confidence,
                        )
                        pipeline_monitor.log_stage(
                            "mtf_confirmation", symbol, True, f"Гибридная MTF: {confidence:.2f}"
                        )
                        return True, None
                    else:
                        logger.debug(
                            "🚫 %s: Гибридная MTF не подтверждена (confidence=%.2f)",
                            symbol,
                            confidence,
                        )
                        pipeline_monitor.log_stage(
                            "mtf_confirmation",
                            symbol,
                            False,
                            f"Гибридная MTF: {confidence:.2f} < min",
                        )
                        return False, f"Гибридная MTF: confidence={confidence:.2f}"
                else:
                    logger.warning(
                        "⚠️ %s: Не удалось получить данные H4 для гибридной MTF, используем fallback",
                        symbol,
                    )
        except Exception as e:
            logger.error("❌ Ошибка гибридной MTF для %s: %s, используем fallback", symbol, e)

    # Fallback: стандартная MTF система
    if not (MTF_CONFIRMATION_AVAILABLE and check_mtf_confirmation):
        return True, None

    try:
        mtf_confirmed, mtf_error = await check_mtf_confirmation(
            symbol, direction, "4h", regime_data
        )
        _log_mtf_event(
            symbol=symbol,
            direction=direction,
            confirmed=mtf_confirmed,
            error_text=mtf_error,
            regime_data=regime_data,
        )
        if not mtf_confirmed:
            logger.debug(
                "🚫 %s: MTF Confirmation не пройден для %s: %s", symbol, direction, mtf_error
            )
            pipeline_monitor.log_stage(
                "mtf_confirmation", symbol, False, f"MTF не подтвержден: {mtf_error}"
            )
            return False, mtf_error

        logger.debug("✅ %s: MTF Confirmation пройден (H4)", symbol)
        pipeline_monitor.log_stage("mtf_confirmation", symbol, True, "MTF подтвержден на H4")
        return True, None
    except Exception as exc:
        _log_mtf_event(
            symbol=symbol,
            direction=direction,
            confirmed=None,
            error_text=str(exc),
            regime_data=regime_data,
        )
        logger.debug("Ошибка MTF Confirmation для %s: %s", symbol, exc)
        return False, str(exc)


# Импортируем оптимизатор timing входа
try:
    from src.strategies.entry_timing import get_entry_timing_optimizer

    ENTRY_TIMING_OPTIMIZER_AVAILABLE = True
    entry_timing_optimizer = get_entry_timing_optimizer()
    logger.info("✅ EntryTimingOptimizer доступен")
except ImportError as e:
    ENTRY_TIMING_OPTIMIZER_AVAILABLE = False
    entry_timing_optimizer = None
    logger.warning("⚠️ EntryTimingOptimizer недоступен: %s", e)

# Импортируем менеджер рисков портфеля
try:
    from src.risk.portfolio import get_portfolio_risk_manager

    PORTFOLIO_RISK_MANAGER_AVAILABLE = True
    portfolio_risk_manager = get_portfolio_risk_manager()
    logger.info("✅ PortfolioRiskManager доступен")
except ImportError as e:
    PORTFOLIO_RISK_MANAGER_AVAILABLE = False
    portfolio_risk_manager = None
    logger.warning("⚠️ PortfolioRiskManager недоступен: %s", e)

# Импортируем ИИ-оптимизатор TP
try:
    from src.ai.tp_optimizer import AITakeProfitOptimizer

    AI_TP_OPTIMIZER_AVAILABLE = True
    AI_TP_OPTIMIZER = AITakeProfitOptimizer()
    logger.info("✅ AI TP Optimizer загружен")
except ImportError:
    AI_TP_OPTIMIZER_AVAILABLE = False
    AI_TP_OPTIMIZER = None
    logger.warning("⚠️ AI TP Optimizer недоступен")

# Импортируем ИИ-оптимизатор SL
try:
    from src.ai.sl_optimizer import AIStopLossOptimizer

    AI_SL_OPTIMIZER_AVAILABLE = True
    AI_SL_OPTIMIZER = AIStopLossOptimizer()
    logger.info("✅ AI SL Optimizer загружен")
except ImportError:
    AI_SL_OPTIMIZER_AVAILABLE = False
    AI_SL_OPTIMIZER = None
    logger.warning("⚠️ AI SL Optimizer недоступен")

# Импортируем AI интеграцию
try:
    from src.ai.integration import ai_integration

    AI_INTEGRATION_AVAILABLE = True
    logger.info("✅ AI Integration доступен")
except ImportError as e:
    AI_INTEGRATION_AVAILABLE = False
    ai_integration = None
    logger.warning("⚠️ AI Integration недоступен: %s", e)

# Глобальная переменная для системы принятия сигналов
signal_acceptance_manager = None

# Импортируем систему принятия сигналов
try:
    from src.database.acceptance import AcceptanceDatabase
    from src.execution.position_manager import ImprovedPositionManager
    from src.signals.acceptance_manager import SignalAcceptanceManager
    from src.telegram.message_updater import TelegramMessageUpdater

    SIGNAL_ACCEPTANCE_AVAILABLE = True
    logger.info("✅ Модули системы принятия сигналов успешно импортированы")
except ImportError as e:
    SIGNAL_ACCEPTANCE_AVAILABLE = False
    logger.warning("⚠️ Система принятия сигналов недоступна: %s", e)
except Exception as e:
    SIGNAL_ACCEPTANCE_AVAILABLE = False
    logger.error("❌ Ошибка при импорте системы принятия сигналов: %s", e)


# Заглушки для отсутствующих функций
def build_mtf_accumulation_line(symbol: str, *args, **kwargs) -> str:
    """
    Строит линию накопления MTF (Multi-Timeframe) на основе анализа нескольких таймфреймов
    """
    try:
        # Импортируем MTF сервис
        from src.filters.mtf_service import build_mtf_accumulation_line as _mtf_func

        return _mtf_func(symbol, *args, **kwargs)
    except ImportError:
        logger.warning("⚠️ Функция build_mtf_accumulation_line недоступна для %s", symbol)
        return "📊 MTF: Данные недоступны"
    except Exception as e:
        logger.error("[MTF] Ошибка для %s: %s", symbol, e)
        return "📊 MTF: Ошибка расчета"


def _binance_recent_notional(symbol: str) -> float:
    """
    Получает недавний номинальный объем через SourcesHub с fallback
    """
    try:

        async def _get_notional():
            try:
                # Приоритет 1: Используем SourcesHub
                if SOURCES_HUB_AVAILABLE and sources_hub:
                    try:
                        volume_data = await sources_hub.get_volume_data(symbol)
                        price_data = await sources_hub.get_price_data(symbol)

                        volume = (
                            volume_data.get("volume_24h", 0)
                            if isinstance(volume_data, dict)
                            else volume_data
                        )
                        price = (
                            price_data
                            if isinstance(price_data, (int, float))
                            else (price_data.get("price", 0) if isinstance(price_data, dict) else 0)
                        )

                        if volume > 0 and price > 0:
                            logger.debug(
                                "[Notional][SourcesHub] %s: volume=%.2f, price=%.4f",
                                symbol,
                                volume,
                                price,
                            )
                            return float(volume * price)
                    except Exception as e:
                        logger.debug("[Notional][SourcesHub] Ошибка для %s: %s", symbol, e)

                # Fallback: Прямой запрос к Binance API
                url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={symbol}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            volume = float(data.get("volume", 0))
                            price = float(data.get("lastPrice", 0))
                            notional = volume * price
                            logger.debug("[Notional][Binance Fallback] %s: %.2f", symbol, notional)
                            return notional
                        return 0.0
            except Exception as e:
                logger.debug("[Notional] Ошибка для %s: %s", symbol, e)
                return 0.0

        # Запускаем асинхронную функцию
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _get_notional())
                    return future.result()
            else:
                return loop.run_until_complete(_get_notional())
        except Exception:
            return 0.0

    except Exception as e:
        logger.debug("[Notional] Binance ошибка для %s: %s", symbol, e)
        return 0.0


def _bybit_recent_notional(symbol: str) -> float:
    """
    Получает недавний номинальный объем через SourcesHub с fallback на Bybit
    """
    try:

        async def _get_notional():
            try:
                # Приоритет 1: Используем SourcesHub
                if SOURCES_HUB_AVAILABLE and sources_hub:
                    try:
                        volume_data = await sources_hub.get_volume_data(symbol)
                        price_data = await sources_hub.get_price_data(symbol)

                        volume = (
                            volume_data.get("volume_24h", 0)
                            if isinstance(volume_data, dict)
                            else volume_data
                        )
                        price = (
                            price_data
                            if isinstance(price_data, (int, float))
                            else (price_data.get("price", 0) if isinstance(price_data, dict) else 0)
                        )

                        if volume > 0 and price > 0:
                            logger.debug(
                                "[Notional][SourcesHub] %s: volume=%.2f, price=%.4f",
                                symbol,
                                volume,
                                price,
                            )
                            return float(volume * price)
                    except Exception as e:
                        logger.debug("[Notional][SourcesHub] Ошибка для %s: %s", symbol, e)

                # Fallback: Прямой запрос к Bybit API
                url = f"https://api.bybit.com/v5/market/tickers?category=spot&symbol={symbol}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("result", {}).get("list"):
                                ticker = data["result"]["list"][0]
                                volume = float(ticker.get("volume24h", 0))
                                price = float(ticker.get("lastPrice", 0))
                                notional = volume * price
                                logger.debug(
                                    "[Notional][Bybit Fallback] %s: %.2f", symbol, notional
                                )
                                return notional
                        return 0.0
            except Exception as e:
                logger.debug("[Notional] Ошибка для %s: %s", symbol, e)
                return 0.0

        # Запускаем асинхронную функцию
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _get_notional())
                    return future.result()
            else:
                return loop.run_until_complete(_get_notional())
        except Exception:
            return 0.0

    except Exception as e:
        logger.debug("[Notional] Bybit ошибка для %s: %s", symbol, e)
        return 0.0


def _okx_recent_notional(symbol: str) -> float:
    """
    Получает недавний номинальный объем с OKX
    """
    try:

        async def _get_notional():
            try:
                url = f"https://www.okx.com/api/v5/market/ticker?instId={symbol}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data.get("data"):
                                ticker = data["data"][0]
                                volume = float(ticker.get("vol24h", 0))
                                price = float(ticker.get("last", 0))
                                return volume * price
                        return 0.0
            except Exception:
                return 0.0

        # Запускаем асинхронную функцию
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, _get_notional())
                    return future.result()
            else:
                return loop.run_until_complete(_get_notional())
        except Exception:
            return 0.0

    except Exception as e:
        logger.debug("[Notional] OKX ошибка для %s: %s", symbol, e)
        return 0.0


def _kucoin_recent_notional(symbol: str) -> float:
    """
    Заглушка для Kucoin - возвращает 0 (функция не реализована)
    """
    return 0.0


async def calculate_anomaly_circles_with_fallback(symbol: str, signal_type: str) -> tuple:
    """
    Рассчитывает количество кружков аномалий на основе данных объема и капитализации
    """
    try:
        # Получаем данные аномалий
        data = await get_anomaly_data_with_fallback(symbol)

        if not data.get("available"):
            # Не логируем как warning, так как это нормальная ситуация для некоторых монет
            logger.debug(
                "⚠️ Функция calculate_anomaly_circles_with_fallback недоступна для %s (источник: %s)",
                symbol,
                data.get("source", "unknown"),
            )
            return None, "Нет данных аномалий (fallback)", "", False

        volume_24h = data.get("volume_24h", 0)
        market_cap = data.get("market_cap", 0)

        if volume_24h <= 0 or market_cap <= 0:
            return None, "Нет данных аномалий (fallback)", "", False

        # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: Блокировка "стоячих" монет по объему
        # Монета с низким абсолютным объемом (< $1M) = низкая ликвидность
        min_volume_threshold = 1_000_000  # $1M (снижено с $5M для большей гибкости)
        if volume_24h < min_volume_threshold:
            logger.warning(
                "[Anomaly] %s: низкий объем торгов $%.0f < $1M — монета 'стоит'", symbol, volume_24h
            )
            return 0, f"НИЗКАЯ ЛИКВИДНОСТЬ (vol: ${volume_24h:,.0f})", "○○○○○", True

        # Рассчитываем соотношение объема к капитализации
        volume_to_cap_ratio = volume_24h / market_cap

        # Определяем количество кружков на основе РЕАЛЬНЫХ ДАННЫХ
        # Анализ 20 монет показал: средний ratio = 0.88%, диапазон 0.18% - 1.78%
        #
        # Статистика:
        # - BTC: 0.18%, ETH: 0.78%, BNB: 0.46% (топ-3)
        # - SOL: 0.99%, XRP: 0.37%, ADA: 0.56%, DOGE: 1.37% (топ-10)
        # - APT: 1.00%, LINK: 0.99%, AVAX: 0.99%, NEAR: 1.78%, ATOM: 1.39% (топ-50)
        # - Медиана: 1.0%, 80-й перцентиль: 1.0%
        #
        if volume_to_cap_ratio >= 0.15:
            # >= 15% — Явная манипуляция (pump&dump)
            circles_count = 5
            activity_description = "МАНИПУЛЯЦИЯ (pump&dump)"
        elif volume_to_cap_ratio >= 0.08:
            # 8-15% — Критическая активность (возможен pump)
            circles_count = 4
            activity_description = "КРИТИЧЕСКАЯ АКТИВНОСТЬ (pump?)"
        elif volume_to_cap_ratio >= 0.03:
            # 3-8% — Аномально высокая активность (новости, хайп)
            circles_count = 3
            activity_description = "ВЫСОКАЯ АКТИВНОСТЬ (хайп)"
        elif volume_to_cap_ratio >= 0.01:
            # 1-3% — Высокая активность (популярные монеты: SOL, APT, NEAR)
            circles_count = 2
            activity_description = "ХОРОШАЯ АКТИВНОСТЬ"
        elif volume_to_cap_ratio >= 0.001:
            # 0.1-1% — Нормальная активность (90% всех монет, включая BTC/ETH)
            circles_count = 1
            activity_description = "НОРМАЛЬНАЯ АКТИВНОСТЬ"
        else:
            # < 0.1% — Критически низкая ликвидность (мертвые монеты)
            circles_count = 0
            activity_description = "НИЗКАЯ ЛИКВИДНОСТЬ"

        # Создаем визуальное представление кружков
        circles_text = "●" * circles_count + "○" * (5 - circles_count)

        logger.info(
            "[Anomaly] %s: %s кружков, %s, ratio=%.4f",
            symbol,
            circles_count,
            activity_description,
            volume_to_cap_ratio,
        )

        return circles_count, activity_description, circles_text, True

    except Exception as e:
        logger.error("[Anomaly] Ошибка расчета аномалий для %s: %s", symbol, e)
        return None, "Нет данных аномалий (fallback)", "", False


def get_anomaly_emoji(ratio: float) -> str:
    """Заглушка для get_anomaly_emoji"""
    return "⚪"


async def get_anomaly_data_with_fallback(symbol: str, ttl_seconds: int = 900) -> dict:
    """
    Получение данных аномалий через SourcesHub с ПАРАЛЛЕЛЬНЫМ fallback
    Запрашивает все источники одновременно и возвращает первый успешный
    """
    try:
        # Санитайз символа от дублей USDT (например, CAKEUSDTUSDT)
        try:
            if symbol.endswith("USDTUSDT") or symbol.count("USDT") > 1:
                base = symbol.split("USDT")[0]
                symbol = f"{base}USDT"
        except Exception:
            pass

        # Приоритет 1: Пробуем SourcesHub
        if SOURCES_HUB_AVAILABLE and sources_hub:
            try:
                market_cap_data = await sources_hub.get_market_cap_data(symbol)
                volume_data = await sources_hub.get_volume_data(symbol)

                if market_cap_data and volume_data:
                    market_cap = market_cap_data.get("market_cap", 0)
                    volume_24h = (
                        volume_data.get("volume_24h", 0)
                        if isinstance(volume_data, dict)
                        else volume_data
                    )

                    if volume_24h > 0 and market_cap > 0:
                        logger.debug(
                            "[Anomaly] SourcesHub: %s - volume=%.2f, mcap=%.2f",
                            symbol,
                            volume_24h,
                            market_cap,
                        )
                        return {
                            "available": True,
                            "source": "sources_hub",
                            "volume_24h": volume_24h,
                            "market_cap": market_cap,
                        }
            except Exception as e:
                logger.debug("[Anomaly] SourcesHub ошибка для %s: %s", symbol, e)

        # Fallback: ПАРАЛЛЕЛЬНЫЕ запросы ко всем источникам одновременно
        logger.debug("[Anomaly] Параллельный fallback для %s", symbol)

        # Извлекаем базовый символ (убираем только торговые пары, не сами монеты!)
        # Правильный порядок: сначала убираем торговые пары, чтобы не затронуть сами монеты
        if symbol.endswith("USDT"):
            base = symbol.replace("USDT", "")
        elif symbol.endswith("BUSD"):
            base = symbol.replace("BUSD", "")
        elif symbol.endswith("BTC"):
            base = symbol.replace("BTC", "")
        elif symbol.endswith("ETH"):
            base = symbol.replace("ETH", "")
        else:
            base = symbol

        # Создаём задачи для ПАРАЛЛЕЛЬНЫХ запросов
        async def _try_coingecko():
            try:
                url = f"https://api.coingecko.com/api/v3/coins/{base.lower()}"
                async with aiohttp.ClientSession() as session:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=4)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            volume_24h = (
                                data.get("market_data", {}).get("total_volume", {}).get("usd", 0)
                            )
                            market_cap = (
                                data.get("market_data", {}).get("market_cap", {}).get("usd", 0)
                            )
                            if volume_24h > 0 and market_cap > 0:
                                return ("coingecko", volume_24h, market_cap)
            except Exception:
                pass
            return None

        async def _try_binance():
            try:
                # Binance не предоставляет market_cap напрямую
                # Используем только для получения volume, если CoinGecko недоступен
                # Но без market_cap мы не можем рассчитать ratio, поэтому пропускаем
                pass
            except Exception:
                pass
            return None

        # Запускаем ВСЕ источники параллельно
        results = await asyncio.gather(_try_coingecko(), _try_binance(), return_exceptions=True)

        # Берём первый успешный результат
        for result in results:
            if result and isinstance(result, tuple) and len(result) == 3:
                source, volume_24h, market_cap = result
                logger.debug(
                    "[Anomaly] %s: %s - volume=%.2f, mcap=%.2f",
                    source,
                    symbol,
                    volume_24h,
                    market_cap,
                )
                return {
                    "available": True,
                    "source": f"{source}_parallel",
                    "volume_24h": volume_24h,
                    "market_cap": market_cap,
                }

        # Если все источники недоступны
        return {"available": False, "source": "fallback"}

    except Exception as e:
        logger.error("[Anomaly] Критическая ошибка для %s: %s", symbol, e)
        return {"available": False, "source": "error"}


# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(filename)s | %(funcName)s:%(lineno)d | %(message)s",
    handlers=[logging.StreamHandler()],
    force=True,  # 🔧 ИСПРАВЛЕНО: Принудительно применяем настройки
)
logger = logging.getLogger(__name__)
# 🔧 ИСПРАВЛЕНО: Устанавливаем уровень для root logger
logging.getLogger().setLevel(logging.INFO)

# Система контроля качества сигналов
# Импортируем классы фильтров из отдельного модуля (Игорь + Павел - To 10/10)
try:
    from src.signals.filters_internal import (
        DynamicSymbolBlocker,
        PatternConfidenceScorer,
        PipelineMonitor,
        SignalQualityValidator,
        SmartRSIFilter,
    )
except ImportError:
    logger.warning("⚠️ src.signals.filters_internal недоступен, используем fallback")

    class SignalQualityValidator:
        """Заглушка для валидатора качества сигнала."""

        def __init__(self, *args, **kwargs):
            pass

        def validate(self, *args, **kwargs):
            """Заглушка для метода валидации."""
            return True, {}

    class PatternConfidenceScorer:
        """Заглушка для оценки уверенности в паттерне."""

        def __init__(self, *args, **kwargs):
            pass

        def score(self, *args, **kwargs):
            """Заглушка для метода оценки."""
            return 0.5

    class DynamicSymbolBlocker:
        """Заглушка для динамической блокировки символов."""

        def __init__(self, *args, **kwargs):
            pass

        def is_blocked(self, *args, **kwargs):
            """Заглушка для проверки блокировки."""
            return False

    class PipelineMonitor:
        """Заглушка для мониторинга пайплайна."""

        def __init__(self, *args, **kwargs):
            pass

        def log_stage(self, *args, **kwargs):
            """Заглушка для логирования этапа."""

    class SmartRSIFilter:
        """Заглушка для умного RSI фильтра."""

        def __init__(self, *args, **kwargs):
            pass

        def evaluate(self, *args, **kwargs):
            """Заглушка для оценки по RSI."""
            return {"decision": "pass", "reason": "fallback"}


FILTERS_IMPORTED = True

# Fallback классы удалены - используем только импорт из filters_internal.py

# Инициализация защитных механизмов (используем импортированные классы)
quality_validator = SignalQualityValidator()
pattern_scorer = PatternConfidenceScorer()
symbol_blocker = DynamicSymbolBlocker()
pipeline_monitor = PipelineMonitor()

# Инициализация AI-регулятора
try:
    from src.adapters.parameters import get_ai_regulator

    ai_regulator = get_ai_regulator(enable_optimization=False)
    AI_REGULATOR_AVAILABLE = True
    logger.info("🧠 AI-регулятор параметров доступен")
except ImportError as e:
    ai_regulator = None
    AI_REGULATOR_AVAILABLE = False
    logger.warning("⚠️ AI-регулятор недоступен: %s", e)

# Инициализация расширенных защитных механизмов
try:
    from scripts.recovery.emergency_response import EmergencyResponseSystem
    from src.filters.multi_timeframe import MultiTimeframeConfirmer
    from src.filters.volume_spike import VolumeSpikeDetector

    mtf_confirmer = MultiTimeframeConfirmer()
    volume_detector = VolumeSpikeDetector()
    emergency_system = EmergencyResponseSystem()

    DEFENSE_SYSTEMS_AVAILABLE = True
    logger.info("🛡️ Расширенные защитные системы доступны")
except ImportError as e:
    mtf_confirmer = None
    volume_detector = None
    emergency_system = None
    DEFENSE_SYSTEMS_AVAILABLE = False
    logger.warning("⚠️ Расширенные защитные системы недоступны: %s", e)

# Импортируем LightGBM предсказатель для ML фильтрации
try:
    # pylint: disable=ungrouped-imports
    from src.ai.lightgbm_predictor import get_lightgbm_predictor

    lightgbm_predictor = get_lightgbm_predictor()
    # Пытаемся загрузить обученные модели
    if lightgbm_predictor.load_models():
        LIGHTGBM_AVAILABLE = True
        logger.info("✅ LightGBM предсказатель доступен и модели загружены")
    else:
        LIGHTGBM_AVAILABLE = False
        logger.warning(
            "⚠️ LightGBM предсказатель доступен, но модели не обучены (используйте train_lightgbm_models.py)"
        )
except ImportError as e:
    lightgbm_predictor = None
    LIGHTGBM_AVAILABLE = False
    logger.warning("⚠️ LightGBM предсказатель недоступен: %s", e)


# Очередь сообщений с TTL и приоритетами
class SignalQueue:
    """Очередь сигналов с TTL и приоритетами для управления торговыми сигналами."""

    def __init__(self):
        self.queue = []
        self.ttl = 3600  # 1 час TTL
        self.max_size = 1000

    async def add_signal(self, signal_data: Dict[str, Any], priority: int = 1):
        """Добавляет сигнал в очередь с приоритетом"""
        signal_data["priority"] = priority
        signal_data["queue_time"] = time.time()
        self.queue.append(signal_data)

        # Ограничиваем размер очереди
        if len(self.queue) > self.max_size:
            self.queue = self.queue[-self.max_size :]

    async def get_next_signal(self) -> Optional[Dict[str, Any]]:
        """Получает следующий сигнал из очереди"""
        if not self.queue:
            return None

        # Сортируем по приоритету (высший приоритет = меньше число)
        self.queue.sort(key=lambda x: x.get("priority", 1))

        # Удаляем просроченные сигналы
        current_time = time.time()
        self.queue = [s for s in self.queue if current_time - s.get("queue_time", 0) < self.ttl]

        if self.queue:
            return self.queue.pop(0)
        return None

    def get_queue_stats(self) -> Dict[str, Any]:
        """Возвращает статистику очереди"""
        return {"queue_size": len(self.queue), "max_size": self.max_size, "ttl": self.ttl}


# Глобальная очередь сигналов
signal_queue = SignalQueue()


# Rate Limiting для Telegram API
class TelegramRateLimiter:
    """Ограничитель скорости для Telegram API с поддержкой пользовательских и групповых лимитов."""

    def __init__(self):
        self.user_limits = {}  # user_id -> last_send_time
        self.bot_limits = {"last_send": 0, "count": 0}  # Общие лимиты бота
        self.user_rate = 1.0  # 1 сообщение в секунду на пользователя
        self.bot_rate = 30.0  # 30 сообщений в секунду на бота
        self.group_rate = 20.0  # 20 сообщений в минуту на группу

    async def can_send_to_user(self, user_id: str) -> bool:
        """Проверяет, можно ли отправить сообщение пользователю"""
        current_time = time.time()

        if user_id not in self.user_limits:
            self.user_limits[user_id] = current_time
            return True

        time_since_last = current_time - self.user_limits[user_id]
        if time_since_last >= self.user_rate:
            self.user_limits[user_id] = current_time
            return True

        return False

    async def can_send_bot_message(self) -> bool:
        """Проверяет, можно ли отправить сообщение от бота"""
        current_time = time.time()

        # Сбрасываем счетчик каждую секунду
        if current_time - self.bot_limits["last_send"] >= 1.0:
            self.bot_limits["count"] = 0
            self.bot_limits["last_send"] = current_time

        if self.bot_limits["count"] < self.bot_rate:
            self.bot_limits["count"] += 1
            return True

        return False

    async def wait_if_needed(self, user_id: str):
        """Ждет, если необходимо соблюсти rate limiting"""
        while not await self.can_send_to_user(user_id) or not await self.can_send_bot_message():
            await asyncio.sleep(0.1)


# Глобальный rate limiter
rate_limiter = TelegramRateLimiter()

# Попытка импорта гибридного менеджера данных
try:
    from src.data.hybrid_manager import HybridDataManager

    HYBRID_DATA_MANAGER = HybridDataManager()
    HYBRID_DATA_MANAGER_AVAILABLE = True
    logger.info("✅ Гибридный менеджер данных доступен")
except ImportError:
    HYBRID_DATA_MANAGER = None
    HYBRID_DATA_MANAGER_AVAILABLE = False
    logger.warning(
        "⚠️ Гибридный менеджер данных недоступен. Будет использоваться прямой доступ к API."
    )

# Импорты для exchange API (критично для работы системы)
try:
    from src.execution.exchange_api import get_symbol_info
except ImportError:
    get_symbol_info = None

try:
    from src.execution.exchange_base import get_ohlc_with_fallback
except ImportError:
    try:
        from src.execution.exchange_api import get_ohlc_with_fallback
    except ImportError:
        try:
            from src.data.providers import get_ohlc_data as get_ohlc_with_fallback
        except ImportError:
            get_ohlc_with_fallback = None

# Импорты для реальной отправки в Telegram
try:
    from src.telegram.handlers import notify_user
    from src.telegram.messaging import build_new_signal_message
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup

    TELEGRAM_INTEGRATION_AVAILABLE = True
    logger.info("✅ Интеграция с Telegram доступна")
except ImportError as e:
    TELEGRAM_INTEGRATION_AVAILABLE = False
    logger.error(
        "❌ Ошибка импорта Telegram-интеграции: %s. Отправка в Telegram будет отключена.", e
    )

# Импорт улучшенной системы доставки
try:
    # pylint: disable=ungrouped-imports
    from src.telegram.enhanced_delivery import notify_user_enhanced, print_telegram_delivery_stats

    ENHANCED_DELIVERY_AVAILABLE = True
    logger.info("✅ Улучшенная система доставки Telegram доступна")
except ImportError as e:
    ENHANCED_DELIVERY_AVAILABLE = False
    logger.warning("⚠️ Улучшенная система доставки недоступна: %s", e)

# Глобальная переменная для хранения истории сигналов
signal_history_global: List[Dict[str, Any]] = []

# --- AI-оптимизированные параметры ---
AI_OPTIMIZED_PARAMETERS_FILE = "ai_learning_data/filter_parameters.json"


def load_ai_optimized_parameters() -> Dict[str, Any]:
    """Загружает ИИ-оптимизированные параметры из файла."""
    try:
        with open(AI_OPTIMIZED_PARAMETERS_FILE, encoding="utf-8") as f:
            data = json.load(f)
            metrics = data.get("metrics", {})
            logger.info("🤖 Загружены ИИ-оптимизированные параметры:")
            logger.info("  • Win Rate: %.1f%%", metrics.get("win_rate", 0.0) * 100)
            logger.info("  • Profit Factor: %.2f", metrics.get("profit_factor", 0.0))
            logger.info("  • Сделок: %d", metrics.get("trades_count", 0))
            return data
    except FileNotFoundError:
        logger.warning(
            "Файл ИИ-оптимизированных параметров не найден. Используем параметры по умолчанию."
        )
        return {
            "parameters": {
                "soft_score_threshold": 15.0,  # Снижено с 25.0 (-40%)
                "strict_score_threshold": 25.0,  # Снижено с 35.0 (-29%)
                "min_volume_usd": 10,  # Минимальный порог для тестирования
                "min_volatility_pct": 0.005,  # 0.5% (как было ранее)
                "max_volatility_pct": 0.15,  # 15% (как было ранее)
                "min_rsi": 30,
                "max_rsi": 70,
                "min_adx": 20,
                "max_adx": 50,
                "ema_fast_period": 20,
                "ema_slow_period": 50,
                "bb_window": 20,
                "bb_std_dev": 2,
                "ai_confidence_threshold": 0.7,
                "risk_per_trade_pct": 0.5,
                "max_leverage": 5,
                "take_profit_multiplier": 1.5,
                "stop_loss_multiplier": 0.75,
            },
            "metrics": {"win_rate": 0.0, "profit_factor": 0.0, "trades_count": 0},
        }
    except Exception as e:
        logger.error("Ошибка загрузки ИИ-оптимизированных параметров: %s", e)
        return {}


# Загружаем параметры при старте
ai_optimized_params_global = load_ai_optimized_parameters()


def _get_recent_signals_count(hours: int = 1) -> int:
    """
    Подсчет сигналов за последние N часов для адаптивной регуляции порогов

    Args:
        hours: Количество часов для подсчета (по умолчанию 1)

    Returns:
        int: Количество сигналов за указанный период
    """
    try:
        from datetime import timedelta

        from src.database.db import Database  # type: ignore

        db = Database()
        if not db:
            return 0

        # Вычисляем время начала периода
        time_threshold = get_utc_now() - timedelta(hours=hours)

        # Подсчитываем сигналы за период
        query = """
            SELECT COUNT(*)
            FROM signals_log
            WHERE created_at >= ?
        """

        with db.get_lock():
            cursor = db.conn.execute(query, (time_threshold.isoformat(),))
            count = cursor.fetchone()[0]

        return count if count else 0

    except Exception as e:
        logger.debug("⚠️ Ошибка подсчета сигналов за последние %d часов: %s", hours, e)
        # Возвращаем 0 для активации дополнительного снижения порогов
        return 0


def get_ai_optimized_parameters(symbol: Optional[str] = None) -> Dict[str, Any]:
    """
    Динамически загружает ИИ-оптимизированные параметры.
    Если указан символ, пытается загрузить специфичные для символа параметры.
    """
    ai_params = load_ai_optimized_parameters()

    if symbol:
        try:
            # Попытка загрузить параметры, специфичные для символа
            symbol_specific_file = f"ai_learning_data/symbol_params/{symbol}.json"
            if os.path.exists(symbol_specific_file):
                with open(symbol_specific_file, encoding="utf-8") as f:
                    data = json.load(f)
                symbol_params = data.get("parameters", ai_params.get("parameters", {}))
                logger.debug("✅ Загружены индивидуальные параметры для %s из файла", symbol)
                return {"parameters": symbol_params, "metrics": ai_params.get("metrics", {})}
            else:
                logger.debug(
                    "ℹ️ Индивидуальные параметры для %s не найдены, используем общие.", symbol
                )
        except Exception as e:
            logger.warning(
                "Ошибка загрузки индивидуальных параметров для %s: %s. Используем общие.", symbol, e
            )
    return ai_params


async def calculate_ai_signal_score(
    df: pd.DataFrame,
    ai_params: Dict[str, Any],
    symbol: Optional[str] = None,
    news_analysis: Optional[Dict[str, Any]] = None,
) -> float:
    """
    Рассчитывает ИИ-скор сигнала на основе технических индикаторов, ИИ-оптимизированных параметров и новостей.
    """
    if (
        df.empty
        or len(df) < max(ai_params.get("ema_slow_period", 50), ai_params.get("bb_window", 20)) + 1
    ):
        logger.debug("Недостаточно данных для расчета скора для %s", symbol)
        return 0.0

    # ДИАГНОСТИКА: Логируем колонки DataFrame
    logger.debug("🔍 DataFrame для %s содержит колонки: %s", symbol, list(df.columns))

    # Получаем индивидуальные параметры для символа
    current_ai_params = get_ai_optimized_parameters(symbol).get("parameters", {})

    # 🆕 ИСПОЛЬЗУЕМ АДАПТИВНУЮ РЕГУЛЯЦИЮ ДЛЯ SCORE
    adaptive_rsi_long = 70.0
    adaptive_volume_ratio = 1.2

    if ADAPTIVE_REGULATOR_AVAILABLE and get_adaptive_regulator:
        try:
            regulator = get_adaptive_regulator()
            thresholds = await regulator.get_all_adaptive_thresholds(
                df=df,
                market_volatility=float(df["volatility"].iloc[-1])
                if "volatility" in df.columns
                else None,
                volume_ratio=float(df["volume_ratio"].iloc[-1])
                if "volume_ratio" in df.columns
                else None,
            )
            adaptive_rsi_long = thresholds.get("rsi_long", 70.0)
            adaptive_volume_ratio = thresholds.get("volume_ratio", 1.2)
        except Exception:
            pass

    score = 0
    bonus = 0

    # 1. RSI (с учетом адаптивного порога)
    rsi_val = df["rsi"].iloc[-1] if "rsi" in df.columns else 50
    min_rsi_threshold = current_ai_params.get("min_rsi", 30)

    if "rsi" in df.columns and rsi_val > min_rsi_threshold:
        score += 15
        # Бонус за нахождение в оптимальной зоне (между min и адаптивным максимумом)
        if rsi_val < adaptive_rsi_long:
            bonus += 5
        if rsi_val < 50:
            bonus += 5

    # 2. Volume Ratio (с учетом адаптивного порога)
    vol_ratio_val = df["volume_ratio"].iloc[-1] if "volume_ratio" in df.columns else 1.0
    if "volume_ratio" in df.columns and vol_ratio_val > adaptive_volume_ratio:
        score += 10
        bonus += 5  # Увеличенный бонус за хороший объем
    elif "volume_ratio" in df.columns and vol_ratio_val > current_ai_params.get(
        "soft_volume_ratio", 1.2
    ):
        score += 5

    # 3. Volatility (ATR%)
    if "volatility" in df.columns and current_ai_params.get("min_volatility_pct", 0.01) < df[
        "volatility"
    ].iloc[-1] < current_ai_params.get("max_volatility_pct", 0.10):
        score += 20
        bonus += 7

    # 4. Trend Strength (ADX)
    if "trend_strength" in df.columns and df["trend_strength"].iloc[-1] > current_ai_params.get(
        "min_adx", 20
    ):
        score += 15
        bonus += 5

    # 5. Bollinger Bands (пример: цена у нижней границы для лонга)
    if "bb_lower" in df.columns and df["close"].iloc[-1] < df["bb_lower"].iloc[-1]:
        score += 10
        bonus += 4

    # 6. EMA Crossover (пример: бычий кроссовер)
    if (
        "ema_fast" in df.columns
        and "ema_slow" in df.columns
        and df["ema_fast"].iloc[-1] > df["ema_slow"].iloc[-1]
    ):
        score += 10
        bonus += 3

    # 🆕 7. НОВОСТНОЙ СЕНТИМЕНТ (SENTIMENT BONUS)
    if news_analysis:
        sentiment = news_analysis.get("sentiment", "neutral")
        news_score = news_analysis.get("score", 0)

        if sentiment == "bullish":
            score += 15  # Существенный бонус за позитивные новости
            bonus += 5
            logger.debug("🚀 [%s] Сентимент-бонус: +20 к скору", symbol)
        elif sentiment == "bearish":
            score -= 20  # Штраф за негативные новости
            logger.debug("⚠️ [%s] Сентимент-штраф: -20 к скору", symbol)

        # Дополнительная корректировка по числовому скору новостей
        if abs(news_score) > 2:
            score += np.sign(news_score) * 5

    # Применяем бонус
    score += bonus

    # ДИАГНОСТИКА: Логируем итоговый score
    logger.debug("📊 Score для %s: %.1f (бонус: %d)", symbol, score, bonus)

    return min(max(score, 0.0), 100.0)  # В диапазоне [0, 100]


SMART_RSI_LOG_FIELDS = [
    "timestamp",
    "group",
    "symbol",
    "direction",
    "rsi",
    "decision",
    "reason",
    "trend_strength",
    "volume_ratio",
    "ai_confidence",
    "btc_alignment",
    "adjustments",
]

SMART_RSI_LOG_PATH = Path(__file__).resolve().parent / "logs" / "smart_rsi_log.csv"


def _deterministic_hash(value: str) -> int:
    """Детерминированный хэш для A/B распределения."""
    return int(hashlib.sha256(value.encode("utf-8")).hexdigest(), 16)


def get_rsi_experiment_group(symbol: str, timestamp: Optional[datetime]) -> str:
    """
    Определяет группу A/B теста для RSI фильтра.
    🔧 ИСПРАВЛЕНО: Все символы используют группу A (Smart RSI с AI) для лучшей адаптации к рынку.
    """
    # Все символы используют Smart RSI Filter (группа A)
    return "A"  # 🤖 AI регулировка для всех символов


def _log_smart_rsi(entry: Dict[str, Any]) -> None:
    """Логирование решений умного RSI фильтра в CSV."""
    try:
        logs_dir = SMART_RSI_LOG_PATH.parent
        os.makedirs(logs_dir, exist_ok=True)
        file_exists = SMART_RSI_LOG_PATH.exists()
        with open(SMART_RSI_LOG_PATH, "a", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=SMART_RSI_LOG_FIELDS)
            if not file_exists:
                writer.writeheader()
            writer.writerow(entry)
    except Exception as exc:
        logger.debug("⚠️ Не удалось записать лог Smart RSI: %s", exc)


def set_smart_rsi_btc_alignment(df: pd.DataFrame, value: bool = True) -> None:
    """
    Устанавливает BTC alignment в smart_rsi context.
    🔧 ИСПРАВЛЕНО: Убрано дублирование кода (Игорь - после аудита)

    Args:
        df: DataFrame с атрибутами
        value: Значение для btc_alignment (по умолчанию True)
    """
    smart_ctx = df.attrs.get("smart_rsi")
    if isinstance(smart_ctx, dict):
        smart_ctx["btc_alignment"] = value


def calculate_tp_prices_for_ml(
    signal_price: float, df: pd.DataFrame, signal_type: str, trade_mode: str = "spot"
) -> Tuple[float, float]:
    """
    Рассчитывает TP1 и TP2 цены для ML фильтра.
    🔧 ИСПРАВЛЕНО: Рассчитываем TP перед ML для более точных предсказаний (Дмитрий - после аудита)

    Args:
        signal_price: Цена входа
        df: DataFrame с данными
        signal_type: Тип сигнала (BUY/SELL/LONG/SHORT)
        trade_mode: Режим торговли (spot/futures)

    Returns:
        Tuple[float, float]: (tp1_price, tp2_price)
    """
    try:
        last_idx = len(df) - 1
        side = "long" if signal_type in ("BUY", "LONG") else "short"
        tp1_pct, tp2_pct = get_dynamic_tp_levels(
            df, last_idx, side=side, trade_mode=trade_mode, adjust_for_fees=True
        )

        if side == "long":
            tp1_price = signal_price * (1 + tp1_pct / 100.0)
            tp2_price = signal_price * (1 + tp2_pct / 100.0)
        else:  # short
            tp1_price = signal_price * (1 - tp1_pct / 100.0)
            tp2_price = signal_price * (1 - tp2_pct / 100.0)

        return tp1_price, tp2_price
    except Exception as e:
        logger.debug("⚠️ [TP CALC] Ошибка расчёта TP, используем дефолты: %s", e)
        # Дефолтные значения
        if signal_type in ("BUY", "LONG"):
            return signal_price * 1.02, signal_price * 1.04
        else:
            return signal_price * 0.98, signal_price * 0.96


# SmartRSIFilter импортирован из src.signals.filters_internal (строка 1132)
# Локальное определение удалено для избежания дублирования
SMART_RSI_FILTER = SmartRSIFilter()


try:
    from src.signals.indicators import add_technical_indicators
except ImportError:
    # Fallback если модуль недоступен (не должно случаться в продакшне)
    def add_technical_indicators(df: pd.DataFrame) -> pd.DataFrame:
        logger.warning("⚠️ Используется встроенный fallback для индикаторов")
        return df


async def get_symbol_data(symbol: str, force_fresh: bool = False) -> Optional[Any]:
    """Получение данных символа с использованием кеша"""
    try:
        # Пробуем получить данные через гибридный менеджер (с кешированием)
        if HYBRID_DATA_MANAGER_AVAILABLE and HYBRID_DATA_MANAGER:
            df = await HYBRID_DATA_MANAGER.get_smart_data(symbol, "ohlc", force_fresh=force_fresh)
        else:
            # Fallback: прямой доступ к API (без кеша, но с rate limiting)
            if get_ohlc_with_fallback is None:
                logger.error("❌ get_ohlc_with_fallback недоступен для %s", symbol)
                return None
            df = await get_ohlc_with_fallback(symbol, interval="1h", limit=300)
        # Проверяем, что данные получены и не пустые
        if df is None or (hasattr(df, "__len__") and len(df) == 0):
            logger.debug("Нет данных для %s", symbol)
            return None

        if not isinstance(df, pd.DataFrame):
            try:
                # Проверяем, что df не пустой и содержит данные
                if df is not None and len(df) > 0:
                    df = pd.DataFrame(df)
                    logger.debug("Конвертировали список в DataFrame для %s", symbol)
                else:
                    logger.debug("Пустые данные для %s", symbol)
                    return None
            except Exception as e:
                logger.error("Ошибка конвертации данных для %s: %s", symbol, e)
                return None

        if df is not None and len(df) > 0:
            df = add_technical_indicators(df)
            logger.debug("✅ Добавлены технические индикаторы для %s", symbol)

        return df

    except Exception as e:
        logger.error("Ошибка получения данных для %s: %s", symbol, e)
        return None


async def load_user_data() -> Dict[str, Any]:
    """Загрузка данных пользователей из базы данных"""
    try:
        # load_user_data_for_signals() не асинхронная функция
        user_data_dict = load_user_data_for_signals()
        logger.info("✅ Загружено %d пользователей из базы данных", len(user_data_dict))
        return user_data_dict
    except Exception as e:
        logger.error("Ошибка загрузки пользователей: %s", e)
        return {}


async def get_cached_api_coins() -> List[str]:
    """Получает монеты из API с кэшированием на 24 часа"""
    global _api_coins_cache, _api_coins_cache_timestamp

    current_time = time.time()

    # Проверяем кэш
    if (
        _api_coins_cache is not None
        and _api_coins_cache_timestamp is not None
        and current_time - _api_coins_cache_timestamp < API_COINS_CACHE_TTL
    ):
        logger.info(
            "✅ Используем кэшированный список монет из API (%d монет)", len(_api_coins_cache)
        )
        return _api_coins_cache

    # Обновляем кэш
    logger.info("🔄 Обновление списка монет из API...")
    try:
        symbols = await get_filtered_top_usdt_pairs_fast(top_n=500, final_limit=200)

        if symbols:
            _api_coins_cache = symbols
            _api_coins_cache_timestamp = current_time
            logger.info("✅ Список монет из API обновлен и закэширован (%d монет)", len(symbols))
            return symbols
    except Exception as e:
        logger.error("❌ Ошибка получения монет из API: %s", e)
        # Используем старый кэш, если есть
        if _api_coins_cache:
            logger.warning("⚠️ Используем устаревший кэш")
            return _api_coins_cache

    return []


def force_refresh_api_coins_cache():
    """Принудительно обновляет кэш монет из API"""
    global _api_coins_cache, _api_coins_cache_timestamp
    _api_coins_cache = None
    _api_coins_cache_timestamp = None
    logger.info("🔄 Кэш монет из API сброшен, будет обновлен при следующем вызове get_symbols()")


async def get_symbols() -> List[str]:
    """Получение символов для анализа (async версия)"""
    try:
        from config import AUTO_FETCH_COINS, COINS
        from src.ai.intelligent_filter_system import get_all_optimized_symbols

        # Используем глобальную STABLECOIN_SYMBOLS (определена в начале файла)
        from src.ai.symbol_params_manager import get_symbol_params_manager

        # ПРИОРИТЕТ 0: Авто-подбор из API (с кэшированием на 24 часа)
        try:
            api_coins = await get_cached_api_coins()
            if api_coins and len(api_coins) > 0:
                logger.info(
                    "✅ Получено %d монет из API (кэш обновляется раз в сутки)", len(api_coins)
                )

                # Фильтрация стейблкоинов и дублей
                filtered_symbols = [
                    s
                    for s in api_coins
                    if s not in STABLECOIN_SYMBOLS
                    and s.endswith("USDT")
                    and not s.endswith("USDTUSDT")
                    and s.count("USDT") == 1
                ]

                if filtered_symbols:
                    # 🔧 ДОБАВЛЕНО: Фильтрация по листингу Bitget Futures
                    bitget_symbols = await get_bitget_futures_symbols()
                    if bitget_symbols:
                        bitget_set = set(bitget_symbols)
                        original_count = len(filtered_symbols)
                        filtered_symbols = [s for s in filtered_symbols if s in bitget_set]
                        if len(filtered_symbols) < original_count:
                            logger.info(
                                "📉 [LISTING] Исключено %d монет, не торгуемых на Bitget Futures",
                                original_count - len(filtered_symbols),
                            )

                    # Получаем список оптимизированных монет из intelligent_filter_system
                    optimized_symbols = set(get_all_optimized_symbols())

                    params_manager = get_symbol_params_manager()
                    ready_symbols = []
                    pending_symbols = []

                    for symbol in filtered_symbols:
                        # Проверяем наличие в intelligent_filter_system
                        if symbol in optimized_symbols:
                            # Монета уже оптимизирована - используем параметры
                            _, is_ready = await params_manager.ensure_symbol_optimized(symbol)
                            if is_ready:
                                ready_symbols.append(symbol)
                                logger.debug(
                                    "✅ [%s] Используем оптимизированные параметры из intelligent_filter_system",
                                    symbol,
                                )
                            else:
                                # Параметры есть, но оптимизация не завершена
                                pending_symbols.append(symbol)
                                logger.info(
                                    "⏳ [%s] Оптимизация в процессе, монета временно заблокирована",
                                    symbol,
                                )
                        else:
                            # Монеты нет в intelligent_filter_system - добавляем и оптимизируем
                            logger.info(
                                "🆕 [%s] Новая монета, добавляем с базовыми параметрами и запускаем оптимизацию",
                                symbol,
                            )
                            _, is_ready = await params_manager.ensure_symbol_optimized(symbol)

                            if is_ready:
                                # Оптимизация уже завершена (маловероятно, но возможно)
                                ready_symbols.append(symbol)
                                logger.info("✅ [%s] Оптимизация завершена, монета готова", symbol)
                            else:
                                # Оптимизация запущена, но не завершена - блокируем
                                pending_symbols.append(symbol)
                                logger.info(
                                    "⏳ [%s] Оптимизация запущена, монета заблокирована до завершения",
                                    symbol,
                                )

                    if ready_symbols:
                        logger.info(
                            "✅ Готово %d монет для генерации сигналов (из %d API, %d в оптимизации)",
                            len(ready_symbols),
                            len(filtered_symbols),
                            len(pending_symbols),
                        )
                        return ready_symbols
                    else:
                        logger.warning(
                            "⚠️ Нет готовых монет из API (все в процессе оптимизации), используем fallback на intelligent_filter_system"
                        )
                        # Продолжаем выполнение - fallback на intelligent_filter_system
        except Exception as e:
            logger.warning("⚠️ Не удалось получить монеты из API: %s, используем fallback", e)

        # ПРИОРИТЕТ 1: intelligent_filter_system (fallback)
        try:
            intelligent_coins = get_all_optimized_symbols()
            if intelligent_coins and len(intelligent_coins) > 0:
                logger.info(
                    "✅ Используем монеты из intelligent_filter_system (fallback): %d монет",
                    len(intelligent_coins),
                )
                filtered_symbols = [
                    s
                    for s in intelligent_coins
                    if s not in STABLECOIN_SYMBOLS
                    and s.endswith("USDT")
                    and not s.endswith("USDTUSDT")
                    and s.count("USDT") == 1
                ]

                # 🔧 ДОБАВЛЕНО: Фильтрация по листингу Bitget Futures
                bitget_symbols = await get_bitget_futures_symbols()
                if bitget_symbols:
                    bitget_set = set(bitget_symbols)
                    filtered_symbols = [s for s in filtered_symbols if s in bitget_set]

                if filtered_symbols:
                    # Проверяем готовность монет для генерации сигналов
                    params_manager = get_symbol_params_manager()
                    ready_symbols = []
                    for symbol in filtered_symbols:
                        # Обеспечиваем наличие параметров (добавляет новые монеты автоматически)
                        _, is_ready = await params_manager.ensure_symbol_optimized(symbol)
                        if is_ready:
                            ready_symbols.append(symbol)
                            logger.debug("✅ [%s] Монета готова (оптимизирована)", symbol)
                        else:
                            # Разрешаем монеты с базовыми параметрами
                            ready_symbols.append(symbol)
                            logger.info("✅ [%s] Монета готова (базовые параметры)", symbol)
                    logger.info(
                        "✅ Готово %d монет для генерации сигналов (из %d intelligent_filter_system)",
                        len(ready_symbols),
                        len(filtered_symbols),
                    )
                    return ready_symbols
        except Exception as e:
            logger.warning("⚠️ Не удалось загрузить монеты из intelligent_filter_system: %s", e)

        # ПРИОРИТЕТ 2: COINS из config.py (fallback)
        if not AUTO_FETCH_COINS and COINS and len(COINS) > 0:
            logger.info("✅ Используем оптимальный портфель из COINS (fallback): %s", COINS)
            filtered_symbols = [
                s
                for s in COINS
                if s not in STABLECOIN_SYMBOLS
                and s.endswith("USDT")
                and not s.endswith("USDTUSDT")
                and s.count("USDT") == 1
            ]

            # 🔧 ДОБАВЛЕНО: Фильтрация по листингу Bitget Futures
            bitget_symbols = await get_bitget_futures_symbols()
            if bitget_symbols:
                bitget_set = set(bitget_symbols)
                filtered_symbols = [s for s in filtered_symbols if s in bitget_set]

            if filtered_symbols:
                # Проверяем готовность монет для генерации сигналов
                params_manager = get_symbol_params_manager()
                ready_symbols = []
                for symbol in filtered_symbols:
                    # Обеспечиваем наличие параметров (добавляет новые монеты автоматически)
                    _, is_ready = await params_manager.ensure_symbol_optimized(symbol)
                    if is_ready:
                        ready_symbols.append(symbol)
                        logger.debug("✅ [%s] Монета готова (оптимизирована)", symbol)
                    else:
                        # Разрешаем монеты с базовыми параметрами
                        ready_symbols.append(symbol)
                        logger.info("✅ [%s] Монета готова (базовые параметры)", symbol)
                logger.info(
                    "✅ Готово %d монет для генерации сигналов (из %d)",
                    len(ready_symbols),
                    len(filtered_symbols),
                )
                return ready_symbols

        # Fallback: жестко заданный список
        logger.warning("⚠️ Все источники монет недоступны, используем fallback список")
        fallback_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SNXUSDT", "DASHUSDT", "NEARUSDT"]
        filtered_fallback = [s for s in fallback_symbols if s not in STABLECOIN_SYMBOLS]
        params_manager = get_symbol_params_manager()
        ready_symbols = []
        for symbol in filtered_fallback:
            _, is_ready = await params_manager.ensure_symbol_optimized(symbol)
            if is_ready:
                ready_symbols.append(symbol)
        return ready_symbols
    except Exception as e:
        logger.error("❌ Ошибка получения символов: %s", e)
        # Fallback список без стейблкоинов
        fallback_symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SNXUSDT", "DASHUSDT", "NEARUSDT"]
        filtered_fallback = [s for s in fallback_symbols if s not in STABLECOIN_SYMBOLS]
        return filtered_fallback


async def process_symbol_signals(
    symbol: str,
    df: Any,
    user_data_dict: Dict[str, Any],
    signal_history: List[Dict[str, Any]],
    regime_data: Dict[str, Any] = None,
    regime_multipliers: Dict[str, float] = None,
) -> int:
    """Обработка сигналов для символа"""

    signals_sent = 0

    try:
        logger.info(
            "🔍 [PROCESS] Начало обработки символа %s для %d пользователей",
            symbol,
            len(user_data_dict),
        )
        # Проверяем каждого пользователя
        for user_id, user_data in user_data_dict.items():
            try:
                logger.info(
                    "🔍 [PROCESS] %s: Генерация сигнала для пользователя %s (mode=%s)",
                    symbol,
                    user_id,
                    user_data.get("trade_mode", "unknown"),
                )
                # Генерация сигнала с учетом режима
                logger.info(
                    "🔍 [BEFORE CALL] %s: Вызов _generate_signal_impl для пользователя %s",
                    symbol,
                    user_id,
                )
                try:
                    signal_type, signal_price, ml_prediction = await _generate_signal_impl(
                        symbol, df, user_data, regime_data, regime_multipliers
                    )
                    logger.info(
                        "🔍 [AFTER CALL] %s: _generate_signal_impl вернул type=%s, price=%s",
                        symbol,
                        signal_type,
                        signal_price,
                    )
                except Exception as gen_exc:
                    logger.error(
                        "❌ [GEN ERROR] %s: Исключение в _generate_signal_impl: %s", symbol, gen_exc
                    )
                    import traceback

                    logger.error("❌ [GEN TRACEBACK] %s: %s", symbol, traceback.format_exc())
                    signal_type, signal_price, ml_prediction = None, None, None

                if signal_type and signal_price:
                    logger.info(
                        "✅ [SIGNAL GENERATED] %s: Сигнал %s @ %.8f сгенерирован для пользователя %s",
                        symbol,
                        signal_type,
                        signal_price,
                        user_id,
                    )
                    # Отправляем сигнал с учетом режима (composite и quality будут дефолтными)
                    logger.info(
                        "📤 [SEND START] %s: Начало отправки сигнала %s для пользователя %s (источник: process_symbol_signals)",
                        symbol,
                        signal_type,
                        user_id,
                    )
                    success = await send_signal(
                        symbol,
                        signal_type,
                        signal_price,
                        user_data,
                        signal_history,
                        df,
                        regime_data,
                        regime_multipliers,
                        None,
                        0.7,
                        0.6,
                        ml_prediction=ml_prediction,
                    )

                    if success:
                        signals_sent += 1
                        logger.info(
                            "📤 [SEND SUCCESS] Сигнал %s для %s отправлен пользователю %s",
                            signal_type,
                            symbol,
                            user_id,
                        )
                    else:
                        logger.warning(
                            "⚠️ [SEND FAILED] Сигнал %s для %s НЕ отправлен пользователю %s (send_signal вернул False)",
                            signal_type,
                            symbol,
                            user_id,
                        )
                else:
                    logger.info(
                        "🚫 [NO SIGNAL] %s: generate_signal вернул None для пользователя %s",
                        symbol,
                        user_id,
                    )

            except Exception as e:
                logger.error(
                    "❌ [ERROR] Ошибка обработки сигнала для пользователя %s и символа %s: %s",
                    user_id,
                    symbol,
                    e,
                )
                import traceback

                logger.error("Traceback: %s", traceback.format_exc())
                continue  # Продолжаем обработку для других пользователей

    except Exception as e:
        logger.error("Ошибка обработки сигналов для %s: %s", symbol, e)

    return signals_sent


async def get_real_time_price(symbol: str, fallback_price: float) -> float:
    """
    Получает real-time цену с fallback

    Args:
        symbol: Символ актива
        fallback_price: Цена fallback (из OHLC)

    Returns:
        Real-time цена или fallback
    """
    try:
        # Попытка 1: improved_price_api
        try:
            from src.data.price_api import get_current_price_robust

            real_time_price = await get_current_price_robust(symbol, max_retries=2)
            if real_time_price and real_time_price > 0:
                logger.debug("🎯 [REAL-TIME] %s: %.8f (свежая цена)", symbol, real_time_price)
                return real_time_price
        except Exception as e:
            logger.debug("Improved price API недоступен: %s", e)

        # Попытка 2: get_ohlc_with_fallback (1m)
        try:
            if get_ohlc_with_fallback is None:
                raise ImportError("get_ohlc_with_fallback недоступен")
            ohlc_data = await get_ohlc_with_fallback(symbol, "1m", limit=1)
            if ohlc_data and len(ohlc_data) > 0:
                real_time_price = ohlc_data[0]["close"]
                if real_time_price > 0:
                    logger.debug("🎯 [REAL-TIME] %s: %.8f (1m OHLC)", symbol, real_time_price)
                    return real_time_price
        except Exception as e:
            logger.debug("OHLC 1m недоступен: %s", e)

        # Fallback: используем цену из основного DataFrame
        logger.debug("⚠️ [FALLBACK] %s: %.8f (OHLC close)", symbol, fallback_price)
        return fallback_price

    except Exception as e:
        logger.debug("Ошибка get_real_time_price для %s: %s (fallback)", symbol, e)
        return fallback_price


def _call_ai_regulator(
    symbol: str,
    pattern_type: str,
    signal_type: str,
    signal_price: float,
    df: Any,
    score: float,
    regime_data: Dict = None,
    composite_result: Dict = None,
):
    """Helper для вызова AI-регулятора с полными данными"""
    if AI_REGULATOR_AVAILABLE and ai_regulator:
        try:
            asyncio.create_task(
                ai_regulator.process_signal_generation(
                    symbol=symbol,
                    pattern_type=pattern_type,
                    signal_type=signal_type,
                    signal_price=signal_price,
                    df=df,
                    ai_score=score,
                    market_regime=regime_data.get("regime", "UNKNOWN")
                    if regime_data
                    else "UNKNOWN",
                    composite_score=composite_result.get("composite_score", 0.0)
                    if composite_result
                    else 0.0,
                    composite_confidence=composite_result.get("confidence", 0.0)
                    if composite_result
                    else 0.0,
                )
            )
        except Exception as e:
            logger.debug("Ошибка AI-регулятора: %s", e)


async def _generate_signal_impl(
    symbol: str,
    df: Any,
    user_data: Dict[str, Any],
    regime_data: Dict[str, Any] = None,
    regime_multipliers: Dict[str, float] = None,
) -> Tuple[Optional[str], Optional[float], Optional[Dict[str, Any]]]:
    """Генерация сигнала"""
    user_id = user_data.get("user_id", "unknown")
    _ml_prediction = None
    logger.info(
        "🔍 [GENERATE START] %s: Начало генерации сигнала для пользователя %s", symbol, user_id
    )
    try:
        # 🔧 УБРАНО: Проверка is_symbol_ready() здесь не нужна, так как готовность монеты
        # уже проверяется в get_symbols() перед добавлением в список для обработки.
        # Монеты с базовыми параметрами разрешены для генерации сигналов.

        # Получаем режим торговли пользователя
        trade_mode = user_data.get("trade_mode", "spot")

        # УЛУЧШЕННАЯ валидация данных с интерполяцией
        if df is None or not hasattr(df, "shape") or df.shape[0] == 0:
            logger.warning("⚠️ [%s] Нет данных для анализа", symbol)
            pipeline_monitor.log_stage("validation", symbol, False, "Нет данных")
            return None, None, None

        # Проверяем минимальное количество баров
        if len(df) < 50:
            logger.warning("⚠️ [%s] Недостаточно баров: %d (требуется минимум 50)", symbol, len(df))
            pipeline_monitor.log_stage(
                "validation", symbol, False, f"Недостаточно баров: {len(df)}"
            )
            return None, None, None

        # Проверяем наличие обязательных колонок
        required_columns = ["close", "ema_fast", "ema_slow"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            logger.warning("⚠️ [%s] Отсутствуют колонки: %s", symbol, missing_columns)
            pipeline_monitor.log_stage(
                "validation", symbol, False, f"Отсутствуют колонки: {missing_columns}"
            )
            return None, None, None

        # УЛУЧШЕННАЯ обработка NaN/None значений с интерполяцией
        if df["close"].isna().any() or df["close"].isnull().any():
            logger.info("🔄 [%s] Обнаружены NaN/None значения, применяем интерполяцию", symbol)
            # Интерполяция для числовых колонок
            numeric_columns = df.select_dtypes(include=["number"]).columns
            df[numeric_columns] = df[numeric_columns].interpolate(method="linear")

            # Если остались NaN после интерполяции, заполняем forward fill
            df[numeric_columns] = df[numeric_columns].fillna(method="ffill")

            # Проверяем, что интерполяция помогла
            if df["close"].isna().any():
                logger.warning("⚠️ [%s] Не удалось восстановить данные после интерполяции", symbol)
                return None, None, None
            else:
                logger.info("✅ [%s] Данные успешно восстановлены интерполяцией", symbol)

        # Проверяем корректность цен после интерполяции
        if (df["close"] <= 0).any():
            logger.warning("⚠️ [%s] Обнаружены некорректные цены (<=0) после интерполяции", symbol)
            pipeline_monitor.log_stage("validation", symbol, False, "Некорректные цены")
            return None, None, None

        # Валидация пройдена успешно
        pipeline_monitor.log_stage("validation", symbol, True, "Все проверки пройдены")

        # 🆕 ПРОВЕРКА НОВОСТЕЙ ПЕРЕД РАСЧЕТОМ SCORE
        news_analysis = None
        try:
            if get_symbol_news_analysis:
                news_analysis = await get_symbol_news_analysis(symbol)
                if news_analysis:
                    logger.info(
                        "📰 [%s] Сентимент новостей: %s (score: %d)",
                        symbol,
                        news_analysis.get("sentiment"),
                        news_analysis.get("score", 0),
                    )
        except Exception as e:
            logger.debug("⚠️ Ошибка получения новостей для скоринга %s: %s", symbol, e)

        ai_params_data = load_ai_optimized_parameters()  # Загружаем актуальные параметры
        ai_params = ai_params_data.get("parameters", {})

        score = await calculate_ai_signal_score(
            df, ai_params_data, symbol, news_analysis
        )  # Передаем news_analysis

        # 🆕 СОХРАНЯЕМ НОВОСТИ В МЕТАДАННЫЕ ДЛЯ ПОСЛЕДУЮЩЕГО ИСПОЛЬЗОВАНИЯ
        if _ml_prediction is None:
            _ml_prediction = {}
        if isinstance(_ml_prediction, dict):
            _ml_prediction["news_analysis"] = news_analysis

        # Подготавливаем контекст для Smart RSI
        try:
            last_idx = df.index[-1]
            if isinstance(last_idx, pd.Timestamp):
                last_timestamp = last_idx.to_pydatetime()
            elif isinstance(last_idx, datetime):
                last_timestamp = last_idx
            else:
                last_timestamp = get_utc_now()
        except Exception:
            last_timestamp = get_utc_now()

        if "trend_strength" in df.columns and not pd.isna(df["trend_strength"].iloc[-1]):
            trend_strength_value = float(df["trend_strength"].iloc[-1])
            if trend_strength_value > 1:
                trend_strength_value = min(max(trend_strength_value / 100.0, 0.0), 1.0)
            else:
                trend_strength_value = max(min(trend_strength_value, 1.0), 0.0)
        else:
            trend_strength_value = 0.0

        if "volume_ratio" in df.columns and not pd.isna(df["volume_ratio"].iloc[-1]):
            volume_ratio_value = float(df["volume_ratio"].iloc[-1])
        else:
            volume_ratio_value = 1.0

        ai_confidence_value = max(min(score / 100.0, 1.0), 0.0)
        smart_rsi_group = get_rsi_experiment_group(symbol, last_timestamp)

        df.attrs["smart_rsi"] = {
            "symbol": symbol,
            "trend_strength": trend_strength_value,
            "volume_ratio": volume_ratio_value,
            "ai_confidence": ai_confidence_value,
            "timestamp": last_timestamp.isoformat(),
            "ab_group": smart_rsi_group,
            "btc_alignment": None,
            "decision": None,
            "reason": None,
            "adjustments": None,
        }

        filter_mode = user_data.get("filter_mode", "soft")

        # ✅ ИСПОЛЬЗУЕМ ИНДИВИДУАЛЬНЫЕ ПАРАМЕТРЫ ИЗ SYMBOL_SPECIFIC_CONFIG
        try:
            from src.core.config import DEFAULT_SYMBOL_CONFIG, SYMBOL_SPECIFIC_CONFIG

            symbol_params = SYMBOL_SPECIFIC_CONFIG.get(symbol, DEFAULT_SYMBOL_CONFIG)
            ai_score_threshold = symbol_params.get("ai_score_threshold", 5.0)
            logger.debug(
                "✅ [%s] Используем индивидуальные параметры: AI Score threshold = %.1f",
                symbol,
                ai_score_threshold,
            )
        except Exception as e:
            logger.debug(
                "⚠️ [%s] Ошибка загрузки индивидуальных параметров: %s, используем общие", symbol, e
            )
            # Используем наши оптимизированные пороги вместо ИИ-параметров
            # Стандартные пороги AI Score
            if filter_mode == "soft":
                ai_score_threshold = 15.0  # Оптимизированный порог для soft режима
            else:
                ai_score_threshold = 25.0  # Оптимизированный порог для strict режима
            logger.debug(
                "📊 [THRESHOLD] %s: AI Score threshold = %.1f (mode=%s)",
                symbol,
                ai_score_threshold,
                filter_mode,
            )

        if score < ai_score_threshold:
            user_id = user_data.get("user_id", "unknown")
            logger.warning(
                "🚫 [FILTER BLOCK] %s (user=%s): AI Score фильтр - Score %.1f < порог %.1f (mode=%s)",
                symbol,
                user_id,
                score,
                ai_score_threshold,
                filter_mode,
            )
            pipeline_monitor.log_stage(
                "ai_score", symbol, False, f"Score {score:.1f} < {ai_score_threshold}"
            )

            # 📊 Логируем отклонение в БД
            try:
                from src.utils.filter_logger import log_filter_check_async  # type: ignore
                # asyncio.create_task(log_filter_check_async(
                #     symbol=symbol,
                #     filter_type='ai_score',
                #     passed=False,
                #     reason=f"Score {score:.1f} < {ai_score_threshold}",
                #     signal_data={"score": score, "threshold": ai_score_threshold, "mode": filter_mode}
                # ))
            except Exception:
                pass
            return None, None, None

        # ИИ-скор пройден успешно
        pipeline_monitor.log_stage(
            "ai_score", symbol, True, f"Score {score:.1f} >= {ai_score_threshold}"
        )

        # COMPOSITE SIGNAL SCORE (улучшенная оценка)
        composite_bonus = 0.0
        composite_result = None  # Сохраняем для AI-регулятора

        if COMPOSITE_ENGINE_AVAILABLE and composite_engine and regime_data:
            try:
                # Определяем группу актива для composite score
                asset_group = "OTHER"
                if CORRELATION_MANAGER_AVAILABLE and correlation_manager:
                    try:
                        asset_group = await correlation_manager.get_symbol_group_async(symbol, df)
                    except Exception:
                        pass

                # Рассчитываем composite signal
                composite_result = composite_engine.calculate_composite_score(
                    df,
                    asset_group,
                    regime_data.get("regime", "LOW_VOL_RANGE"),
                    signal_type="BUY",  # Пока только BUY, для SELL добавим позже
                )

                # Бонус к score на основе composite confidence
                if composite_result["confidence"] > 0.7:
                    composite_bonus = (composite_result["confidence"] - 0.7) * 20  # макс +6 к score
                    score += composite_bonus
                    logger.info(
                        "🎯 [%s] Composite бонус: +%.1f (confidence: %.2f)",
                        symbol,
                        composite_bonus,
                        composite_result["confidence"],
                    )

            except Exception as e:
                logger.debug("Ошибка composite signal: %s", e)

        # Дополнительные ИИ-оптимизированные проверки
        if not check_ai_volume_filter(df, ai_params):
            user_id = user_data.get("user_id", "unknown")
            logger.warning(
                "🚫 [FILTER BLOCK] %s (user=%s): Volume фильтр - Объем ниже порога", symbol, user_id
            )
            pipeline_monitor.log_stage("volume", symbol, False, "Объем ниже порога")
            # 📊 Логируем отклонение в БД
            try:
                from src.utils.filter_logger import log_filter_check_async  # type: ignore
                # asyncio.create_task(log_filter_check_async(
                #     symbol=symbol,
                #     filter_type='ai_volume',
                #     passed=False,
                #     reason="Объем ниже порога",
                #     signal_data={"volume_ratio": float(df['volume_ratio'].iloc[-1]) if 'volume_ratio' in df.columns else 0}
                # ))
            except Exception:
                pass
            return None, None, None

        # Объемный фильтр пройден успешно
        pipeline_monitor.log_stage("volume", symbol, True, "Объем выше порога")

        if not check_ai_volatility_filter(df, ai_params):
            user_id = user_data.get("user_id", "unknown")
            logger.warning(
                "🚫 [FILTER BLOCK] %s (user=%s): Volatility фильтр - Волатильность вне диапазона",
                symbol,
                user_id,
            )
            pipeline_monitor.log_stage("volatility", symbol, False, "Волатильность вне диапазона")
            # 📊 Логируем отклонение в БД
            try:
                from src.utils.filter_logger import log_filter_check_async  # type: ignore
                # asyncio.create_task(log_filter_check_async(
                #     symbol=symbol,
                #     filter_type='ai_volatility',
                #     passed=False,
                #     reason="Волатильность вне диапазона",
                #     signal_data={"volatility": float(df['volatility'].iloc[-1]) if 'volatility' in df.columns else 0}
                # ))
            except Exception:
                pass
            return None, None, None

        # Волатильность фильтр пройден успешно
        pipeline_monitor.log_stage("volatility", symbol, True, "Волатильность в диапазоне")

        # КРИТИЧЕСКАЯ ПРОВЕРКА: Блокировка по аномалиям (как в рабочей версии от 19 октября)
        try:
            # Получаем цену закрытия свечи для анализа
            candle_close_price = df["close"].iloc[-1]

            # 🆕 ПОЛУЧАЕМ REAL-TIME ЦЕНУ для более точного входа
            current_price = await get_real_time_price(symbol, candle_close_price)

            # Индикаторы для предварительной проверки
            ema_fast_prelim = float(df["ema_fast"].iloc[-1])
            ema_slow_prelim = float(df["ema_slow"].iloc[-1])

            # Простое определение направления для проверки аномалий
            if current_price > ema_fast_prelim and ema_fast_prelim > ema_slow_prelim:
                preliminary_signal_type = "LONG"
            else:
                preliminary_signal_type = "SHORT"

            # Убираем таймаут — пусть работает асинхронно без блокировки
            try:
                circles_count, _, _, anomaly_data_ok = await asyncio.wait_for(
                    calculate_anomaly_circles_with_fallback(symbol, preliminary_signal_type),
                    timeout=10.0,  # Увеличили до 10 сек
                )
            except asyncio.TimeoutError:
                # Таймаут — используем безопасные дефолты
                circles_count, anomaly_data_ok = None, False
                logger.debug("⏱️ [%s] Проверка аномалий timeout (10s), используем fallback", symbol)

            user_id = user_data.get("user_id", "unknown")

            # Блокируем максимальный риск (5 кружков) - манипуляции
            if anomaly_data_ok and circles_count and circles_count >= 5:
                logger.warning(
                    "[Risk][BLOCK] %s для %s: максимальный риск (уровень %d) — сигнал заблокирован",
                    symbol,
                    user_id,
                    circles_count,
                )
                circles_display = circles_count if circles_count is not None else 0
                pipeline_monitor.log_stage(
                    "anomaly_filter", symbol, False, f"Максимальный риск: {circles_display} кружков"
                )
                # 📊 Логируем отклонение в БД
                try:
                    from src.utils.filter_logger import log_filter_check_async  # type: ignore
                    # asyncio.create_task(log_filter_check_async(
                    #     symbol=symbol,
                    #     filter_type='anomaly_filter',
                    #     passed=False,
                    #     reason=f"Максимальный риск: {circles_display} кружков",
                    #     signal_data={"circles": circles_count, "price": current_price}
                    # ))
                except Exception:
                    pass
                return None, None, None

            # Блокируем минимальный риск (0 кружков) - низкая ликвидность
            # 0 кружков = тухлые сигналы, блокируем ВСЕГДА (в любом режиме)
            if anomaly_data_ok and (circles_count is None or circles_count <= 0):
                logger.warning(
                    "[Risk][BLOCK] %s для %s: низкая ликвидность (0 кружков) — сигнал заблокирован",
                    symbol,
                    user_id,
                )
                pipeline_monitor.log_stage(
                    "anomaly_filter", symbol, False, "Низкая ликвидность: 0 кружков"
                )
                # 📊 Логируем отклонение в БД
                try:
                    from src.utils.filter_logger import log_filter_check_async  # type: ignore
                    # asyncio.create_task(log_filter_check_async(
                    #     symbol=symbol,
                    #     filter_type='anomaly_filter',
                    #     passed=False,
                    #     reason="Низкая ликвидность: 0 кружков",
                    #     signal_data={"circles": 0, "price": current_price}
                    # ))
                except Exception:
                    pass
                return None, None, None

            # Предупреждение для высокого риска (4 кружка)
            if anomaly_data_ok and circles_count and circles_count >= 4:
                logger.warning(
                    "[Risk][WARNING] %s для %s: высокий риск (уровень %d) — снижены параметры",
                    symbol,
                    user_id,
                    circles_count,
                )
                # Не блокируем, но отмечаем для снижения параметров

            logger.info(
                "[Risk][OK] %s для %s: риск приемлемый (уровень %d) — сигнал разрешен",
                symbol,
                user_id,
                circles_count or 0,
            )
            circles_display = circles_count if circles_count is not None else 0
            pipeline_monitor.log_stage(
                "anomaly_filter", symbol, True, f"Риск приемлемый: {circles_display} кружков"
            )

        except (ImportError, asyncio.TimeoutError, Exception) as e:
            error_type = type(e).__name__
            error_msg = str(e) if str(e).strip() else "Пустое сообщение ошибки"
            logger.debug(
                "⚠️ Проверка аномалий для %s: %s - %s. Сигнал разрешен (fallback)",
                symbol,
                error_type,
                error_msg,
            )
            pipeline_monitor.log_stage("anomaly_filter", symbol, True, f"Fallback: {error_type}")
            # При ошибке не блокируем сигнал

        # УЛУЧШЕННАЯ логика генерации сигнала с альтернативными паттернами
        current_price = float(df["close"].iloc[-1])
        ema_fast_series = df["ema_fast"]  # Сохраняем Series для проверок тренда
        ema_slow_series = df["ema_slow"]
        ema_fast = float(ema_fast_series.iloc[-1])
        ema_slow = float(ema_slow_series.iloc[-1])
        current_volume = float(df["volume"].iloc[-1])
        avg_volume = float(df["volume"].rolling(window=20).mean().iloc[-1])

        # НОВАЯ ПРОВЕРКА: Блокируем символов с проблемной историей
        if symbol_blocker.is_blocked(symbol):
            logger.warning("🚫 %s: Символ заблокирован", symbol)
            return None, None, None

        # НОВАЯ ПРОВЕРКА: Проверяем здоровье символа
        symbol_health = symbol_blocker.get_symbol_health(symbol)
        if symbol_health < 0.5:  # Здоровье символа ниже 50%
            logger.warning("🚫 %s: Низкое здоровье символа (%.1f%%)", symbol, symbol_health * 100)
            return None, None, None

        # 🔍 НОВАЯ ПРОВЕРКА: Проверка ликвидности перед генерацией сигнала
        try:
            from liquidity_checker import (
                DEFAULT_MIN_24H_VOLUME_USD,
                DEFAULT_MIN_DEPTH_USD,
                check_liquidity,
            )

            from config import RISK_FILTERS

            min_depth_required = RISK_FILTERS.get("min_depth_usd", DEFAULT_MIN_DEPTH_USD)
            min_volume_required = RISK_FILTERS.get(
                "min_volume_24h",
                DEFAULT_MIN_24H_VOLUME_USD,
            )
            max_spread_allowed = RISK_FILTERS.get("max_spread_pct", 0.5)

            liquidity_kwargs = {
                "min_depth_usd": min_depth_required,
                "min_24h_volume_usd": min_volume_required,
                "max_spread_pct": max_spread_allowed,
                "depth_levels": 20,
                "require_both": False,
            }
            # pylint: disable=unexpected-keyword-arg
            liquidity_ok, liquidity_details = await check_liquidity(symbol, **liquidity_kwargs)
            if not liquidity_ok:
                logger.info(
                    (
                        "🚫 %s: Проверка ликвидности/спреда не пройдена "
                        "(depth: %.2f USD / min %.2f USD, 24h volume: %.2f USD / min %.2f USD, spread: %.4f%% / max %.2f%%)"
                    ),
                    symbol,
                    liquidity_details.get("depth_usd", 0) or 0,
                    min_depth_required,
                    liquidity_details.get("volume_24h_usd", 0) or 0,
                    min_volume_required,
                    liquidity_details.get("spread_pct", 0) or 0,
                    max_spread_allowed,
                )
                return None, None, None
            else:
                logger.debug(
                    (
                        "✅ %s: Ликвидность и спред в норме "
                        "(depth: %.2f USD ≥ %.2f USD, 24h volume: %.2f USD ≥ %.2f USD, spread: %.4f%% ≤ %.2f%%)"
                    ),
                    symbol,
                    liquidity_details.get("depth_usd", 0) or 0,
                    min_depth_required,
                    liquidity_details.get("volume_24h_usd", 0) or 0,
                    min_volume_required,
                    liquidity_details.get("spread_pct", 0) or 0,
                    max_spread_allowed,
                )
        except (ImportError, Exception) as e:
            logger.debug("⚠️ Проверка ликвидности недоступна для %s: %s (пропускаем)", symbol, e)

        # 🆕 НОВАЯ ЛОГИКА ВХОДА: Вход на откате к поддержке (если включено)
        # Если USE_PULLBACK_ENTRY=true, используем новую логику вместо EMA кроссовера
        use_new_entry_logic = (
            NEW_ENTRY_LOGIC_AVAILABLE and pullback_entry_logic and USE_PULLBACK_ENTRY
        )

        if use_new_entry_logic:
            # НОВАЯ ЛОГИКА: Вход на откате к поддержке
            should_enter, entry_details = pullback_entry_logic.should_enter_long(
                df,
                current_price,
                min_quality_score=PULLBACK_ENTRY_CONFIG.get("min_quality_score", 0.6),
                require_trend=PULLBACK_ENTRY_CONFIG.get("require_trend", True),
                use_adaptive_config=USE_ADAPTIVE_STRATEGY,  # Использовать адаптивную конфигурацию
            )

            if should_enter:
                signal_type = "BUY"
                signal_price = current_price
                pattern_type = "pullback_to_support"
                logger.info(
                    "✅ [PULLBACK ENTRY] %s: Вход на откате к поддержке (Quality=%.2f, Regime=%s)",
                    symbol,
                    entry_details.get("quality_score", 0),
                    entry_details.get("market_regime", "UNKNOWN"),
                )
                pipeline_monitor.log_stage(
                    "pullback_entry",
                    symbol,
                    True,
                    f"Quality={entry_details.get('quality_score', 0):.2f}",
                )
                pipeline_monitor.log_pattern_type(pattern_type)

                # 🔥 КРИТИЧЕСКИЕ ПРОВЕРКИ НАПРАВЛЕНИЯ СИГНАЛА (те же, что и для старой логики)
                logger.info(
                    "🔍 [PULLBACK ENTRY] %s: Проверка трендов (умная логика на основе корреляции)...",
                    symbol,
                )
                if not await check_all_trend_alignments(symbol, signal_type, df):
                    logger.warning("🚫 [PULLBACK ENTRY] %s: Тренд alignment не пройден", symbol)
                    return None, None, None
                logger.info("✅ [PULLBACK ENTRY] %s: Тренд alignment пройден", symbol)

                # 🆕 ПРОВЕРКА НОВЫХ ФИЛЬТРОВ
                new_filters_passed, new_filters_reason = await check_new_filters(
                    symbol, signal_type, current_price, df, strict_mode=filter_mode == "strict"
                )
                if not new_filters_passed:
                    logger.warning(
                        "🚫 [PULLBACK ENTRY] %s: Новые фильтры заблокировали: %s",
                        symbol,
                        new_filters_reason,
                    )
                    return None, None, None
                logger.info(
                    "✅ [PULLBACK ENTRY] %s: Новые фильтры пройдены (%s)",
                    symbol,
                    new_filters_reason,
                )

                # Проверка RSI warning
                if not await check_rsi_warning(df, signal_type):
                    logger.warning("🚫 [PULLBACK ENTRY] %s: RSI warning не пройден", symbol)
                    return None, None, None

                # Продолжаем с остальными проверками (quality, volume и т.д.)
                # Переходим к проверкам качества ниже
            else:
                # Если новая логика не прошла, пробуем старую (EMA кроссовер) как fallback
                logger.debug(
                    "⏭️ [PULLBACK ENTRY] %s: Не прошел проверку (%s), пробуем EMA кроссовер",
                    symbol,
                    entry_details.get("reason", "Unknown"),
                )
                use_new_entry_logic = False

        # СТАРАЯ ЛОГИКА: Классический EMA кроссовер (fallback или если новая логика отключена)
        if not use_new_entry_logic and current_price > ema_fast and ema_fast > ema_slow:
            signal_type = "BUY"
            signal_price = current_price
            pattern_type = "classic_ema"
            logger.debug("✅ %s: Классический EMA кроссовер", symbol)
            pipeline_monitor.log_stage("ema_pattern", symbol, True, "Классический EMA кроссовер")
            pipeline_monitor.log_pattern_type(pattern_type)

            # 🔥 КРИТИЧЕСКИЕ ПРОВЕРКИ НАПРАВЛЕНИЯ СИГНАЛА
            logger.info("🔍 [LONG CLASSIC] %s: Проверка трендов (умная логика)...", symbol)
            trend_result = await check_all_trend_alignments(symbol, signal_type, df)
            if not trend_result:
                logger.warning(
                    "🚫 [LONG CLASSIC] %s: Тренд alignment не пройден - сигнал заблокирован, авто-исполнение не будет",
                    symbol,
                )
                return None, None, None
            logger.info("✅ [LONG CLASSIC] %s: Все тренды alignment пройдены", symbol)
            # 🔧 ИСПРАВЛЕНО: Убрано дублирование кода (Игорь - после аудита)
            set_smart_rsi_btc_alignment(df, True)

            # 🆕 ПРОВЕРКА НОВЫХ ФИЛЬТРОВ: Dominance Trend и Interest Zone
            new_filters_passed, new_filters_reason = await check_new_filters(
                symbol, signal_type, current_price, df, strict_mode=filter_mode == "strict"
            )
            if not new_filters_passed:
                logger.warning(
                    "🚫 [LONG CLASSIC] %s: Новые фильтры заблокировали сигнал: %s",
                    symbol,
                    new_filters_reason,
                )
                pipeline_monitor.log_stage("new_filters", symbol, False, new_filters_reason)
                return None, None, None
            logger.info(
                "✅ [LONG CLASSIC] %s: Новые фильтры пройдены (%s)", symbol, new_filters_reason
            )
            pipeline_monitor.log_stage("new_filters", symbol, True, new_filters_reason)

            # 🔧 ВРЕМЕННО ОТКЛЮЧЕН ДЛЯ СООТВЕТСТВИЯ УСПЕШНОМУ БЭКТЕСТУ
            # В успешном бэктесте (Win Rate 56.84%, PnL +54.69%) direction confidence был отключен
            # logger.info("🔍 [LONG CLASSIC] %s: Проверка direction confidence...", symbol)
            # if not calculate_direction_confidence(
            #     df,
            #     signal_type,
            #     trade_mode,
            #     user_data.get("filter_mode", "soft"),
            # ):
            #     logger.warning("🚫 [LONG CLASSIC] %s: Direction confidence не пройден (недостаточно подтверждений)", symbol)
            #     return None, None, None
            # logger.info("✅ [LONG CLASSIC] %s: Direction confidence пройден", symbol)
            logger.debug(
                "⏭️ [LONG CLASSIC] %s: Direction confidence временно отключен (как в успешном бэктесте)",
                symbol,
            )

            logger.info("🔍 [LONG CLASSIC] %s: Проверка RSI warning...", symbol)
            if not await check_rsi_warning(df, signal_type):
                logger.warning(
                    "🚫 [LONG CLASSIC] %s: RSI warning не пройден (RSI в опасной зоне)", symbol
                )
                return None, None, None
            logger.info("✅ [LONG CLASSIC] %s: RSI warning пройден", symbol)

            # НОВАЯ ПРОВЕРКА: Quality Score и Pattern Confidence
            quality_score = quality_validator.calculate_quality_score(df, signal_type, symbol)
            pattern_confidence = pattern_scorer.calculate_pattern_confidence(
                pattern_type, df, signal_type
            )

            # БОНУС: Проверка близости к статическим уровням
            if LEVELS_DETECTOR_AVAILABLE and levels_detector:
                try:
                    static_levels = levels_detector.find_levels(
                        df, lookback_period=100, min_touches=2
                    )
                    levels_bonus = levels_detector.get_levels_quality_bonus(
                        current_price, signal_type, static_levels
                    )

                    if levels_bonus > 0:
                        quality_score += levels_bonus
                        logger.debug(
                            "✅ %s: Бонус к качеству от статических уровней: +%.2f%%",
                            symbol,
                            levels_bonus * 100,
                        )
                except Exception as e:
                    logger.debug("Ошибка проверки статических уровней: %s", e)

            # Логирование будет обновлено после расчета адаптивных порогов

            # ✅ АДАПТИВНЫЕ пороги Quality и Confidence на основе рыночных условий
            # Базовые пороги
            base_quality_threshold = 0.68  # Стандартный порог для LONG
            base_confidence_threshold = 0.60  # Стандартный порог для паттернов

            # Рассчитываем адаптивные поправки на основе рыночных условий
            market_adjustment = 0.0

            # 🔧 БАЗОВОЕ СНИЖЕНИЕ ДЛЯ ВОССТАНОВЛЕНИЯ СИГНАЛОВ
            # 🔧 ПОДДЕРЖКА БЭКТЕСТОВ: Переопределение через environment variable
            backtest_market_adjustment = os.getenv("BACKTEST_market_adjustment")
            if backtest_market_adjustment is not None:
                market_adjustment = float(backtest_market_adjustment)
                logger.debug(
                    "🔧 [BACKTEST] Используем переопределенный market_adjustment: %.3f",
                    market_adjustment,
                )
            else:
                # Оптимизировано на основе бэктеста (3 месяца, топ-20 монет, 15 потоков)
                # Результаты: Win Rate 68.81%, Profit Factor 1.29, Total Return +0.52%, Max Drawdown 0.37%
                # См. docs/FILTER_PARAMETERS_OPTIMIZATION_RESULTS.md
                market_adjustment -= 0.10  # Базовое снижение для оптимальной производительности
            logger.info("📊 [ADAPTIVE] Базовое снижение порогов для восстановления сигналов: -0.10")

            # 1. Проверка времени (воскресенье ночь = низкая активность)
            now = get_utc_now()
            current_hour = now.hour  # Используем UTC для консистентности
            current_weekday = now.weekday()  # 6 = воскресенье

            # Воскресенье - максимальное снижение
            if current_weekday == 6:  # Воскресенье
                market_adjustment -= 0.12
                logger.info("📅 [ADAPTIVE] Воскресная адаптация для %s: -0.12", symbol)

            # 🕒 АДАПТАЦИЯ ПО ВРЕМЕНИ СУТОК
            # Вечер/ночь (20:00-08:00 MSK = 17:00-05:00 UTC)
            if current_hour >= 17 or current_hour < 5:
                market_adjustment -= 0.08
                logger.info(
                    "🌙 [ADAPTIVE] Ночная адаптация для %s (час=%d UTC): -0.08",
                    symbol,
                    current_hour,
                )

            # 2. Проверка волатильности (низкая волатильность = снижаем пороги)
            try:
                if "volatility" in df.columns and len(df) > 0:
                    current_volatility = (
                        df["volatility"].iloc[-1]
                        if not pd.isna(df["volatility"].iloc[-1])
                        else None
                    )
                    avg_volatility = df["volatility"].mean() if "volatility" in df.columns else None

                    if (
                        current_volatility is not None
                        and avg_volatility is not None
                        and avg_volatility > 0
                    ):
                        # Если волатильность ниже средней на 30%+
                        if current_volatility < avg_volatility * 0.7:
                            vol_adjustment = min(
                                0.15, (avg_volatility - current_volatility) / avg_volatility * 0.30
                            )  # 🔧 УВЕЛИЧЕНО: до 0.15
                            market_adjustment -= vol_adjustment
                            logger.info(
                                "📉 [ADAPTIVE] Низкая волатильность (%.2f%% < %.2f%%): снижаем пороги на %.3f",
                                current_volatility,
                                avg_volatility,
                                vol_adjustment,
                            )
            except Exception as e:
                logger.debug("Ошибка расчета адаптации по волатильности: %s", e)

            # 3. Проверка объема (низкий объем = снижаем пороги)
            try:
                if "volume" in df.columns and len(df) > 0:
                    current_volume = (
                        df["volume"].iloc[-1] if not pd.isna(df["volume"].iloc[-1]) else None
                    )
                    avg_volume = (
                        df["volume"].rolling(window=20).mean().iloc[-1] if len(df) >= 20 else None
                    )

                    if current_volume is not None and avg_volume is not None and avg_volume > 0:
                        volume_ratio = current_volume / avg_volume
                        # Если объем ниже среднего на 30%+
                        if volume_ratio < 0.7:
                            vol_adjustment = min(
                                0.12, (0.7 - volume_ratio) * 0.25
                            )  # 🔧 УВЕЛИЧЕНО: до 0.12
                            market_adjustment -= vol_adjustment
                            logger.info(
                                "📊 [ADAPTIVE] Низкий объем (ratio=%.2f): снижаем пороги на %.3f",
                                volume_ratio,
                                vol_adjustment,
                            )
                    else:
                        # 🔧 ДОБАВЛЕНО: Если нет данных по объему, применяем базовое снижение
                        logger.debug("📊 [ADAPTIVE] Нет данных по объему, пропускаем адаптацию")
            except Exception as e:
                logger.debug("Ошибка расчета адаптации по объему: %s", e)

            # 4. Используем AI-оптимизированные параметры если доступны
            try:
                ai_params = load_ai_optimized_parameters()
                if ai_params and isinstance(ai_params, dict):
                    # Проверяем есть ли адаптивные параметры для Quality
                    quality_params = ai_params.get("quality_thresholds", {})
                    if quality_params and isinstance(quality_params, dict):
                        adaptive_quality = quality_params.get("long", {}).get(filter_mode, None)
                        if adaptive_quality is not None:
                            base_quality_threshold = adaptive_quality
                            logger.debug(
                                "🤖 [AI ADAPTIVE] Используем AI-оптимизированный порог Quality: %.3f (mode=%s)",
                                base_quality_threshold,
                                filter_mode,
                            )
            except Exception as e:
                logger.debug("Ошибка загрузки AI-параметров для Quality: %s", e)

            # 📉 ДОПОЛНИТЕЛЬНОЕ СНИЖЕНИЕ ПРИ НИЗКОЙ АКТИВНОСТИ
            # Если за последний час было менее 5 сигналов
            try:
                recent_signals_count = _get_recent_signals_count(hours=1)
                if recent_signals_count < 5:
                    market_adjustment -= 0.05
                    logger.info(
                        "📉 [ADAPTIVE] Адаптация по низкой активности для %s (<5 сигналов за час): -0.05",
                        symbol,
                    )
            except Exception as e:
                logger.debug("⚠️ Ошибка подсчета сигналов для адаптации: %s", e)
                # При ошибке все равно применяем дополнительное снижение для восстановления
                market_adjustment -= 0.05
                logger.info(
                    "📉 [ADAPTIVE] Применяем снижение по умолчанию (ошибка подсчета): -0.05"
                )

            # Применяем адаптивные поправки (но не ниже минимума)
            # 🔧 ПОДДЕРЖКА БЭКТЕСТОВ: Переопределение через environment variables
            backtest_min_quality_long = os.getenv("BACKTEST_min_quality_threshold_long")
            if backtest_min_quality_long is not None:
                min_quality_threshold = float(backtest_min_quality_long)
                logger.debug(
                    "🔧 [BACKTEST] Используем переопределенный min_quality_threshold LONG: %.3f",
                    min_quality_threshold,
                )
            else:
                # Оптимизировано на основе бэктеста (3 месяца, топ-20 монет, 15 потоков)
                # Результаты: Win Rate 68.81%, Profit Factor 1.29, Total Return +0.52%, Max Drawdown 0.37%
                # См. docs/FILTER_PARAMETERS_OPTIMIZATION_RESULTS.md
                min_quality_threshold = max(0.33, base_quality_threshold + market_adjustment)

            backtest_min_confidence_long = os.getenv("BACKTEST_min_confidence_threshold_long")
            if backtest_min_confidence_long is not None:
                min_confidence_threshold = float(backtest_min_confidence_long)
                logger.debug(
                    "🔧 [BACKTEST] Используем переопределенный min_confidence_threshold LONG: %.3f",
                    min_confidence_threshold,
                )
            else:
                min_confidence_threshold = max(
                    0.40, base_confidence_threshold + market_adjustment * 0.7
                )

            # 📊 ДЕТАЛЬНОЕ ЛОГИРОВАНИЕ
            logger.info(
                "🎯 [ADAPTIVE THRESHOLDS] %s: Quality=%.3f (base=%.3f, adjustment=%.3f), Confidence=%.3f "
                "(время: %02d:00 UTC, день: %d)",
                symbol,
                min_quality_threshold,
                base_quality_threshold,
                market_adjustment,
                min_confidence_threshold,
                current_hour,
                current_weekday,
            )

            # 🌍 4. ГЛОБАЛЬНЫЙ МАКРО-ФИЛЬТР (DXY)
            try:
                from src.data.macro_provider import get_macro_provider

                macro = get_macro_provider().get_dxy_trend()
                dxy_trend = macro.get("trend", "NEUTRAL")

                # Если DXY сильно бычий (BULLISH + STRONG), повышаем требования к качеству LONG сигналов
                if dxy_trend == "BULLISH" and macro.get("strength") == "STRONG":
                    if signal_type == "LONG":
                        min_quality_threshold += 0.05
                        logger.info(
                            "🌍 [MACRO] DXY Strong Bullish -> LONG quality threshold increased (+0.05)"
                        )

                # Если DXY медвежий (BEARISH), можно чуть ослабить для LONG
                elif dxy_trend == "BEARISH":
                    if signal_type == "LONG":
                        min_quality_threshold = max(0.40, min_quality_threshold - 0.02)
                        logger.info(
                            "🌍 [MACRO] DXY Bearish -> LONG quality threshold relaxed (-0.02)"
                        )
            except Exception as e:
                logger.debug("🌍 [MACRO] Ошибка получения данных DXY: %s", e)

            if quality_score < min_quality_threshold:
                user_id = user_data.get("user_id", "unknown")
                logger.warning(
                    "🚫 [FILTER BLOCK] %s (user=%s) LONG CLASSIC: Quality фильтр - Score %.3f < порог %.3f (base=%.3f, adjustment=%.3f)",
                    symbol,
                    user_id,
                    quality_score,
                    min_quality_threshold,
                    base_quality_threshold,
                    market_adjustment,
                )
                return None, None, None

            if pattern_confidence < min_confidence_threshold:
                user_id = user_data.get("user_id", "unknown")
                logger.warning(
                    "🚫 [FILTER BLOCK] %s (user=%s) LONG CLASSIC: Confidence фильтр - Confidence %.3f < порог %.3f",
                    symbol,
                    user_id,
                    pattern_confidence,
                    min_confidence_threshold,
                )
                return None, None, None

            logger.info(
                "✅ [QUALITY PASS] %s LONG CLASSIC: Quality %.3f >= %.3f, Confidence %.3f >= %.3f",
                symbol,
                quality_score,
                min_quality_threshold,
                pattern_confidence,
                min_confidence_threshold,
            )

            # НОВАЯ ИНТЕГРАЦИЯ: Дополнительные защитные проверки
            if DEFENSE_SYSTEMS_AVAILABLE and volume_detector:
                try:
                    # Проверка на манипуляции объемом
                    volume_quality = volume_detector.get_volume_quality(df)
                    if volume_quality < 0.8:  # Качество объема < 80%
                        logger.warning(
                            "🚫 [VOLUME BLOCK] %s LONG CLASSIC: Volume quality %.3f < 0.80 (манипуляции объемом)",
                            symbol,
                            volume_quality,
                        )
                        pipeline_monitor.log_stage(
                            "volume_quality",
                            symbol,
                            False,
                            f"Volume quality {volume_quality:.3f} < 0.80",
                        )
                        return None, None, None
                    else:
                        logger.info(
                            "✅ [VOLUME PASS] %s LONG CLASSIC: Volume quality %.3f >= 0.80",
                            symbol,
                            volume_quality,
                        )
                except Exception as e:
                    logger.debug("Ошибка проверки объема: %s", e)

            # НОВАЯ ИНТЕГРАЦИЯ: AI-регулятор отслеживает генерацию сигнала
            _call_ai_regulator(
                symbol,
                pattern_type,
                signal_type,
                signal_price,
                df,
                score,
                regime_data,
                composite_result,
            )

            # 🆕 КРИТИЧЕСКАЯ ПРОВЕРКА: False Breakout Detector
            if FALSE_BREAKOUT_DETECTOR_AVAILABLE and false_breakout_detector:
                try:
                    breakout_context = {}
                    if regime_data:
                        breakout_context["regime"] = regime_data.get("regime")
                        breakout_context["regime_confidence"] = regime_data.get("confidence")

                    # 🤖 ML ОПТИМИЗАЦИЯ: Получаем оптимизированный порог false_breakout
                    try:
                        from src.ai.filter_optimizer import AIFilterOptimizer

                        ml_optimizer = AIFilterOptimizer()
                        # AIFilterOptimizer не имеет метода is_trained, всегда выполняем оптимизацию
                        # AIFilterOptimizer не имеет метода optimize_filter_parameters, используем текущие параметры
                        optimized_params = (
                            ml_optimizer.load_optimized_params()
                        )  # Используем публичный метод

                        # 🆕 ML оптимизированный порог
                        ml_false_breakout_threshold = optimized_params.get(
                            "false_breakout_threshold"
                        )
                        if ml_false_breakout_threshold is not None:
                            breakout_context["ml_false_breakout_threshold"] = (
                                ml_false_breakout_threshold
                            )
                            logger.debug(
                                "🤖 [ML_FALSE_BREAKOUT] %s: ML оптимизированный порог = %.3f",
                                symbol,
                                ml_false_breakout_threshold,
                            )

                        # 🆕 ML оптимизированные веса
                        ml_weights = optimized_params.get("false_breakout_weights")
                        if ml_weights:
                            breakout_context["ml_false_breakout_weights"] = ml_weights
                            logger.debug(
                                "🤖 [ML_WEIGHTS] %s: ML веса (vol=%.2f, mom=%.2f, lvl=%.2f)",
                                symbol,
                                ml_weights.get("volume", 0.40),
                                ml_weights.get("momentum", 0.30),
                                ml_weights.get("level", 0.30),
                            )
                    except Exception as ml_e:
                        logger.debug(
                            "⚠️ [ML_FALSE_BREAKOUT] %s: ошибка ML оптимизации, используем стандартный порог: %s",
                            symbol,
                            ml_e,
                        )

                    breakout_analysis = await false_breakout_detector.analyze_breakout_quality(
                        df, symbol, signal_type, breakout_context
                    )

                    if breakout_analysis.get("is_false_breakout", False):
                        logger.warning(
                            "🚫 [BREAKOUT BLOCK] %s %s LONG CLASSIC: False breakout обнаружен (confidence: %.2f)",
                            symbol,
                            signal_type,
                            breakout_analysis.get("confidence", 0.0),
                        )
                        pipeline_monitor.log_stage(
                            "false_breakout",
                            symbol,
                            False,
                            f"False breakout detected (confidence: {breakout_analysis.get('confidence', 0.0):.2f})",
                        )
                        return None, None, None
                    else:
                        logger.info(
                            "✅ [BREAKOUT PASS] %s %s LONG CLASSIC: False breakout не обнаружен (confidence: %.2f)",
                            symbol,
                            signal_type,
                            breakout_analysis.get("confidence", 1.0),
                        )
                except Exception as e:
                    logger.debug(
                        "⚠️ Ошибка false breakout detector для %s: %s (пропускаем проверку)",
                        symbol,
                        e,
                    )

            # 🔥 MTF CONFIRMATION (H4 таймфрейм)
            # 🔧 ВОССТАНОВЛЕНО: MTF включен с улучшенной логикой для LONG
            # ✅ Улучшения (аналогично SHORT):
            #   1. H4 не снижает confidence ниже 0.2 для LONG
            #   2. Умный fallback с учетом всех факторов (H1, market, H4)
            #   3. Более мягкие условия для H1 тренда для LONG
            logger.info(
                "🔍 [MTF CHECK] %s LONG CLASSIC: Проверка MTF confirmation (улучшенная логика)...",
                symbol,
            )
            mtf_ok, mtf_error = await _run_mtf_confirmation_with_logging(
                symbol, signal_type, regime_data
            )
            logger.info(
                "🔍 [MTF RESULT] %s LONG CLASSIC: MTF ok=%s, error=%s", symbol, mtf_ok, mtf_error
            )
            if not mtf_ok:
                user_id = user_data.get("user_id", "unknown")
                logger.warning(
                    "🚫 [MTF BLOCK] %s (user=%s) LONG CLASSIC: MTF confirmation не пройден: %s",
                    symbol,
                    user_id,
                    mtf_error or "MTF не подтвержден",
                )
                pipeline_monitor.log_stage(
                    "mtf_confirmation", symbol, False, f"MTF блокировка: {mtf_error}"
                )
                return None, None, None
            logger.info("✅ [MTF PASS] %s LONG CLASSIC: MTF confirmation пройден", symbol)

            # AI-регулятор
            logger.info("📊 [AI REGULATOR] %s LONG: Вызов AI регулятора...", symbol)
            _call_ai_regulator(
                symbol, pattern_type, signal_type, signal_price, df, 0.0, regime_data, None
            )

            # 🔧 ИСПРАВЛЕНО: Рассчитываем TP перед ML фильтром для более точных предсказаний (Дмитрий - после аудита)
            trade_mode = user_data.get("trade_mode", "spot")
            last_idx = len(df) - 1
            try:
                tp1_pct, tp2_pct = get_dynamic_tp_levels(
                    df, last_idx, side="long", trade_mode=trade_mode, adjust_for_fees=True
                )
                tp1_price = signal_price * (1 + tp1_pct / 100.0)
                tp2_price = signal_price * (1 + tp2_pct / 100.0)
            except Exception as e:
                logger.debug("⚠️ [TP CALC] %s: Ошибка расчёта TP, используем дефолты: %s", symbol, e)
                tp1_price = signal_price * 1.02  # Дефолт 2%
                tp2_price = signal_price * 1.04  # Дефолт 4%

            # 🆕 ML ФИЛЬТР: Проверка через LightGBM
            ml_passed, ml_reason, _ml_prediction = await check_ml_filter(
                symbol=symbol,
                signal_type=signal_type,
                entry_price=signal_price,
                df=df,
                quality_score=quality_score,
                mtf_score=0.5,  # Можно получить из MTF конфирмера
                tp1=tp1_price,  # 🔧 ИСПРАВЛЕНО: Рассчитан перед вызовом
                tp2=tp2_price,  # 🔧 ИСПРАВЛЕНО: Рассчитан перед вызовом
                risk_pct=user_data.get("risk_pct", 2.0),
                leverage=user_data.get("leverage", 1.0),
                regime_data=regime_data,
            )

            if not ml_passed:
                logger.warning(
                    "🚫 [ML BLOCK] %s LONG CLASSIC: ML фильтр заблокировал сигнал: %s",
                    symbol,
                    ml_reason,
                )
                pipeline_monitor.log_stage("ml_filter", symbol, False, ml_reason)
                return None, None, None

            # Логируем детали предсказания если доступны
            if _ml_prediction:
                logger.debug(
                    "📊 [ML DETAILS] %s: prob=%.2f%%, profit=%.2f%%, score=%.3f",
                    symbol,
                    _ml_prediction.get("success_probability", 0) * 100,
                    _ml_prediction.get("expected_profit_pct", 0),
                    _ml_prediction.get("combined_score", 0),
                )

            logger.info("✅ [ML PASS] %s LONG CLASSIC: ML фильтр пройден: %s", symbol, ml_reason)
            pipeline_monitor.log_stage("ml_filter", symbol, True, ml_reason)

            logger.info(
                "✅ [SIGNAL GENERATED] %s LONG CLASSIC: Сигнал успешно сгенерирован! Quality=%.3f, Confidence=%.3f",
                symbol,
                quality_score,
                pattern_confidence,
            )
            pipeline_monitor.log_stage("final_signal", symbol, True, "Сигнал сгенерирован")

            # 📊 Записываем метрику генерации сигнала (Елена)
            if PROMETHEUS_METRICS_AVAILABLE:
                try:
                    record_signal_generated(
                        symbol=symbol, signal_type=signal_type, pattern_type=pattern_type
                    )
                except Exception:
                    pass

            return signal_type, signal_price, _ml_prediction

        # Альтернативный паттерн 1: EMA близко к кроссоверу + бычий бар + объем
        elif (
            ema_fast > ema_slow * 0.995  # EMA близко к кроссоверу
            and current_price > df["open"].iloc[-1]  # Бычий бар
            and current_volume > avg_volume * 1.2
        ):  # Объем выше среднего
            signal_type = "BUY"
            signal_price = current_price
            pattern_type = "alternative_1"
            logger.debug("✅ %s: Альтернативный паттерн 1 (EMA близко + бычий бар + объем)", symbol)
            pipeline_monitor.log_stage("ema_pattern", symbol, True, "Альтернативный паттерн 1")
            pipeline_monitor.log_pattern_type(pattern_type)

            # 🔥 КРИТИЧЕСКИЕ ПРОВЕРКИ НАПРАВЛЕНИЯ СИГНАЛА
            if not await check_all_trend_alignments(symbol, signal_type, df):
                return None, None, None
            # 🔧 ИСПРАВЛЕНО: Убрано дублирование кода (Игорь - после аудита)
            set_smart_rsi_btc_alignment(df, True)
            # 🔧 ВРЕМЕННО ОТКЛЮЧЕН ДЛЯ СООТВЕТСТВИЯ УСПЕШНОМУ БЭКТЕСТУ
            # if not calculate_direction_confidence(
            #     df,
            #     signal_type,
            #     trade_mode,
            #     user_data.get("filter_mode", "soft"),
            # ):
            #     return None, None, None
            if not await check_rsi_warning(df, signal_type):
                return None, None, None

            # Проверка качества и надежности
            quality_score = quality_validator.calculate_quality_score(df, signal_type, symbol)
            pattern_confidence = pattern_scorer.calculate_pattern_confidence(
                pattern_type, df, signal_type
            )

            if not quality_validator.is_signal_valid(
                quality_score
            ) or not pattern_scorer.is_pattern_reliable(pattern_confidence):
                logger.debug("🚫 %s: Паттерн 1 не прошел проверку качества", symbol)
                return None, None, None

            logger.debug(
                "✅ %s: Quality %.2f, Confidence %.2f", symbol, quality_score, pattern_confidence
            )

            # 🔥 MTF CONFIRMATION (H4 таймфрейм)
            mtf_ok, _ = await _run_mtf_confirmation_with_logging(symbol, signal_type, regime_data)
            if not mtf_ok:
                return None, None, None

            # AI-регулятор
            _call_ai_regulator(
                symbol, pattern_type, signal_type, signal_price, df, 0.0, regime_data, None
            )

            # 🔧 ИСПРАВЛЕНО: Рассчитываем TP перед ML фильтром (Дмитрий - после аудита)
            trade_mode = user_data.get("trade_mode", "spot")
            tp1_price, tp2_price = calculate_tp_prices_for_ml(
                signal_price, df, signal_type, trade_mode
            )

            # 🆕 ML ФИЛЬТР: Проверка через LightGBM
            ml_passed, ml_reason, _ml_prediction = await check_ml_filter(
                symbol=symbol,
                signal_type=signal_type,
                entry_price=signal_price,
                df=df,
                quality_score=quality_score,
                mtf_score=0.5,  # Можно получить из MTF конфирмера
                tp1=tp1_price,  # 🔧 ИСПРАВЛЕНО: Рассчитан перед вызовом
                tp2=tp2_price,  # 🔧 ИСПРАВЛЕНО: Рассчитан перед вызовом
                risk_pct=user_data.get("risk_pct", 2.0),
                leverage=user_data.get("leverage", 1.0),
                regime_data=regime_data,
            )

            if not ml_passed:
                logger.warning(
                    "🚫 [ML BLOCK] %s LONG Alt-1: ML фильтр заблокировал сигнал: %s",
                    symbol,
                    ml_reason,
                )
                pipeline_monitor.log_stage("ml_filter", symbol, False, ml_reason)
                return None, None, None

            # Логируем детали предсказания если доступны
            if _ml_prediction:
                logger.debug(
                    "📊 [ML DETAILS] %s: prob=%.2f%%, profit=%.2f%%, score=%.3f",
                    symbol,
                    _ml_prediction.get("success_probability", 0) * 100,
                    _ml_prediction.get("expected_profit_pct", 0),
                    _ml_prediction.get("combined_score", 0),
                )

            logger.info("✅ [ML PASS] %s LONG Alt-1: ML фильтр пройден: %s", symbol, ml_reason)
            pipeline_monitor.log_stage("ml_filter", symbol, True, ml_reason)

            pipeline_monitor.log_stage("final_signal", symbol, True, "Сигнал сгенерирован")
            return signal_type, signal_price, _ml_prediction

        # Альтернативный паттерн 2: Цена выше EMA + восходящий тренд + RSI не перекуплен
        elif (
            current_price > ema_fast  # Цена выше быстрой EMA
            and ema_fast > float(ema_fast_series.iloc[-2])  # Восходящий тренд EMA
            and "rsi" in df.columns
            and df["rsi"].iloc[-1] < 70
        ):  # RSI не перекуплен
            signal_type = "BUY"
            signal_price = current_price
            pattern_type = "alternative_2"
            logger.debug("✅ %s: Альтернативный паттерн 2 (цена > EMA + тренд + RSI)", symbol)
            pipeline_monitor.log_stage("ema_pattern", symbol, True, "Альтернативный паттерн 2")
            pipeline_monitor.log_pattern_type(pattern_type)

            # 🔥 КРИТИЧЕСКИЕ ПРОВЕРКИ НАПРАВЛЕНИЯ СИГНАЛА
            if not await check_all_trend_alignments(symbol, signal_type, df):
                return None, None, None
            # 🆕 ПРОВЕРКА НОВЫХ ФИЛЬТРОВ
            new_filters_passed, new_filters_reason = await check_new_filters(
                symbol, signal_type, signal_price, df, strict_mode=filter_mode == "strict"
            )
            if not new_filters_passed:
                logger.warning(
                    "🚫 [ALT-2] %s: Новые фильтры заблокировали: %s", symbol, new_filters_reason
                )
                return None, None, None
            # 🔧 ВРЕМЕННО ОТКЛЮЧЕН ДЛЯ СООТВЕТСТВИЯ УСПЕШНОМУ БЭКТЕСТУ
            # if not calculate_direction_confidence(
            #     df,
            #     signal_type,
            #     trade_mode,
            #     user_data.get("filter_mode", "soft"),
            # ):
            #     return None, None, None
            if not await check_rsi_warning(df, signal_type):
                return None, None, None

            # Проверка качества и надежности
            quality_score = quality_validator.calculate_quality_score(df, signal_type, symbol)
            pattern_confidence = pattern_scorer.calculate_pattern_confidence(
                pattern_type, df, signal_type
            )

            if not quality_validator.is_signal_valid(
                quality_score
            ) or not pattern_scorer.is_pattern_reliable(pattern_confidence):
                logger.debug("🚫 %s: Паттерн 2 не прошел проверку качества", symbol)
                return None, None, None

            logger.debug(
                "✅ %s: Quality %.2f, Confidence %.2f", symbol, quality_score, pattern_confidence
            )

            # 🔥 MTF CONFIRMATION (H4 таймфрейм)
            mtf_ok, _ = await _run_mtf_confirmation_with_logging(symbol, signal_type, regime_data)
            if not mtf_ok:
                return None, None, None

            # AI-регулятор
            _call_ai_regulator(
                symbol, pattern_type, signal_type, signal_price, df, 0.0, regime_data, None
            )

            # 🔧 ИСПРАВЛЕНО: Рассчитываем TP перед ML фильтром (Дмитрий - после аудита)
            trade_mode = user_data.get("trade_mode", "spot")
            tp1_price, tp2_price = calculate_tp_prices_for_ml(
                signal_price, df, signal_type, trade_mode
            )

            # 🆕 ML ФИЛЬТР: Проверка через LightGBM
            ml_passed, ml_reason, _ml_prediction = await check_ml_filter(
                symbol=symbol,
                signal_type=signal_type,
                entry_price=signal_price,
                df=df,
                quality_score=quality_score,
                mtf_score=0.5,  # Можно получить из MTF конфирмера
                tp1=tp1_price,  # 🔧 ИСПРАВЛЕНО: Рассчитан перед вызовом
                tp2=tp2_price,  # 🔧 ИСПРАВЛЕНО: Рассчитан перед вызовом
                risk_pct=user_data.get("risk_pct", 2.0),
                leverage=user_data.get("leverage", 1.0),
                regime_data=regime_data,
            )

            if not ml_passed:
                logger.warning(
                    "🚫 [ML BLOCK] %s LONG Alt-2: ML фильтр заблокировал сигнал: %s",
                    symbol,
                    ml_reason,
                )
                pipeline_monitor.log_stage("ml_filter", symbol, False, ml_reason)
                return None, None, None

            # Логируем детали предсказания если доступны
            if _ml_prediction:
                logger.debug(
                    "📊 [ML DETAILS] %s: prob=%.2f%%, profit=%.2f%%, score=%.3f",
                    symbol,
                    _ml_prediction.get("success_probability", 0) * 100,
                    _ml_prediction.get("expected_profit_pct", 0),
                    _ml_prediction.get("combined_score", 0),
                )

            logger.info("✅ [ML PASS] %s LONG Alt-2: ML фильтр пройден: %s", symbol, ml_reason)
            pipeline_monitor.log_stage("ml_filter", symbol, True, ml_reason)

            pipeline_monitor.log_stage("final_signal", symbol, True, "Сигнал сгенерирован")
            return signal_type, signal_price, _ml_prediction

        # Альтернативный паттерн 3: Отскок от поддержки + объем
        elif (
            current_price > df["low"].iloc[-1] * 1.001  # Отскок от минимума
            and current_volume > avg_volume * 1.5  # Высокий объем
            and "bb_lower" in df.columns
            and current_price > df["bb_lower"].iloc[-1]
        ):  # Выше нижней BB
            signal_type = "BUY"
            signal_price = current_price
            pattern_type = "alternative_3"
            logger.debug("✅ %s: Альтернативный паттерн 3 (отскок + объем + BB)", symbol)
            pipeline_monitor.log_stage("ema_pattern", symbol, True, "Альтернативный паттерн 3")
            pipeline_monitor.log_pattern_type(pattern_type)

            # 🔥 КРИТИЧЕСКИЕ ПРОВЕРКИ НАПРАВЛЕНИЯ СИГНАЛА
            if not await check_all_trend_alignments(symbol, signal_type, df):
                return None, None, None
            # 🆕 ПРОВЕРКА НОВЫХ ФИЛЬТРОВ
            new_filters_passed, new_filters_reason = await check_new_filters(
                symbol, signal_type, signal_price, df, strict_mode=filter_mode == "strict"
            )
            if not new_filters_passed:
                logger.warning(
                    "🚫 [ALT-2] %s: Новые фильтры заблокировали: %s", symbol, new_filters_reason
                )
                return None, None, None
            # 🔧 ВРЕМЕННО ОТКЛЮЧЕН ДЛЯ СООТВЕТСТВИЯ УСПЕШНОМУ БЭКТЕСТУ
            # if not calculate_direction_confidence(
            #     df,
            #     signal_type,
            #     trade_mode,
            #     user_data.get("filter_mode", "soft"),
            # ):
            #     return None, None, None
            if not await check_rsi_warning(df, signal_type):
                return None, None, None

            # Проверка качества и надежности
            quality_score = quality_validator.calculate_quality_score(df, signal_type, symbol)
            pattern_confidence = pattern_scorer.calculate_pattern_confidence(
                pattern_type, df, signal_type
            )

            if not quality_validator.is_signal_valid(
                quality_score
            ) or not pattern_scorer.is_pattern_reliable(pattern_confidence):
                logger.debug("🚫 %s: Паттерн 3 не прошел проверку качества", symbol)
                return None, None, None

            logger.debug(
                "✅ %s: Quality %.2f, Confidence %.2f", symbol, quality_score, pattern_confidence
            )

            # Дополнительные защитные проверки
            if DEFENSE_SYSTEMS_AVAILABLE and volume_detector:
                try:
                    volume_quality = volume_detector.get_volume_quality(df)
                    if volume_quality < 0.8:
                        return None, None, None
                except Exception as e:
                    logger.debug("Ошибка проверки объема: %s", e)

            # 🔥 MTF CONFIRMATION (H4 таймфрейм)
            mtf_ok, _ = await _run_mtf_confirmation_with_logging(symbol, signal_type, regime_data)
            if not mtf_ok:
                return None, None, None

            # AI-регулятор
            _call_ai_regulator(
                symbol, pattern_type, signal_type, signal_price, df, 0.0, regime_data, None
            )

            # 🔧 ИСПРАВЛЕНО: Рассчитываем TP перед ML фильтром (Дмитрий - после аудита)
            trade_mode = user_data.get("trade_mode", "spot")
            tp1_price, tp2_price = calculate_tp_prices_for_ml(
                signal_price, df, signal_type, trade_mode
            )

            # 🆕 ML ФИЛЬТР: Проверка через LightGBM
            ml_passed, ml_reason, _ml_prediction = await check_ml_filter(
                symbol=symbol,
                signal_type=signal_type,
                entry_price=signal_price,
                df=df,
                quality_score=quality_score,
                mtf_score=0.5,  # Можно получить из MTF конфирмера
                tp1=tp1_price,  # 🔧 ИСПРАВЛЕНО: Рассчитан перед вызовом
                tp2=tp2_price,  # 🔧 ИСПРАВЛЕНО: Рассчитан перед вызовом
                risk_pct=user_data.get("risk_pct", 2.0),
                leverage=user_data.get("leverage", 1.0),
                regime_data=regime_data,
            )

            if not ml_passed:
                logger.warning(
                    "🚫 [ML BLOCK] %s LONG Alt-3: ML фильтр заблокировал сигнал: %s",
                    symbol,
                    ml_reason,
                )
                pipeline_monitor.log_stage("ml_filter", symbol, False, ml_reason)
                return None, None, None

            # Логируем детали предсказания если доступны
            if _ml_prediction:
                logger.debug(
                    "📊 [ML DETAILS] %s: prob=%.2f%%, profit=%.2f%%, score=%.3f",
                    symbol,
                    _ml_prediction.get("success_probability", 0) * 100,
                    _ml_prediction.get("expected_profit_pct", 0),
                    _ml_prediction.get("combined_score", 0),
                )

            logger.info("✅ [ML PASS] %s LONG Alt-3: ML фильтр пройден: %s", symbol, ml_reason)
            pipeline_monitor.log_stage("ml_filter", symbol, True, ml_reason)

            pipeline_monitor.log_stage("final_signal", symbol, True, "Сигнал сгенерирован")
            return signal_type, signal_price, _ml_prediction

        # ШОРТОВЫЕ ПАТТЕРНЫ (только для FUTURES режима)
        # 🆕 НОВАЯ ЛОГИКА ВХОДА: Вход на откате к сопротивлению (если включено)
        use_new_short_entry_logic = (
            NEW_ENTRY_LOGIC_AVAILABLE
            and pullback_entry_logic
            and USE_PULLBACK_ENTRY
            and trade_mode == "futures"
        )

        if use_new_short_entry_logic:
            # НОВАЯ ЛОГИКА: Вход на откате к сопротивлению
            should_enter, entry_details = pullback_entry_logic.should_enter_short(
                df,
                current_price,
                min_quality_score=PULLBACK_ENTRY_CONFIG.get("min_quality_score", 0.6),
                require_trend=PULLBACK_ENTRY_CONFIG.get("require_trend", True),
                use_adaptive_config=USE_ADAPTIVE_STRATEGY,  # Использовать адаптивную конфигурацию
            )

            if should_enter:
                signal_type = "SELL"
                signal_price = current_price
                pattern_type = "pullback_to_resistance"
                logger.info(
                    "✅ [PULLBACK ENTRY SHORT] %s: Вход на откате к сопротивлению (Quality=%.2f, Regime=%s)",
                    symbol,
                    entry_details.get("quality_score", 0),
                    entry_details.get("market_regime", "UNKNOWN"),
                )
                pipeline_monitor.log_stage(
                    "pullback_entry",
                    symbol,
                    True,
                    f"Quality={entry_details.get('quality_score', 0):.2f}",
                )
                pipeline_monitor.log_pattern_type(pattern_type)

                # 🔥 КРИТИЧЕСКИЕ ПРОВЕРКИ НАПРАВЛЕНИЯ СИГНАЛА
                logger.info(
                    "🔍 [PULLBACK ENTRY SHORT] %s: Проверка трендов (умная логика)...", symbol
                )
                if not await check_all_trend_alignments(symbol, signal_type, df):
                    logger.warning(
                        "🚫 [PULLBACK ENTRY SHORT] %s: Тренд alignment не пройден", symbol
                    )
                    return None, None, None
                logger.info("✅ [PULLBACK ENTRY SHORT] %s: BTC alignment пройден", symbol)

                # 🆕 ПРОВЕРКА НОВЫХ ФИЛЬТРОВ
                new_filters_passed, new_filters_reason = await check_new_filters(
                    symbol, signal_type, current_price, df, strict_mode=filter_mode == "strict"
                )
                if not new_filters_passed:
                    logger.warning(
                        "🚫 [PULLBACK ENTRY SHORT] %s: Новые фильтры заблокировали: %s",
                        symbol,
                        new_filters_reason,
                    )
                    return None, None, None
                logger.info(
                    "✅ [PULLBACK ENTRY SHORT] %s: Новые фильтры пройдены (%s)",
                    symbol,
                    new_filters_reason,
                )

                # Проверка RSI warning
                if not await check_rsi_warning(df, signal_type):
                    logger.warning("🚫 [PULLBACK ENTRY SHORT] %s: RSI warning не пройден", symbol)
                    return None, None, None

                # Продолжаем с остальными проверками
            else:
                # Если новая логика не прошла, пробуем старую (EMA кроссовер) как fallback
                logger.debug(
                    "⏭️ [PULLBACK ENTRY SHORT] %s: Не прошел проверку (%s), пробуем EMA кроссовер",
                    symbol,
                    entry_details.get("reason", "Unknown"),
                )
                use_new_short_entry_logic = False

        # СТАРАЯ ЛОГИКА: Классический медвежий кроссовер EMA (fallback или если новая логика отключена)
        if not use_new_short_entry_logic and current_price < ema_fast and ema_fast < ema_slow:
            # 🔍 ЛОГИРОВАНИЕ ДО ПРОВЕРКИ РЕЖИМА
            logger.info(
                "🔍 [SHORT CLASSIC] %s: Обнаружен классический медвежий EMA кроссовер (цена=%.8f, ema_fast=%.8f, ema_slow=%.8f, режим=%s)",
                symbol,
                current_price,
                ema_fast,
                ema_slow,
                trade_mode,
            )
            pipeline_monitor.log_stage(
                "ema_pattern", symbol, True, f"Классический медвежий EMA (режим: {trade_mode})"
            )

            # Проверяем режим торговли - SHORT только для FUTURES
            if trade_mode != "futures":
                logger.warning(
                    "🚫 [SHORT CLASSIC BLOCK] %s: SHORT сигнал пропущен (режим: %s, требуется: futures)",
                    symbol,
                    trade_mode,
                )
                pipeline_monitor.log_stage(
                    "trade_mode_check", symbol, False, f"Режим {trade_mode} не позволяет SHORT"
                )
                return None, None, None

            logger.info(
                "✅ [SHORT CLASSIC] %s: Режим проверен (futures), продолжаем генерацию сигнала",
                symbol,
            )

            signal_type = "SELL"
            signal_price = current_price
            pattern_type = "classic_ema_short"
            logger.debug("✅ %s: Классический медвежий EMA кроссовер (FUTURES)", symbol)
            pipeline_monitor.log_stage("ema_pattern", symbol, True, "Классический медвежий EMA")
            pipeline_monitor.log_pattern_type("short_classic_ema")

            # 🔥 КРИТИЧЕСКИЕ ПРОВЕРКИ НАПРАВЛЕНИЯ СИГНАЛА
            logger.info("🔍 [SHORT CLASSIC] %s: Проверка трендов (умная логика)...", symbol)
            if not await check_all_trend_alignments(symbol, signal_type, df):
                logger.warning("🚫 [SHORT CLASSIC] %s: Тренд alignment не пройден", symbol)
                return None, None, None
            logger.info("✅ [SHORT CLASSIC] %s: BTC alignment пройден", symbol)

            # 🆕 ПРОВЕРКА НОВЫХ ФИЛЬТРОВ
            new_filters_passed, new_filters_reason = await check_new_filters(
                symbol, signal_type, current_price, df, strict_mode=filter_mode == "strict"
            )
            if not new_filters_passed:
                logger.warning(
                    "🚫 [SHORT CLASSIC] %s: Новые фильтры заблокировали: %s",
                    symbol,
                    new_filters_reason,
                )
                return None, None, None
            logger.info(
                "✅ [SHORT CLASSIC] %s: Новые фильтры пройдены (%s)", symbol, new_filters_reason
            )

            # 🔧 ВРЕМЕННО ОТКЛЮЧЕН ДЛЯ СООТВЕТСТВИЯ УСПЕШНОМУ БЭКТЕСТУ
            # В успешном бэктесте (Win Rate 56.84%, PnL +54.69%) direction confidence был отключен
            # logger.info("🔍 [SHORT CLASSIC] %s: Проверка direction confidence...", symbol)
            # if not calculate_direction_confidence(
            #     df,
            #     signal_type,
            #     trade_mode,
            #     user_data.get("filter_mode", "soft"),
            # ):
            #     logger.warning("🚫 [SHORT CLASSIC] %s: Direction confidence не пройден (недостаточно подтверждений)", symbol)
            #     return None, None, None
            # logger.info("✅ [SHORT CLASSIC] %s: Direction confidence пройден", symbol)
            logger.debug(
                "⏭️ [SHORT CLASSIC] %s: Direction confidence временно отключен (как в успешном бэктесте)",
                symbol,
            )

            logger.info("🔍 [SHORT CLASSIC] %s: Проверка RSI warning...", symbol)
            if not await check_rsi_warning(df, signal_type):
                logger.warning(
                    "🚫 [SHORT CLASSIC] %s: RSI warning не пройден (RSI в опасной зоне)", symbol
                )
                return None, None, None
            logger.info("✅ [SHORT CLASSIC] %s: RSI warning пройден", symbol)

            # УСИЛЕННАЯ проверка качества для SHORT (более строгие требования)
            quality_score = quality_validator.calculate_quality_score(df, signal_type, symbol)
            pattern_confidence = pattern_scorer.calculate_pattern_confidence(
                pattern_type, df, signal_type
            )

            # SHORT требует более высокого качества (72% vs 70% для LONG, смягчено для интрадей)
            # 🔧 ПОДДЕРЖКА БЭКТЕСТОВ: Переопределение через environment variables
            backtest_min_quality_short = os.getenv("BACKTEST_min_quality_for_short")
            if backtest_min_quality_short is not None:
                min_quality_for_short = float(backtest_min_quality_short)
                logger.debug(
                    "🔧 [BACKTEST] Используем переопределенный min_quality_for_short: %.3f",
                    min_quality_for_short,
                )
            else:
                # Оптимизировано на основе бэктеста (3 месяца, топ-20 монет, 15 потоков)
                # Результаты: Win Rate 68.81%, Profit Factor 1.29, Total Return +0.52%, Max Drawdown 0.37%
                # См. docs/FILTER_PARAMETERS_OPTIMIZATION_RESULTS.md
                min_quality_for_short = 0.45

            backtest_min_confidence_short = os.getenv("BACKTEST_min_confidence_for_short")
            if backtest_min_confidence_short is not None:
                min_confidence_for_short = float(backtest_min_confidence_short)
                logger.debug(
                    "🔧 [BACKTEST] Используем переопределенный min_confidence_for_short: %.3f",
                    min_confidence_for_short,
                )
            else:
                # Оптимизировано на основе бэктеста (3 месяца, топ-20 монет, 15 потоков)
                # Результаты: Win Rate 68.81%, Profit Factor 1.29, Total Return +0.52%, Max Drawdown 0.37%
                # См. docs/FILTER_PARAMETERS_OPTIMIZATION_RESULTS.md
                min_confidence_for_short = 0.40

            logger.info(
                "📊 [QUALITY CHECK] %s SHORT CLASSIC: Quality=%.3f (min=%.2f), Confidence=%.3f (min=%.2f)",
                symbol,
                quality_score,
                min_quality_for_short,
                pattern_confidence,
                min_confidence_for_short,
            )

            # 🌍 4. ГЛОБАЛЬНЫЙ МАКРО-ФИЛЬТР (DXY)
            try:
                from src.data.macro_provider import get_macro_provider

                macro = get_macro_provider().get_dxy_trend()
                dxy_trend = macro.get("trend", "NEUTRAL")

                # Если DXY медвежий (BEARISH), повышаем требования к качеству SHORT сигналов
                if dxy_trend == "BEARISH":
                    min_quality_for_short += 0.05
                    logger.info(
                        "🌍 [MACRO] DXY Bearish -> SHORT quality threshold increased (+0.05)"
                    )

                # Если DXY бычий (BULLISH), можно чуть ослабить для SHORT
                elif dxy_trend == "BULLISH":
                    min_quality_for_short = max(0.40, min_quality_for_short - 0.02)
                    logger.info("🌍 [MACRO] DXY Bullish -> SHORT quality threshold relaxed (-0.02)")
            except Exception as e:
                logger.debug("🌍 [MACRO] Ошибка получения данных DXY: %s", e)

            if quality_score < min_quality_for_short:
                logger.warning(
                    "🚫 [QUALITY BLOCK] %s SHORT CLASSIC: Quality score %.3f < %.2f",
                    symbol,
                    quality_score,
                    min_quality_for_short,
                )
                pipeline_monitor.log_stage(
                    "quality_check",
                    symbol,
                    False,
                    f"Quality {quality_score:.3f} < {min_quality_for_short}",
                )
                return None, None, None

            if pattern_confidence < min_confidence_for_short:
                logger.warning(
                    "🚫 [CONFIDENCE BLOCK] %s SHORT CLASSIC: Pattern confidence %.3f < %.2f",
                    symbol,
                    pattern_confidence,
                    min_confidence_for_short,
                )
                pipeline_monitor.log_stage(
                    "confidence_check",
                    symbol,
                    False,
                    f"Confidence {pattern_confidence:.3f} < {min_confidence_for_short}",
                )
                return None, None, None

            logger.info(
                "✅ [QUALITY PASS] %s SHORT CLASSIC: Quality %.3f >= %.2f, Confidence %.3f >= %.2f",
                symbol,
                quality_score,
                min_quality_for_short,
                pattern_confidence,
                min_confidence_for_short,
            )

            # УСИЛЕННАЯ проверка объема для SHORT (85% vs 80% для LONG)
            if DEFENSE_SYSTEMS_AVAILABLE and volume_detector:
                try:
                    volume_quality = volume_detector.get_volume_quality(df)
                    min_volume_quality_for_short = 0.85
                    logger.info(
                        "📊 [VOLUME QUALITY] %s SHORT: Volume quality=%.3f (min=%.2f)",
                        symbol,
                        volume_quality,
                        min_volume_quality_for_short,
                    )
                    if volume_quality < min_volume_quality_for_short:
                        logger.warning(
                            "🚫 [VOLUME BLOCK] %s SHORT: Volume quality %.3f < %.2f",
                            symbol,
                            volume_quality,
                            min_volume_quality_for_short,
                        )
                        pipeline_monitor.log_stage(
                            "volume_quality",
                            symbol,
                            False,
                            f"Volume quality {volume_quality:.3f} < {min_volume_quality_for_short}",
                        )
                        return None, None, None
                    logger.info(
                        "✅ [VOLUME PASS] %s SHORT: Volume quality %.3f >= %.2f",
                        symbol,
                        volume_quality,
                        min_volume_quality_for_short,
                    )
                except Exception as e:
                    logger.warning(
                        "⚠️ [VOLUME ERROR] Ошибка проверки объема для %s: %s (пропускаем)", symbol, e
                    )

            # 🔥 MTF CONFIRMATION (H4 таймфрейм)
            # 🔧 ВОССТАНОВЛЕНО: MTF включен с улучшенной логикой для SHORT
            # ✅ Улучшения:
            #   1. H4 не снижает confidence ниже 0.2 для SHORT
            #   2. Умный fallback с учетом всех факторов (H1, market, H4)
            #   3. Более мягкие условия для H1 тренда для SHORT
            logger.info(
                "🔍 [MTF CHECK] %s SHORT CLASSIC: Проверка MTF confirmation (улучшенная логика)...",
                symbol,
            )
            mtf_ok, mtf_error = await _run_mtf_confirmation_with_logging(
                symbol, signal_type, regime_data
            )
            logger.info(
                "🔍 [MTF RESULT] %s SHORT CLASSIC: MTF ok=%s, error=%s", symbol, mtf_ok, mtf_error
            )
            if not mtf_ok:
                logger.warning(
                    "🚫 [MTF BLOCK] %s SHORT CLASSIC: MTF confirmation не пройден: %s",
                    symbol,
                    mtf_error,
                )
                return None, None, None
            logger.info("✅ [MTF PASS] %s SHORT CLASSIC: MTF confirmation пройден", symbol)

            # AI-регулятор
            logger.info("📊 [AI REGULATOR] %s SHORT: Вызов AI регулятора...", symbol)
            _call_ai_regulator(
                symbol, pattern_type, signal_type, signal_price, df, 0.0, regime_data, None
            )

            # 🆕 ML ФИЛЬТР: Проверка через LightGBM
            ml_passed, ml_reason, _ml_prediction = await check_ml_filter(
                symbol=symbol,
                signal_type=signal_type,
                entry_price=signal_price,
                df=df,
                quality_score=quality_score,
                mtf_score=0.5,  # Можно получить из MTF конфирмера
                tp1=None,  # Будет рассчитан позже
                tp2=None,  # Будет рассчитан позже
                risk_pct=user_data.get("risk_pct", 2.0),
                leverage=user_data.get("leverage", 1.0),
                regime_data=regime_data,
            )

            if not ml_passed:
                logger.warning(
                    "🚫 [ML BLOCK] %s SHORT CLASSIC: ML фильтр заблокировал сигнал: %s",
                    symbol,
                    ml_reason,
                )
                pipeline_monitor.log_stage("ml_filter", symbol, False, ml_reason)
                return None, None, None

            # Логируем детали предсказания если доступны
            if _ml_prediction:
                logger.debug(
                    "📊 [ML DETAILS] %s: prob=%.2f%%, profit=%.2f%%, score=%.3f",
                    symbol,
                    _ml_prediction.get("success_probability", 0) * 100,
                    _ml_prediction.get("expected_profit_pct", 0),
                    _ml_prediction.get("combined_score", 0),
                )

            logger.info("✅ [ML PASS] %s SHORT CLASSIC: ML фильтр пройден: %s", symbol, ml_reason)
            pipeline_monitor.log_stage("ml_filter", symbol, True, ml_reason)

            logger.info(
                "✅ [SIGNAL GENERATED] %s SHORT CLASSIC: Сигнал успешно сгенерирован! Quality=%.3f, Confidence=%.3f",
                symbol,
                quality_score,
                pattern_confidence,
            )
            pipeline_monitor.log_stage("final_signal", symbol, True, "SHORT сигнал сгенерирован")

            # 📊 Записываем метрику генерации сигнала (Елена)
            if PROMETHEUS_METRICS_AVAILABLE:
                try:
                    record_signal_generated(
                        symbol=symbol, signal_type=signal_type, pattern_type=pattern_type
                    )
                except Exception:
                    pass

            return signal_type, signal_price, _ml_prediction

        # Альтернативный SHORT паттерн 1: EMA близко к кроссоверу + медвежий бар + объем (только FUTURES)
        elif (
            ema_fast < ema_slow * 1.005  # EMA близко к кроссоверу (медвежий)
            and current_price < df["open"].iloc[-1]  # Медвежий бар
            and current_volume > avg_volume * 1.2
        ):  # Объем выше среднего
            # 🔍 ЛОГИРОВАНИЕ ДО ПРОВЕРКИ РЕЖИМА
            logger.info(
                "🔍 [SHORT Alt-1] %s: Обнаружен альтернативный паттерн 1 (режим=%s)",
                symbol,
                trade_mode,
            )
            pipeline_monitor.log_stage(
                "ema_pattern", symbol, True, f"SHORT Альтернативный паттерн 1 (режим: {trade_mode})"
            )

            # Проверяем режим торговли - SHORT только для FUTURES
            if trade_mode != "futures":
                logger.warning(
                    "🚫 [SHORT Alt-1 BLOCK] %s: SHORT сигнал пропущен (режим: %s, требуется: futures)",
                    symbol,
                    trade_mode,
                )
                pipeline_monitor.log_stage(
                    "trade_mode_check", symbol, False, f"Режим {trade_mode} не позволяет SHORT"
                )
                return None, None, None

            logger.info(
                "✅ [SHORT Alt-1] %s: Режим проверен (futures), продолжаем генерацию сигнала",
                symbol,
            )
            signal_type = "SELL"
            signal_price = current_price
            pattern_type = "alternative_short_1"
            logger.debug(
                "✅ %s: SHORT Альтернативный паттерн 1 (EMA близко + медвежий бар + объем)", symbol
            )
            pipeline_monitor.log_stage(
                "ema_pattern", symbol, True, "SHORT Альтернативный паттерн 1"
            )
            pipeline_monitor.log_pattern_type("short_alternative_1")

            # 🔥 КРИТИЧЕСКИЕ ПРОВЕРКИ НАПРАВЛЕНИЯ СИГНАЛА
            if not await check_all_trend_alignments(symbol, signal_type, df):
                return None, None, None
            # 🆕 ПРОВЕРКА НОВЫХ ФИЛЬТРОВ
            new_filters_passed, new_filters_reason = await check_new_filters(
                symbol, signal_type, signal_price, df, strict_mode=filter_mode == "strict"
            )
            if not new_filters_passed:
                logger.warning(
                    "🚫 [ALT-2] %s: Новые фильтры заблокировали: %s", symbol, new_filters_reason
                )
                return None, None, None
            # 🔧 ВРЕМЕННО ОТКЛЮЧЕН ДЛЯ СООТВЕТСТВИЯ УСПЕШНОМУ БЭКТЕСТУ
            # if not calculate_direction_confidence(
            #     df,
            #     signal_type,
            #     trade_mode,
            #     user_data.get("filter_mode", "soft"),
            # ):
            #     return None, None, None
            if not await check_rsi_warning(df, signal_type):
                return None, None, None

            # Проверка качества (усиленные требования для SHORT)
            quality_score = quality_validator.calculate_quality_score(df, signal_type, symbol)
            pattern_confidence = pattern_scorer.calculate_pattern_confidence(
                pattern_type, df, signal_type
            )

            # 🔧 ПОДДЕРЖКА БЭКТЕСТОВ: Переопределение через environment variables
            backtest_min_quality_short = os.getenv("BACKTEST_min_quality_for_short")
            if backtest_min_quality_short is not None:
                min_quality_for_short = float(backtest_min_quality_short)
                logger.debug(
                    "🔧 [BACKTEST] Используем переопределенный min_quality_for_short: %.3f",
                    min_quality_for_short,
                )
            else:
                # Оптимизировано на основе бэктеста (3 месяца, топ-20 монет, 15 потоков)
                # Результаты: Win Rate 68.81%, Profit Factor 1.29, Total Return +0.52%, Max Drawdown 0.37%
                # См. docs/FILTER_PARAMETERS_OPTIMIZATION_RESULTS.md
                min_quality_for_short = 0.45

            backtest_min_confidence_short = os.getenv("BACKTEST_min_confidence_for_short")
            if backtest_min_confidence_short is not None:
                min_confidence_for_short = float(backtest_min_confidence_short)
                logger.debug(
                    "🔧 [BACKTEST] Используем переопределенный min_confidence_for_short: %.3f",
                    min_confidence_for_short,
                )
            else:
                # Оптимизировано на основе бэктеста (3 месяца, топ-20 монет, 15 потоков)
                # Результаты: Win Rate 68.81%, Profit Factor 1.29, Total Return +0.52%, Max Drawdown 0.37%
                # См. docs/FILTER_PARAMETERS_OPTIMIZATION_RESULTS.md
                min_confidence_for_short = 0.40

            if (
                quality_score < min_quality_for_short
                or pattern_confidence < min_confidence_for_short
            ):
                logger.debug("🚫 %s: SHORT Alt-1 не прошел проверку качества", symbol)
                return None, None, None

            logger.debug(
                "✅ %s: SHORT Quality %.2f, Confidence %.2f",
                symbol,
                quality_score,
                pattern_confidence,
            )

            # 🔥 MTF CONFIRMATION (H4 таймфрейм)
            mtf_ok, _ = await _run_mtf_confirmation_with_logging(symbol, signal_type, regime_data)
            if not mtf_ok:
                return None, None, None

            # AI-регулятор
            _call_ai_regulator(
                symbol, pattern_type, signal_type, signal_price, df, 0.0, regime_data, None
            )

            # 🔧 ИСПРАВЛЕНО: Рассчитываем TP перед ML фильтром (Дмитрий - после аудита)
            trade_mode = user_data.get("trade_mode", "spot")
            tp1_price, tp2_price = calculate_tp_prices_for_ml(
                signal_price, df, signal_type, trade_mode
            )

            # 🆕 ML ФИЛЬТР: Проверка через LightGBM
            ml_passed, ml_reason, _ml_prediction = await check_ml_filter(
                symbol=symbol,
                signal_type=signal_type,
                entry_price=signal_price,
                df=df,
                quality_score=quality_score,
                mtf_score=0.5,  # Можно получить из MTF конфирмера
                tp1=tp1_price,  # 🔧 ИСПРАВЛЕНО: Рассчитан перед вызовом
                tp2=tp2_price,  # 🔧 ИСПРАВЛЕНО: Рассчитан перед вызовом
                risk_pct=user_data.get("risk_pct", 2.0),
                leverage=user_data.get("leverage", 1.0),
                regime_data=regime_data,
            )

            if not ml_passed:
                logger.warning(
                    "🚫 [ML BLOCK] %s SHORT Alt-1: ML фильтр заблокировал сигнал: %s",
                    symbol,
                    ml_reason,
                )
                pipeline_monitor.log_stage("ml_filter", symbol, False, ml_reason)
                return None, None, None

            # Логируем детали предсказания если доступны
            if _ml_prediction:
                logger.debug(
                    "📊 [ML DETAILS] %s: prob=%.2f%%, profit=%.2f%%, score=%.3f",
                    symbol,
                    _ml_prediction.get("success_probability", 0) * 100,
                    _ml_prediction.get("expected_profit_pct", 0),
                    _ml_prediction.get("combined_score", 0),
                )

            logger.info("✅ [ML PASS] %s SHORT Alt-1: ML фильтр пройден: %s", symbol, ml_reason)
            pipeline_monitor.log_stage("ml_filter", symbol, True, ml_reason)

            pipeline_monitor.log_stage("final_signal", symbol, True, "SHORT сигнал сгенерирован")
            return signal_type, signal_price, _ml_prediction

        # Альтернативный SHORT паттерн 2: Цена ниже EMA + нисходящий тренд + RSI не перепродан (только FUTURES)
        elif (
            current_price < ema_fast  # Цена ниже быстрой EMA
            and ema_fast < float(ema_fast_series.iloc[-2])  # Нисходящий тренд EMA
            and "rsi" in df.columns
            and df["rsi"].iloc[-1] > 30
        ):  # RSI не перепродан
            # 🔍 ЛОГИРОВАНИЕ ДО ПРОВЕРКИ РЕЖИМА
            logger.info(
                "🔍 [SHORT Alt-2] %s: Обнаружен альтернативный паттерн 2 (цена=%.8f, ema_fast=%.8f, RSI=%.2f, режим=%s)",
                symbol,
                current_price,
                ema_fast,
                df["rsi"].iloc[-1] if "rsi" in df.columns else 0,
                trade_mode,
            )
            pipeline_monitor.log_stage(
                "ema_pattern", symbol, True, f"SHORT Альтернативный паттерн 2 (режим: {trade_mode})"
            )

            # Проверяем режим торговли - SHORT только для FUTURES
            if trade_mode != "futures":
                logger.warning(
                    "🚫 [SHORT Alt-2 BLOCK] %s: SHORT сигнал пропущен (режим: %s, требуется: futures)",
                    symbol,
                    trade_mode,
                )
                pipeline_monitor.log_stage(
                    "trade_mode_check", symbol, False, f"Режим {trade_mode} не позволяет SHORT"
                )
                return None, None, None

            logger.info(
                "✅ [SHORT Alt-2] %s: Режим проверен (futures), продолжаем генерацию сигнала",
                symbol,
            )
            signal_type = "SELL"
            signal_price = current_price
            pattern_type = "alternative_short_2"
            logger.debug("✅ %s: SHORT Альтернативный паттерн 2 (цена < EMA + тренд + RSI)", symbol)
            pipeline_monitor.log_stage(
                "ema_pattern", symbol, True, "SHORT Альтернативный паттерн 2"
            )
            pipeline_monitor.log_pattern_type("short_alternative_2")

            # 🔥 КРИТИЧЕСКИЕ ПРОВЕРКИ НАПРАВЛЕНИЯ СИГНАЛА
            logger.debug("🔍 [SHORT Alt-2] %s: Проверка трендов (умная логика)...", symbol)
            if not await check_all_trend_alignments(symbol, signal_type, df):
                logger.warning("🚫 [SHORT Alt-2] %s: Тренд alignment не пройден", symbol)
                return None, None, None
            logger.debug("✅ [SHORT Alt-2] %s: BTC alignment пройден", symbol)

            # 🆕 ПРОВЕРКА НОВЫХ ФИЛЬТРОВ
            new_filters_passed, new_filters_reason = await check_new_filters(
                symbol, signal_type, signal_price, df, strict_mode=filter_mode == "strict"
            )
            if not new_filters_passed:
                logger.warning(
                    "🚫 [SHORT Alt-2] %s: Новые фильтры заблокировали: %s",
                    symbol,
                    new_filters_reason,
                )
                return None, None, None

            # 🔧 ВРЕМЕННО ОТКЛЮЧЕН ДЛЯ СООТВЕТСТВИЯ УСПЕШНОМУ БЭКТЕСТУ
            # logger.debug("🔍 [SHORT Alt-2] %s: Проверка direction confidence...", symbol)
            # if not calculate_direction_confidence(
            #     df,
            #     signal_type,
            #     trade_mode,
            #     user_data.get("filter_mode", "soft"),
            # ):
            #     logger.warning("🚫 [SHORT Alt-2] %s: Direction confidence не пройден (недостаточно подтверждений)", symbol)
            #     return None, None, None
            # logger.debug("✅ [SHORT Alt-2] %s: Direction confidence пройден", symbol)
            logger.debug(
                "⏭️ [SHORT Alt-2] %s: Direction confidence временно отключен (как в успешном бэктесте)",
                symbol,
            )

            logger.debug("🔍 [SHORT Alt-2] %s: Проверка RSI warning...", symbol)
            if not await check_rsi_warning(df, signal_type):
                logger.warning(
                    "🚫 [SHORT Alt-2] %s: RSI warning не пройден (RSI в опасной зоне)", symbol
                )
                return None, None, None
            logger.debug("✅ [SHORT Alt-2] %s: RSI warning пройден", symbol)

            # Проверка качества (усиленные требования для SHORT)
            quality_score = quality_validator.calculate_quality_score(df, signal_type, symbol)
            pattern_confidence = pattern_scorer.calculate_pattern_confidence(
                pattern_type, df, signal_type
            )

            # 🔧 ПОДДЕРЖКА БЭКТЕСТОВ: Переопределение через environment variables
            backtest_min_quality_short = os.getenv("BACKTEST_min_quality_for_short")
            if backtest_min_quality_short is not None:
                min_quality_for_short = float(backtest_min_quality_short)
                logger.debug(
                    "🔧 [BACKTEST] Используем переопределенный min_quality_for_short: %.3f",
                    min_quality_for_short,
                )
            else:
                # Оптимизировано на основе бэктеста (3 месяца, топ-20 монет, 15 потоков)
                # Результаты: Win Rate 68.81%, Profit Factor 1.29, Total Return +0.52%, Max Drawdown 0.37%
                # См. docs/FILTER_PARAMETERS_OPTIMIZATION_RESULTS.md
                min_quality_for_short = 0.45

            backtest_min_confidence_short = os.getenv("BACKTEST_min_confidence_for_short")
            if backtest_min_confidence_short is not None:
                min_confidence_for_short = float(backtest_min_confidence_short)
                logger.debug(
                    "🔧 [BACKTEST] Используем переопределенный min_confidence_for_short: %.3f",
                    min_confidence_for_short,
                )
            else:
                # Оптимизировано на основе бэктеста (3 месяца, топ-20 монет, 15 потоков)
                # Результаты: Win Rate 68.81%, Profit Factor 1.29, Total Return +0.52%, Max Drawdown 0.37%
                # См. docs/FILTER_PARAMETERS_OPTIMIZATION_RESULTS.md
                min_confidence_for_short = 0.40

            logger.info(
                "📊 [QUALITY CHECK] %s SHORT Alt-2: Quality=%.3f (min=%.2f), Confidence=%.3f (min=%.2f)",
                symbol,
                quality_score,
                min_quality_for_short,
                pattern_confidence,
                min_confidence_for_short,
            )

            if quality_score < min_quality_for_short:
                logger.warning(
                    "🚫 [QUALITY BLOCK] %s SHORT Alt-2: Quality score %.3f < %.2f",
                    symbol,
                    quality_score,
                    min_quality_for_short,
                )
                pipeline_monitor.log_stage(
                    "quality_check",
                    symbol,
                    False,
                    f"Quality {quality_score:.3f} < {min_quality_for_short}",
                )
                return None, None, None

            if pattern_confidence < min_confidence_for_short:
                logger.warning(
                    "🚫 [CONFIDENCE BLOCK] %s SHORT Alt-2: Pattern confidence %.3f < %.2f",
                    symbol,
                    pattern_confidence,
                    min_confidence_for_short,
                )
                pipeline_monitor.log_stage(
                    "confidence_check",
                    symbol,
                    False,
                    f"Confidence {pattern_confidence:.3f} < {min_confidence_for_short}",
                )
                return None, None, None

            logger.info(
                "✅ [QUALITY PASS] %s SHORT Alt-2: Quality %.3f >= %.2f, Confidence %.3f >= %.2f",
                symbol,
                quality_score,
                min_quality_for_short,
                pattern_confidence,
                min_confidence_for_short,
            )

            # Дополнительные защитные проверки для SHORT
            if DEFENSE_SYSTEMS_AVAILABLE and volume_detector:
                try:
                    volume_quality = volume_detector.get_volume_quality(df)
                    logger.info(
                        "📊 [VOLUME QUALITY] %s SHORT: Volume quality=%.3f (min=0.80)",
                        symbol,
                        volume_quality,
                    )
                    if volume_quality < 0.80:
                        logger.warning(
                            "🚫 [VOLUME BLOCK] %s SHORT: Volume quality %.3f < 0.80",
                            symbol,
                            volume_quality,
                        )
                        pipeline_monitor.log_stage(
                            "volume_quality",
                            symbol,
                            False,
                            f"Volume quality {volume_quality:.3f} < 0.80",
                        )
                        return None, None, None
                    logger.info(
                        "✅ [VOLUME PASS] %s SHORT: Volume quality %.3f >= 0.80",
                        symbol,
                        volume_quality,
                    )
                except Exception as e:
                    logger.debug("⚠️ Ошибка проверки объема для %s: %s (пропускаем)", symbol, e)

            # 🔥 MTF CONFIRMATION (H4 таймфрейм) - ДОБАВЛЕНО для SHORT Alt-2
            mtf_ok, _ = await _run_mtf_confirmation_with_logging(symbol, signal_type, regime_data)
            if not mtf_ok:
                return None, None, None

            # AI-регулятор
            logger.info("📊 [AI REGULATOR] %s SHORT: Вызов AI регулятора...", symbol)
            _call_ai_regulator(
                symbol, pattern_type, signal_type, signal_price, df, 0.0, regime_data, None
            )

            # 🆕 ML ФИЛЬТР: Проверка через LightGBM
            ml_passed, ml_reason, _ml_prediction = await check_ml_filter(
                symbol=symbol,
                signal_type=signal_type,
                entry_price=signal_price,
                df=df,
                quality_score=quality_score,
                mtf_score=0.5,  # Можно получить из MTF конфирмера
                tp1=None,  # Будет рассчитан позже
                tp2=None,  # Будет рассчитан позже
                risk_pct=user_data.get("risk_pct", 2.0),
                leverage=user_data.get("leverage", 1.0),
                regime_data=regime_data,
            )

            if not ml_passed:
                logger.warning(
                    "🚫 [ML BLOCK] %s SHORT Alt-2: ML фильтр заблокировал сигнал: %s",
                    symbol,
                    ml_reason,
                )
                pipeline_monitor.log_stage("ml_filter", symbol, False, ml_reason)
                return None, None, None

            # Логируем детали предсказания если доступны
            if _ml_prediction:
                logger.debug(
                    "📊 [ML DETAILS] %s: prob=%.2f%%, profit=%.2f%%, score=%.3f",
                    symbol,
                    _ml_prediction.get("success_probability", 0) * 100,
                    _ml_prediction.get("expected_profit_pct", 0),
                    _ml_prediction.get("combined_score", 0),
                )

            logger.info("✅ [ML PASS] %s SHORT Alt-2: ML фильтр пройден: %s", symbol, ml_reason)
            pipeline_monitor.log_stage("ml_filter", symbol, True, ml_reason)

            logger.info(
                "✅ [SIGNAL GENERATED] %s SHORT Alt-2: Сигнал успешно сгенерирован! Quality=%.3f, Confidence=%.3f",
                symbol,
                quality_score,
                pattern_confidence,
            )
            pipeline_monitor.log_stage("final_signal", symbol, True, "SHORT сигнал сгенерирован")
            return signal_type, signal_price, _ml_prediction

        # Альтернативный SHORT паттерн 3: Отскок от сопротивления + объем (только FUTURES)
        elif (
            current_price < df["high"].iloc[-1] * 0.999  # Отскок от максимума (вниз)
            and current_volume > avg_volume * 1.5  # Высокий объем
            and "bb_upper" in df.columns
            and current_price < df["bb_upper"].iloc[-1]
        ):  # Ниже верхней BB
            # 🔍 ЛОГИРОВАНИЕ ДО ПРОВЕРКИ РЕЖИМА
            logger.info(
                "🔍 [SHORT Alt-3] %s: Обнаружен альтернативный паттерн 3 (режим=%s)",
                symbol,
                trade_mode,
            )
            pipeline_monitor.log_stage(
                "ema_pattern", symbol, True, f"SHORT Альтернативный паттерн 3 (режим: {trade_mode})"
            )

            # Проверяем режим торговли - SHORT только для FUTURES
            if trade_mode != "futures":
                logger.warning(
                    "🚫 [SHORT Alt-3 BLOCK] %s: SHORT сигнал пропущен (режим: %s, требуется: futures)",
                    symbol,
                    trade_mode,
                )
                pipeline_monitor.log_stage(
                    "trade_mode_check", symbol, False, f"Режим {trade_mode} не позволяет SHORT"
                )
                return None, None, None

            logger.info(
                "✅ [SHORT Alt-3] %s: Режим проверен (futures), продолжаем генерацию сигнала",
                symbol,
            )
            signal_type = "SELL"
            signal_price = current_price
            pattern_type = "alternative_short_3"
            logger.debug(
                "✅ %s: SHORT Альтернативный паттерн 3 (отскок от сопротивления + объем + BB)",
                symbol,
            )
            pipeline_monitor.log_stage(
                "ema_pattern", symbol, True, "SHORT Альтернативный паттерн 3"
            )
            pipeline_monitor.log_pattern_type("short_alternative_3")

            # 🔥 КРИТИЧЕСКИЕ ПРОВЕРКИ НАПРАВЛЕНИЯ СИГНАЛА
            if not await check_all_trend_alignments(symbol, signal_type, df):
                return None, None, None
            # 🆕 ПРОВЕРКА НОВЫХ ФИЛЬТРОВ
            new_filters_passed, new_filters_reason = await check_new_filters(
                symbol, signal_type, signal_price, df, strict_mode=filter_mode == "strict"
            )
            if not new_filters_passed:
                logger.warning(
                    "🚫 [ALT-2] %s: Новые фильтры заблокировали: %s", symbol, new_filters_reason
                )
                return None, None, None
            # 🔧 ВРЕМЕННО ОТКЛЮЧЕН ДЛЯ СООТВЕТСТВИЯ УСПЕШНОМУ БЭКТЕСТУ
            # if not calculate_direction_confidence(
            #     df,
            #     signal_type,
            #     trade_mode,
            #     user_data.get("filter_mode", "soft"),
            # ):
            #     return None, None, None
            if not await check_rsi_warning(df, signal_type):
                return None, None, None

            # Проверка качества (усиленные требования для SHORT)
            quality_score = quality_validator.calculate_quality_score(df, signal_type, symbol)
            pattern_confidence = pattern_scorer.calculate_pattern_confidence(
                pattern_type, df, signal_type
            )

            # 🔧 ПОДДЕРЖКА БЭКТЕСТОВ: Переопределение через environment variables
            backtest_min_quality_short = os.getenv("BACKTEST_min_quality_for_short")
            if backtest_min_quality_short is not None:
                min_quality_for_short = float(backtest_min_quality_short)
                logger.debug(
                    "🔧 [BACKTEST] Используем переопределенный min_quality_for_short: %.3f",
                    min_quality_for_short,
                )
            else:
                # Оптимизировано на основе бэктеста (3 месяца, топ-20 монет, 15 потоков)
                # Результаты: Win Rate 68.81%, Profit Factor 1.29, Total Return +0.52%, Max Drawdown 0.37%
                # См. docs/FILTER_PARAMETERS_OPTIMIZATION_RESULTS.md
                min_quality_for_short = 0.45

            backtest_min_confidence_short = os.getenv("BACKTEST_min_confidence_for_short")
            if backtest_min_confidence_short is not None:
                min_confidence_for_short = float(backtest_min_confidence_short)
                logger.debug(
                    "🔧 [BACKTEST] Используем переопределенный min_confidence_for_short: %.3f",
                    min_confidence_for_short,
                )
            else:
                # Оптимизировано на основе бэктеста (3 месяца, топ-20 монет, 15 потоков)
                # Результаты: Win Rate 68.81%, Profit Factor 1.29, Total Return +0.52%, Max Drawdown 0.37%
                # См. docs/FILTER_PARAMETERS_OPTIMIZATION_RESULTS.md
                min_confidence_for_short = 0.40

            if (
                quality_score < min_quality_for_short
                or pattern_confidence < min_confidence_for_short
            ):
                logger.debug("🚫 %s: SHORT Alt-3 не прошел проверку качества", symbol)
                return None, None, None

            logger.debug(
                "✅ %s: SHORT Quality %.2f, Confidence %.2f",
                symbol,
                quality_score,
                pattern_confidence,
            )

            # УСИЛЕННАЯ проверка объема для SHORT (85% vs 80% для LONG)
            if DEFENSE_SYSTEMS_AVAILABLE and volume_detector:
                try:
                    volume_quality = volume_detector.get_volume_quality(df)
                    if volume_quality < 0.85:
                        return None, None, None
                except Exception as e:
                    logger.debug("Ошибка проверки объема: %s", e)

            # 🔥 MTF CONFIRMATION (H4 таймфрейм)
            mtf_ok, _ = await _run_mtf_confirmation_with_logging(symbol, signal_type, regime_data)
            if not mtf_ok:
                return None, None, None

            # AI-регулятор
            _call_ai_regulator(
                symbol, pattern_type, signal_type, signal_price, df, 0.0, regime_data, None
            )

            # 🔧 ИСПРАВЛЕНО: Рассчитываем TP перед ML фильтром (Дмитрий - после аудита)
            trade_mode = user_data.get("trade_mode", "spot")
            tp1_price, tp2_price = calculate_tp_prices_for_ml(
                signal_price, df, signal_type, trade_mode
            )

            # 🆕 ML ФИЛЬТР: Проверка через LightGBM
            ml_passed, ml_reason, _ml_prediction = await check_ml_filter(
                symbol=symbol,
                signal_type=signal_type,
                entry_price=signal_price,
                df=df,
                quality_score=quality_score,
                mtf_score=0.5,  # Можно получить из MTF конфирмера
                tp1=tp1_price,  # 🔧 ИСПРАВЛЕНО: Рассчитан перед вызовом
                tp2=tp2_price,  # 🔧 ИСПРАВЛЕНО: Рассчитан перед вызовом
                risk_pct=user_data.get("risk_pct", 2.0),
                leverage=user_data.get("leverage", 1.0),
                regime_data=regime_data,
            )

            if not ml_passed:
                logger.warning(
                    "🚫 [ML BLOCK] %s SHORT Alt-3: ML фильтр заблокировал сигнал: %s",
                    symbol,
                    ml_reason,
                )
                pipeline_monitor.log_stage("ml_filter", symbol, False, ml_reason)
                return None, None, None

            # Логируем детали предсказания если доступны
            if _ml_prediction:
                logger.debug(
                    "📊 [ML DETAILS] %s: prob=%.2f%%, profit=%.2f%%, score=%.3f",
                    symbol,
                    _ml_prediction.get("success_probability", 0) * 100,
                    _ml_prediction.get("expected_profit_pct", 0),
                    _ml_prediction.get("combined_score", 0),
                )

            logger.info("✅ [ML PASS] %s SHORT Alt-3: ML фильтр пройден: %s", symbol, ml_reason)
            pipeline_monitor.log_stage("ml_filter", symbol, True, ml_reason)

            pipeline_monitor.log_stage("final_signal", symbol, True, "SHORT сигнал сгенерирован")
            return signal_type, signal_price, _ml_prediction

        else:
            logger.debug("🚫 %s: Ни один паттерн не подходит", symbol)
            pipeline_monitor.log_stage("ema_pattern", symbol, False, "Ни один паттерн не подходит")
            return None, None, None

    except Exception as e:
        logger.error("Ошибка генерации сигнала для %s: %s", symbol, e)
        return None, None, None


async def send_signal(
    symbol: str,
    signal_type: str,
    signal_price: float,
    user_data: Dict[str, Any],
    signal_history: List[Dict[str, Any]],
    df: Any = None,
    regime_data: Dict[str, Any] = None,
    regime_multipliers: Dict[str, float] = None,
    composite_result: Dict[str, Any] = None,
    quality_score: float = 0.7,
    pattern_confidence: float = 0.6,
    ml_prediction: Dict[str, Any] = None,
) -> bool:
    """PRODUCTION версия отправки сигнала с полной интеграцией корреляционных рисков"""

    logger.info(
        "📨 [SEND_SIGNAL START] %s %s @ %.8f для пользователя %s (mode=%s)",
        symbol,
        signal_type,
        signal_price,
        user_data.get("user_id"),
        user_data.get("trade_mode", "unknown"),
    )

    # 🔧 Проверка доступности tracer (ИСПРАВЛЕНО: удален проблемный tracer.start)
    class DummyTrace:
        """Заглушка для трейсера."""

        def record(self, *args, **kwargs):
            """Заглушка для записи шага."""

        def finish(self, *args, **kwargs):
            """Заглушка для завершения трейса."""

    trace = DummyTrace()

    # 🆕 Загрузка системного промпта агента с умным выбором контекста
    if get_prompt_manager:
        prompt_manager = get_prompt_manager()
        agent_prompt = prompt_manager.load_prompt("signal_live") if prompt_manager else None
    else:
        agent_prompt = None
    if agent_prompt:
        # Базовый контекст
        base_context = {
            "symbol": symbol,
            "signal_type": signal_type,
            "signal_price": signal_price,
            "user_id": user_data.get("user_id"),
            "trade_mode": user_data.get("trade_mode"),
            "quality_score": quality_score,
            "pattern_confidence": pattern_confidence,
        }

        # 🧠 Используем ContextEngine для умного выбора контекста
        enriched_context = {}
        if get_context_engine is not None:
            try:
                context_engine = get_context_engine()
                if context_engine is not None:
                    enriched_context = context_engine.select_context(
                        agent="signal_live",
                        mission=f"{symbol}:{signal_type}",
                        history=None,  # Можно добавить историю из trace
                    )
            except (AttributeError, TypeError, Exception) as e:
                logger.debug(
                    "⚠️ ContextEngine недоступен: %s (продолжаем без обогащенного контекста)", e
                )
                enriched_context = {}
        # Объединяем базовый и обогащенный контекст
        final_context = {**base_context, **enriched_context}

        full_prompt = agent_prompt.get_full_prompt(final_context, use_context_engine=True)
        if trace is not None:
            trace.record(
                step="think",
                name="prompt_loaded",
                metadata={
                    "version": agent_prompt.version,
                    "prompt_length": len(full_prompt),
                    "context_keys": list(final_context.keys()),
                },
            )
        logger.debug(
            "📝 [PROMPT] signal_live v%s загружен (%d символов, контекст: %s)",
            agent_prompt.version,
            len(full_prompt),
            ", ".join(final_context.keys()),
        )

    if authorize_agent_action is not None:
        authorize_agent_action(
            agent="signal_live",
            permission="telegram:send",
            context={
                "user_id": user_data.get("user_id"),
                "symbol": symbol,
                "mode": user_data.get("trade_mode"),
            },
        )

    guidance_entries = get_guidance("signal_live", limit=3)
    guidance_summary: Optional[List[Dict[str, Any]]] = None
    if guidance_entries:
        guidance_summary = [
            {"issue": entry.issue, "recommendation": entry.recommendation, "count": entry.count}
            for entry in guidance_entries
        ]
        if trace is not None:
            trace.record(
                step="think",
                name="guidance_loaded",
                metadata={"entries": guidance_summary},
            )
        logger.debug(
            "📘 [GUIDANCE] signal_live lessons: %s",
            "; ".join(f"{item['issue']} (#{item['count']})" for item in guidance_summary),
        )
    lm_judge = get_lm_judge()
    judge_verdict = None

    # 🆕 ИНИЦИАЛИЗАЦИЯ ПЕРЕМЕННЫХ ДЛЯ АВТОИСПОЛНЕНИЯ (должны быть доступны в конце функции)
    entry_amount_usdt = None
    leverage = None
    trade_mode = None
    sl_price = None
    tp1_price = None
    tp2_price = None
    signal_sent_successfully = False  # 🆕 Флаг успешной отправки сигнала (инициализируем в начале)

    # 🆕 0. ОПТИМИЗАЦИЯ TIMING ВХОДА
    entry_timing_result = None
    if ENTRY_TIMING_OPTIMIZER_AVAILABLE and entry_timing_optimizer and df is not None:
        try:
            entry_timing_result = await entry_timing_optimizer.get_optimal_entry_strategy(
                df=df,
                signal_type=signal_type,
                current_price=signal_price,
                market_regime=regime_data.get("regime", "NEUTRAL") if regime_data else "NEUTRAL",
                composite_confidence=composite_result.get("confidence", 0.5)
                if composite_result
                else 0.5,
            )

            # Обновляем цену входа если стратегия рекомендует
            if entry_timing_result["strategy"] == "retracement":
                logger.info(
                    "📍 [ENTRY TIMING] %s: рекомендован откат до %.8f (было: %.8f)",
                    symbol,
                    entry_timing_result["entry_price"],
                    signal_price,
                )
                # Используем рекомендованную цену (откат 0.3%)
                signal_price = entry_timing_result["entry_price"]
            elif entry_timing_result["strategy"] == "breakout_confirmation":
                logger.info(
                    "📍 [ENTRY TIMING] %s: рекомендовано ждать подтверждения (%d мин)",
                    symbol,
                    entry_timing_result["wait_minutes"],
                )
                # Для подтверждения используем текущую цену

        except Exception as e:
            logger.debug("⚠️ Ошибка entry timing optimizer: %s (используем текущую цену)", e)

    # 1. Быстрая проверка доступности менеджера
    if CORRELATION_MANAGER_AVAILABLE and correlation_manager is None:
        logger.warning("⚠️ CorrelationManager недоступен, пропускаем проверку рисков")
        # Продолжаем стандартную отправку

    try:
        # 2. ПРОВЕРКА КОРРЕЛЯЦИОННЫХ РИСКОВ
        # ✅ РЕ-АКТИВИРОВАНО: Correlation Risk включен после исправления лимитов
        USE_CORRELATION_RISK = True

        if USE_CORRELATION_RISK and CORRELATION_MANAGER_AVAILABLE and correlation_manager:
            try:
                risk_check = await correlation_manager.check_correlation_risk_async(
                    symbol=symbol,
                    signal_type=signal_type,
                    user_id=user_data.get("user_id"),
                    df=df,  # Передаем данные для расчета корреляции
                )

                if not risk_check["allowed"]:
                    logger.warning(
                        "🚫 [SEND_SIGNAL BLOCK] %s %s: Корреляционный риск заблокирован - %s",
                        symbol,
                        signal_type,
                        risk_check["reason"],
                    )
                    if trace is not None:
                        trace.record(
                            step="observe",
                            name="correlation_block",
                            status="error",
                            metadata={"reason": risk_check.get("reason")},
                        )

                    # Детальное логирование для отладки
                    if "details" in risk_check:
                        logger.info("   📋 Детали: %s", risk_check["details"])
                    if "active_signals" in risk_check and risk_check["active_signals"]:
                        # 🔧 ИСПРАВЛЕНО: Убираем дубликаты в логах (по символу)
                        seen_symbols = set()
                        unique_signals = []
                        for s in risk_check["active_signals"]:
                            symbol_key = s["symbol"]
                            if symbol_key not in seen_symbols:
                                unique_signals.append(s)
                                seen_symbols.add(symbol_key)

                        active_list = [
                            f"{s['symbol']} ({s.get('sector', 'N/A')})" for s in unique_signals
                        ]
                        logger.info("   📊 Активные сигналы: %s", ", ".join(active_list))

                    if trace is not None:
                        trace.finish(status="error", metadata={"reason": "correlation_block"})
                    return False
                else:
                    logger.debug(
                        "✅ [CORRELATION] %s %s разрешен: %s",
                        symbol,
                        signal_type,
                        risk_check.get("details", "OK"),
                    )
                    if trace is not None:
                        trace.record(
                            step="observe",
                            name="correlation_pass",
                            metadata={"details": risk_check.get("details")},
                        )
            except Exception as e:
                logger.error("❌ Ошибка проверки корреляции для %s: %s", symbol, e)
                # Продолжаем работу в случае ошибки (fallback)

        # Проверяем, не отправляли ли уже сигнал
        signal_was_sent_earlier = is_signal_already_sent(
            symbol, user_data.get("user_id"), signal_history
        )
        if signal_was_sent_earlier:
            logger.warning(
                "🚫 [SEND_SIGNAL BLOCK] %s %s: Сигнал уже был отправлен ранее", symbol, signal_type
            )
            # 🔧 ИСПРАВЛЕНО: Если сигнал уже был отправлен ранее, это означает успешную отправку
            # Устанавливаем signal_sent_successfully = True для автоисполнения
            signal_sent_successfully = True
            logger.info(
                "✅ [SEND_SIGNAL] %s %s: Сигнал уже был отправлен ранее - считаем успешной отправкой для автоисполнения",
                symbol,
                signal_type,
            )
            if trace is not None:
                trace.record(
                    step="observe",
                    name="duplicate_signal",
                    status="success",  # Изменено с "error" на "success" - сигнал уже был отправлен
                    metadata={"reason": "already_sent", "signal_sent": True},
                )
                trace.finish(status="success", metadata={"reason": "duplicate_but_sent"})
            # 🔧 ВАЖНО: НЕ возвращаемся раньше! Продолжаем выполнение, чтобы автоисполнение могло проверить signal_sent_successfully
            # Просто пропускаем отправку в Telegram, но продолжаем до блока автоисполнения
            # Устанавливаем message_id_result = None, так как новый сигнал не отправлялся
            message_id_result = None
            # Продолжаем выполнение функции до блока автоисполнения

        # Генерируем уникальный trace ID для отслеживания
        trace_id = str(uuid.uuid4())[:8]

        # Формируем сигнал
        signal_data = {
            "symbol": symbol,
            "signal_type": signal_type,
            "entry_price": signal_price,
            "current_price": signal_price,
            "user_id": user_data.get("user_id"),
            "timestamp": time.time(),
            "trace_id": trace_id,
            "status": "GENERATED",
        }

        logger.info(
            "🔍 [%s] Сигнал сгенерирован: %s %s %.4f", trace_id, symbol, signal_type, signal_price
        )

        # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Реальная отправка в Telegram
        # 🆕 Переменные entry_amount_usdt, leverage, trade_mode, sl_price, tp1_price, tp2_price
        # определены в начале функции и будут доступны через замыкание
        if TELEGRAM_INTEGRATION_AVAILABLE:
            try:
                # Получаем информацию о символе для форматирования
                symbol_info = await get_symbol_info(symbol)
                price_precision = symbol_info.get("price_precision", 3)
                fmt = f"{{:.{price_precision}f}}"

                def price_formatter(price):
                    return fmt.format(price)

                # Рассчитываем TP и SL
                try:
                    # Получаем данные для расчета TP/SL
                    df_for_tp = await get_symbol_data(symbol)
                    if df_for_tp is not None and len(df_for_tp) > 0:
                        # 🤖 ИИ-ОПТИМИЗИРОВАННЫЕ TP УРОВНИ НА ОСНОВЕ НАКОПЛЕННЫХ ПАТТЕРНОВ
                        current_index = len(df_for_tp) - 1

                        if AI_TP_OPTIMIZER_AVAILABLE and AI_TP_OPTIMIZER:
                            try:
                                tp1_pct, tp2_pct = AI_TP_OPTIMIZER.calculate_ai_optimized_tp(
                                    symbol=symbol,
                                    side=signal_type.upper(),
                                    df=df_for_tp,
                                    current_index=current_index,
                                    base_tp1=2.0,
                                    base_tp2=4.0,
                                )
                                logger.info(
                                    "🤖 [%s] ИИ-оптимизированные TP: %.2f%%, %.2f%% (на основе %d+ паттернов)",
                                    symbol,
                                    tp1_pct,
                                    tp2_pct,
                                    30000,
                                )
                            except Exception as e:
                                logger.warning(
                                    "⚠️ [%s] ИИ-оптимизация TP недоступна: %s, используем динамические",
                                    symbol,
                                    e,
                                )
                                tp1_pct, tp2_pct = get_dynamic_tp_levels(
                                    df_for_tp,
                                    current_index,
                                    signal_type.lower(),
                                    trade_mode=user_data.get("trade_mode", "spot"),
                                    adjust_for_fees=True,
                                )
                        else:
                            # Fallback к динамическим TP
                            trade_mode = user_data.get("trade_mode", "spot")
                            tp1_pct, tp2_pct = get_dynamic_tp_levels(
                                df_for_tp,
                                current_index,
                                signal_type.lower(),
                                trade_mode=trade_mode,
                                adjust_for_fees=True,
                            )

                        # 🛡️ ДИНАМИЧЕСКИЙ СТОП-ЛОСС С AI-ОПТИМИЗАЦИЕЙ
                        if AI_SL_OPTIMIZER_AVAILABLE and AI_SL_OPTIMIZER:
                            try:
                                sl_pct_positive = AI_SL_OPTIMIZER.calculate_ai_optimized_sl(
                                    symbol=symbol,
                                    side=signal_type.upper(),
                                    df=df_for_tp,
                                    current_index=current_index,
                                    base_sl=2.0,
                                )
                                logger.info(
                                    "🤖 [%s] ИИ-оптимизированный SL: %.2f%% (на основе паттернов)",
                                    symbol,
                                    sl_pct_positive,
                                )
                            except Exception as e:
                                logger.warning(
                                    "⚠️ [%s] ИИ-оптимизация SL недоступна: %s, используем динамический",
                                    symbol,
                                    e,
                                )
                                try:
                                    sl_pct_positive = get_dynamic_sl_level(
                                        df_for_tp,
                                        current_index,
                                        signal_type.lower(),
                                        base_sl_pct=2.0,
                                        symbol=symbol,
                                        use_ai_optimization=False,
                                    )
                                except Exception as e2:
                                    logger.warning(
                                        "⚠️ [%s] Динамический SL также недоступен: %s, используем 2%%",
                                        symbol,
                                        e2,
                                    )
                                    sl_pct_positive = 2.0
                        else:
                            # Fallback к динамическому SL
                            try:
                                sl_pct_positive = get_dynamic_sl_level(
                                    df_for_tp,
                                    current_index,
                                    signal_type.lower(),
                                    base_sl_pct=2.0,
                                    symbol=symbol,
                                    use_ai_optimization=False,
                                )
                                logger.info(
                                    "🛡️ [%s] Динамический SL: %.2f%%", symbol, sl_pct_positive
                                )
                            except Exception as e:
                                logger.warning(
                                    "⚠️ [%s] Ошибка расчета динамического SL: %s, используем 2%%",
                                    symbol,
                                    e,
                                )
                                sl_pct_positive = 2.0

                        # 🆕 ДИНАМИЧЕСКИЕ TP/SL ОТ ЗОН (если включено)
                        from config import USE_DYNAMIC_TP_SL_FROM_ZONES

                        if USE_DYNAMIC_TP_SL_FROM_ZONES and NEW_FILTERS_AVAILABLE:
                            try:
                                from src.signals.zone_based_tp_sl import get_zone_tp_sl_calculator

                                zone_calculator = get_zone_tp_sl_calculator()

                                # Пробуем использовать Фибоначчи
                                if fibonacci_calculator:
                                    tp1_pct_zone, tp2_pct_zone, sl_pct_zone, zone_details = (
                                        zone_calculator.calculate_tp_sl_from_fibonacci(
                                            entry_price=signal_price,
                                            direction=signal_type.upper(),
                                            df=df_for_tp,
                                            base_tp1_pct=tp1_pct,
                                            base_tp2_pct=tp2_pct,
                                            base_sl_pct=sl_pct_positive,
                                        )
                                    )

                                    if zone_details.get("method") == "fibonacci":
                                        tp1_pct = tp1_pct_zone
                                        tp2_pct = tp2_pct_zone
                                        sl_pct_positive = sl_pct_zone
                                        logger.info(
                                            "🎯 [%s] TP/SL от Фибоначчи: TP1=%.2f%%, TP2=%.2f%%, SL=%.2f%%",
                                            symbol,
                                            tp1_pct,
                                            tp2_pct,
                                            sl_pct_positive,
                                        )

                                # Пробуем использовать Interest Zones
                                if interest_zone_filter:
                                    try:
                                        zones = interest_zone_filter.get_zones(
                                            df_for_tp, signal_price
                                        )
                                        if zones:
                                            (
                                                tp1_pct_zone,
                                                tp2_pct_zone,
                                                sl_pct_zone,
                                                zone_details,
                                            ) = zone_calculator.calculate_tp_sl_from_interest_zones(
                                                entry_price=signal_price,
                                                direction=signal_type.upper(),
                                                zones=zones,
                                                base_tp1_pct=tp1_pct,
                                                base_tp2_pct=tp2_pct,
                                                base_sl_pct=sl_pct_positive,
                                            )

                                            if zone_details.get("method") == "interest_zones":
                                                # Используем зоны, если они дают лучшие значения
                                                if (
                                                    abs(tp1_pct_zone - tp1_pct) > 0.1
                                                ):  # Если разница значительная
                                                    tp1_pct = tp1_pct_zone
                                                    tp2_pct = tp2_pct_zone
                                                    sl_pct_positive = sl_pct_zone
                                                    logger.info(
                                                        "🎯 [%s] TP/SL от Interest Zones: TP1=%.2f%%, TP2=%.2f%%, SL=%.2f%%",
                                                        symbol,
                                                        tp1_pct,
                                                        tp2_pct,
                                                        sl_pct_positive,
                                                    )
                                    except Exception as e:
                                        logger.debug(
                                            "⚠️ [%s] Ошибка расчета TP/SL от Interest Zones: %s",
                                            symbol,
                                            e,
                                        )

                            except Exception as e:
                                logger.warning(
                                    "⚠️ [%s] Ошибка расчета динамических TP/SL от зон: %s, используем базовые",
                                    symbol,
                                    e,
                                )

                        # 🏆 ОПТИМИЗАЦИЯ TP/SL: Улучшение соотношения (на основе бектеста)
                        # Увеличиваем TP на 20%, уменьшаем SL на 20% для лучшего Profit Factor
                        tp1_pct_optimized = tp1_pct * 1.2
                        tp2_pct_optimized = tp2_pct * 1.2
                        sl_pct_optimized = sl_pct_positive * 0.8

                        # Рассчитываем цены TP и SL с оптимизацией
                        # 🆕 Обновляем переменные уровня функции (не создаем локальные)
                        if signal_type.upper() == "BUY":
                            tp1_price = signal_price * (1 + tp1_pct_optimized / 100)
                            tp2_price = signal_price * (1 + tp2_pct_optimized / 100)
                            sl_price = signal_price * (1 - sl_pct_optimized / 100)
                            sl_pct = -sl_pct_optimized  # Отрицательный для отображения
                        else:
                            tp1_price = signal_price * (1 - tp1_pct_optimized / 100)
                            tp2_price = signal_price * (1 - tp2_pct_optimized / 100)
                            sl_price = signal_price * (1 + sl_pct_optimized / 100)
                            sl_pct = -sl_pct_optimized  # Отрицательный для отображения

                        logger.debug(
                            "🎯 [%s] Оптимизированные TP/SL: TP1=%.2f%%, TP2=%.2f%%, SL=%.2f%% (было: TP1=%.2f%%, TP2=%.2f%%, SL=%.2f%%)",
                            symbol,
                            tp1_pct_optimized,
                            tp2_pct_optimized,
                            sl_pct_optimized,
                            tp1_pct,
                            tp2_pct,
                            sl_pct_positive,
                        )
                    else:
                        # Значения по умолчанию
                        tp1_pct, tp2_pct = 2.75, 4.80
                        # 🆕 Обновляем переменные уровня функции (не создаем локальные)
                        if signal_type.upper() == "BUY":
                            tp1_price = signal_price * 1.0275
                            tp2_price = signal_price * 1.048
                            sl_price = signal_price * 0.98
                        else:
                            tp1_price = signal_price * 0.9725
                            tp2_price = signal_price * 0.952
                            sl_price = signal_price * 1.02
                        sl_pct = -2.0
                except Exception as e:
                    logger.warning("⚠️ Ошибка расчета TP/SL: %s", e)
                    # Значения по умолчанию
                    tp1_pct, tp2_pct = 2.75, 4.80
                    # 🆕 Обновляем переменные уровня функции (не создаем локальные)
                    if signal_type.upper() == "BUY":
                        tp1_price = signal_price * 1.0275
                        tp2_price = signal_price * 1.048
                        sl_price = signal_price * 0.98
                    else:
                        tp1_price = signal_price * 0.9725
                        tp2_price = signal_price * 0.952
                        sl_price = signal_price * 1.02
                    sl_pct = -2.0

                # ИИ-оптимизированный расчет параметров для каждого пользователя
                deposit_usdt = user_data.get("deposit", 1000.0)
                # 🆕 Обновляем переменную уровня функции (не создаем локальную)
                trade_mode = user_data.get("trade_mode", "spot")
                # Обновляем переменную уровня функции для автоисполнения
                base_risk_pct = user_data.get("risk_pct", 2.0)
                base_leverage = user_data.get("leverage", 5.0 if trade_mode == "futures" else 1.0)

                baseline_amount_usd = float(deposit_usdt) * (float(base_risk_pct) / 100.0)
                sizing_audit = {
                    "symbol": symbol,
                    "direction": signal_type.upper(),
                    "entry_time": get_utc_now().isoformat(),
                    "user_id": user_data.get("user_id"),
                    "trade_mode": trade_mode,
                    "signal_price": signal_price,
                    "baseline_amount_usd": baseline_amount_usd,
                    "ai_amount_usd": None,
                    "regime_multiplier": regime_multipliers.get("position_size", 1.0)
                    if regime_multipliers
                    else 1.0,
                    "after_regime_amount_usd": None,
                    "correlation_multiplier": 1.0,
                    "after_correlation_amount_usd": None,
                    "adaptive_multiplier": 1.0,
                    "after_adaptive_amount_usd": None,
                    "risk_adjustment_multiplier": 1.0,
                    "final_amount_usd": None,
                    "base_risk_pct": float(base_risk_pct),
                    "ai_risk_pct": None,
                    "leverage": None,
                    "regime": regime_data.get("regime") if regime_data else None,
                    "regime_confidence": regime_data.get("confidence") if regime_data else None,
                    "quality_score": quality_score,
                    "composite_score": composite_result.get("composite_score")
                    if composite_result
                    else None,
                    "pattern_confidence": pattern_confidence,
                    "adaptive_reason": None,
                    "adaptive_components": None,
                    "signal_token": None,
                }

                # 🤖 ИИ-ОПТИМИЗАЦИЯ ПАРАМЕТРОВ
                try:
                    if df is not None and len(df) > 0:
                        from src.ai.position_sizing import AIPositionSizing

                        ai_system = AIPositionSizing()

                        # Получаем ИИ-оптимизированные параметры
                        ai_risk_pct, ai_leverage, ai_entry_amount = (
                            ai_system.calculate_ai_optimized_position_size(
                                symbol=symbol,
                                side=signal_type,
                                df=df,
                                current_index=len(df) - 1,
                                user_data=user_data,
                                base_risk_pct=base_risk_pct,
                                base_leverage=base_leverage,
                            )
                        )
                    else:
                        raise ValueError("DataFrame недоступен для ИИ-анализа")

                    # Используем ИИ-оптимизированные значения
                    risk_pct = ai_risk_pct
                    # 🆕 Обновляем переменные уровня функции (не создаем локальные)
                    # ИСПРАВЛЕНО: возвращаем динамическое плечо (float) для точности
                    leverage = float(ai_leverage) if trade_mode == "futures" else 1.0
                    # 🔧 ИСПРАВЛЕНО: entry_amount_usdt должна быть маржой (без плеча), а не номиналом
                    # ИИ возвращает номинал (с плечом), нужно разделить на плечо для получения маржи
                    if trade_mode == "futures" and leverage > 1:
                        entry_amount_usdt = ai_entry_amount / leverage  # Маржа = номинал / плечо
                    else:
                        entry_amount_usdt = ai_entry_amount

                    sizing_audit["ai_risk_pct"] = float(risk_pct)
                    sizing_audit["ai_amount_usd"] = float(entry_amount_usdt)
                    sizing_audit["leverage"] = float(leverage)

                    logger.info(
                        "🤖 [%s] ИИ-оптимизация: риск=%.2f%% (было %.2f%%), плечо=%.1fx (было %.1fx)",
                        symbol,
                        ai_risk_pct,
                        base_risk_pct,
                        leverage,
                        base_leverage,
                    )

                except (ImportError, Exception) as e:
                    logger.warning(
                        "⚠️ [%s] ИИ-оптимизация недоступна: %s, используем базовые параметры",
                        symbol,
                        e,
                    )
                    # Используем базовые значения, они будут уточнены в Intelligent Sizing ниже
                    risk_pct = base_risk_pct
                    leverage = float(base_leverage) if trade_mode == "futures" else 1.0
                    entry_amount_usdt = deposit_usdt * (risk_pct / 100)

                # 🧠 ИНТЕЛЛЕКТУАЛЬНЫЙ РАСЧЕТ РАЗМЕРА ПОЗИЦИИ (KELLY + SL AWARE)
                if RISK_MANAGER_AVAILABLE and risk_manager:
                    try:
                        # Собираем данные для умного расчета
                        conf_score = (
                            composite_result.get("confidence", 0.5) if composite_result else 0.5
                        )
                        ml_conf = (
                            ml_prediction.get("success_probability") if ml_prediction else None
                        )
                        current_regime = (
                            regime_data.get("regime", "NORMAL") if regime_data else "NORMAL"
                        )

                        # Обновляем баланс в менеджере рисков перед расчетом
                        risk_manager.update_balance(deposit_usdt)

                        # Выполняем умный расчет
                        intelligent_size = risk_manager.calculate_intelligent_position_size(
                            symbol=symbol,
                            entry_price=signal_price,
                            stop_loss_price=sl_price,
                            confidence_score=conf_score,
                            ml_confidence=ml_conf,
                            regime=current_regime,
                        )

                        if intelligent_size:
                            # Обновляем параметры на основе умного расчета
                            entry_amount_usdt = float(intelligent_size["margin_used"])
                            risk_pct = float(intelligent_size["position_size_pct"])

                            sizing_audit["intelligent_method"] = intelligent_size.get("method")
                            sizing_audit["kelly_fraction"] = float(
                                intelligent_size.get("kelly_fraction", 0)
                            )

                            logger.info(
                                "🧠 [%s] Intelligent Sizing (Kelly): сумма=%.2f USDT, риск=%.2f%% (conf=%.2f, ml=%s, regime=%s)",
                                symbol,
                                entry_amount_usdt,
                                risk_pct,
                                conf_score,
                                ml_conf,
                                current_regime,
                            )
                    except Exception as e:
                        logger.error("❌ [%s] Ошибка в Intelligent Sizing: %s", symbol, e)

                sizing_audit["ai_risk_pct"] = float(risk_pct)
                sizing_audit["ai_amount_usd"] = float(entry_amount_usdt)
                sizing_audit["leverage"] = float(leverage)

                # ПРИМЕНЯЕМ МНОЖИТЕЛИ РЫНОЧНОГО РЕЖИМА (если они еще не учтены в Intelligent Sizing)
                # Мы их уже учли внутри calculate_intelligent_position_size, поэтому здесь
                # просто фиксируем для аудита.
                regime_multiplier_used = (
                    regime_multipliers.get("position_size", 1.0) if regime_multipliers else 1.0
                )
                sizing_audit["regime_multiplier"] = float(regime_multiplier_used)
                sizing_audit["after_regime_amount_usd"] = float(entry_amount_usdt)

                # ПРИМЕНЯЕМ CORRELATION PENALTY
                correlation_multiplier = 1.0
                if CORRELATION_MANAGER_AVAILABLE and correlation_manager:
                    try:
                        penalty_data = await correlation_manager.calculate_position_multiplier(
                            symbol=symbol, user_id=user_data.get("user_id"), df=df
                        )
                        correlation_multiplier = penalty_data["multiplier"]

                        before_penalty = entry_amount_usdt
                        entry_amount_usdt *= correlation_multiplier

                        if correlation_multiplier < 1.0:
                            logger.info(
                                "📉 [PENALTY] %s: сумма %.2f → %.2f USDT (x%.2f) - %s",
                                symbol,
                                before_penalty,
                                entry_amount_usdt,
                                correlation_multiplier,
                                penalty_data["reason"],
                            )

                    except Exception as e:
                        logger.debug("Ошибка correlation penalty: %s", e)

                sizing_audit["correlation_multiplier"] = float(correlation_multiplier)
                sizing_audit["after_correlation_amount_usd"] = float(entry_amount_usdt)

                # ПРИМЕНЯЕМ ADAPTIVE POSITION SIZING (финальная коррекция)
                if ADAPTIVE_SIZER_AVAILABLE and adaptive_sizer:
                    try:
                        # Используем переданные параметры или дефолтные значения
                        adaptive_result = adaptive_sizer.calculate_quality_multiplier(
                            {
                                "composite_score": composite_result.get("composite_score", 0.5)
                                if composite_result
                                else 0.5,
                                "composite_confidence": composite_result.get("confidence", 0.5)
                                if composite_result
                                else 0.5,
                                "quality_score": quality_score,
                                "pattern_confidence": pattern_confidence,
                                "regime": regime_data.get("regime", "NEUTRAL")
                                if regime_data
                                else "NEUTRAL",
                                "regime_confidence": regime_data.get("confidence", 0.5)
                                if regime_data
                                else 0.5,
                                "volatility_pct": df["volatility"].iloc[-1] / 100
                                if "volatility" in df.columns
                                else 0.03,
                                "symbol": symbol,
                            }
                        )

                        adaptive_multiplier = adaptive_result["multiplier"]
                        before_adaptive = entry_amount_usdt
                        entry_amount_usdt *= adaptive_multiplier

                        sizing_audit["adaptive_multiplier"] = float(adaptive_multiplier)
                        sizing_audit["after_adaptive_amount_usd"] = float(entry_amount_usdt)
                        sizing_audit["adaptive_reason"] = adaptive_result.get("reason")
                        sizing_audit["adaptive_components"] = adaptive_result.get("components")

                        logger.info(
                            "⚖️ [ADAPTIVE] %s: сумма %.2f → %.2f USDT (x%.2f) - %s",
                            symbol,
                            before_adaptive,
                            entry_amount_usdt,
                            adaptive_multiplier,
                            adaptive_result["reason"],
                        )

                    except Exception as e:
                        logger.debug("Ошибка adaptive sizing: %s", e)

                # 🆕 КОМПЕНСАЦИЯ ПРОСКАЛЬЗЫВАНИЯ (корректировка размера позиции)
                try:
                    from src.execution.slippage_manager import get_slippage_manager

                    slippage_manager = get_slippage_manager()

                    # Получаем volume_24h для символа
                    volume_24h = None
                    if sources_hub:
                        try:
                            volume_24h = await sources_hub.get_volume_data(symbol)
                        except Exception:
                            pass

                    # Применяем компенсацию проскальзывания
                    if slippage_manager is not None:
                        before_slippage_compensation = entry_amount_usdt
                        entry_amount_usdt = slippage_manager.get_adjusted_position_size(
                            symbol=symbol,
                            base_position_size=entry_amount_usdt,
                            volume_24h=volume_24h,
                        )
                    else:
                        before_slippage_compensation = entry_amount_usdt

                    if entry_amount_usdt < before_slippage_compensation:
                        compensation_pct = (
                            1 - entry_amount_usdt / before_slippage_compensation
                        ) * 100
                        logger.info(
                            "💰 [SLIPPAGE COMPENSATION] %s: размер скорректирован %.2f → %.2f USDT (компенсация %.2f%%)",
                            symbol,
                            before_slippage_compensation,
                            entry_amount_usdt,
                            compensation_pct,
                        )
                        sizing_audit["slippage_compensation_pct"] = float(compensation_pct)
                        sizing_audit["after_slippage_compensation_amount_usd"] = float(
                            entry_amount_usdt
                        )
                except Exception as e:
                    logger.debug("Ошибка компенсации проскальзывания: %s", e)

                # 🆕 ПРОВЕРКА PORTFOLIO RISK (финальная проверка перед отправкой)
                if PORTFOLIO_RISK_MANAGER_AVAILABLE and portfolio_risk_manager:
                    try:
                        pre_risk_amount_usd = entry_amount_usdt
                        risk_check = await portfolio_risk_manager.check_portfolio_risk(
                            user_id=user_data.get("user_id"),
                            new_position_size_usdt=entry_amount_usdt,
                            user_data=user_data,
                        )

                        if not risk_check["allowed"]:
                            reason = risk_check.get("reason", "UNKNOWN")
                            if reason == "POSITION_SIZE_TOO_LARGE":
                                suggested_max = float(
                                    risk_check.get("details", {}).get("suggested_max_size") or 0.0
                                )
                                if suggested_max > 0:
                                    adjusted_amount = min(entry_amount_usdt, suggested_max)
                                    if adjusted_amount < entry_amount_usdt:
                                        multiplier = (
                                            adjusted_amount / entry_amount_usdt
                                            if entry_amount_usdt
                                            else 1.0
                                        )
                                        logger.warning(
                                            (
                                                "⚠️ [PORTFOLIO RISK] %s %s: размер позиции %.2f USDT "
                                                "превышает лимит %.2f%%. Уменьшаем до %.2f USDT."
                                            ),
                                            symbol,
                                            signal_type,
                                            entry_amount_usdt,
                                            portfolio_risk_manager.risk_limits[
                                                "max_capital_per_position_pct"
                                            ],
                                            adjusted_amount,
                                        )
                                        entry_amount_usdt = adjusted_amount
                                        sizing_audit["risk_adjustment_multiplier"] = float(
                                            multiplier
                                        )
                                        risk_check["allowed"] = True
                                    else:
                                        logger.warning(
                                            "⚠️ [PORTFOLIO RISK] %s %s: рассчитанный размер уже в пределах лимита",
                                            symbol,
                                            signal_type,
                                        )
                                        risk_check["allowed"] = True
                                else:
                                    logger.warning(
                                        "🚫 [SEND_SIGNAL BLOCK] %s %s: Portfolio risk заблокирован - %s (нет предложения)",
                                        symbol,
                                        signal_type,
                                        reason,
                                    )
                                    return False
                            else:
                                logger.warning(
                                    "🚫 [SEND_SIGNAL BLOCK] %s %s: Portfolio risk заблокирован - %s",
                                    symbol,
                                    signal_type,
                                    reason,
                                )
                                return False

                        # Корректируем размер позиции на основе portfolio risk
                        risk_adjusted_size = portfolio_risk_manager.get_position_size_adjustment(
                            entry_amount_usdt
                        )
                        if risk_adjusted_size < entry_amount_usdt:
                            logger.info(
                                "📉 [PORTFOLIO RISK] %s: размер скорректирован %.2f → %.2f USDT (risk score: %.2f)",
                                symbol,
                                entry_amount_usdt,
                                risk_adjusted_size,
                                risk_check["risk_score"],
                            )
                            entry_amount_usdt = risk_adjusted_size
                            sizing_audit["risk_adjustment_multiplier"] = (
                                float(risk_adjusted_size) / float(pre_risk_amount_usd)
                                if pre_risk_amount_usd
                                else 1.0
                            )

                    except Exception as e:
                        logger.debug("⚠️ Ошибка portfolio risk manager: %s", e)

                if sizing_audit.get("after_adaptive_amount_usd") is None:
                    sizing_audit["after_adaptive_amount_usd"] = float(entry_amount_usdt)

                # Расчет количества для отображения в сигнале
                # 🔧 ИСПРАВЛЕНО: entry_amount_usdt - это маржа (без плеча)
                # Для futures: количество = (entry_amount_usdt * leverage) / signal_price
                #   Это дает номинал позиции = entry_amount_usdt * leverage
                # Для spot: количество = entry_amount_usdt / signal_price
                if trade_mode == "futures" and leverage > 1:
                    quantity = (entry_amount_usdt * leverage) / signal_price
                else:
                    quantity = entry_amount_usdt / signal_price

                # Рассчитываем техническую уверенность (заглушка)
                _ = 85.0  # confidence - не используется в текущей версии

                # Логирование для отладки
                logger.info(
                    "💰 [%s] Финальные параметры: депозит=%.2f USDT, режим=%s, риск=%.2f%%, "
                    "плечо=%.1fx, сумма_входа=%.2f USDT, количество=%.6f",
                    symbol,
                    deposit_usdt,
                    trade_mode,
                    risk_pct,
                    leverage,
                    entry_amount_usdt,
                    quantity,
                )

                # 🛡️ ФИЛЬТР МИКРО-СДЕЛОК: предотвращение открытия копеечных позиций
                min_allowed_order = 5.5  # С запасом от 5.0 USDT (лимит Bitget)
                if entry_amount_usdt and entry_amount_usdt < min_allowed_order:
                    logger.warning(
                        "📉 [%s] Сигнал ОТМЕНЕН: сумма входа %.2f USDT меньше минимума %.2f USDT",
                        symbol,
                        entry_amount_usdt,
                        min_allowed_order,
                    )
                    if trace is not None:
                        trace.finish(
                            status="error",
                            metadata={"reason": "micro_order", "amount": entry_amount_usdt},
                        )
                    return False

                sizing_audit["final_amount_usd"] = float(entry_amount_usdt)
                if sizing_audit["ai_risk_pct"] is None:
                    sizing_audit["ai_risk_pct"] = float(risk_pct)
                if sizing_audit["ai_amount_usd"] is None:
                    sizing_audit["ai_amount_usd"] = float(baseline_amount_usd)
                if sizing_audit["after_regime_amount_usd"] is None:
                    sizing_audit["after_regime_amount_usd"] = float(entry_amount_usdt)
                if sizing_audit["after_correlation_amount_usd"] is None:
                    sizing_audit["after_correlation_amount_usd"] = float(entry_amount_usdt)
                if sizing_audit["after_adaptive_amount_usd"] is None:
                    sizing_audit["after_adaptive_amount_usd"] = float(entry_amount_usdt)
                if sizing_audit["leverage"] is None:
                    sizing_audit["leverage"] = float(leverage)

                # Рассчитываем реальные технические данные для каждой монеты
                technical_data = {}

                if df is not None and len(df) > 0:
                    try:
                        # RSI
                        if "rsi" in df.columns:
                            current_rsi = df["rsi"].iloc[-1]
                            technical_data["rsi"] = (
                                round(current_rsi, 1) if not pd.isna(current_rsi) else 50.0
                            )
                        else:
                            technical_data["rsi"] = 50.0

                        # MACD статус
                        if "macd" in df.columns and "macd_signal" in df.columns:
                            macd = df["macd"].iloc[-1]
                            macd_signal = df["macd_signal"].iloc[-1]
                            if not pd.isna(macd) and not pd.isna(macd_signal):
                                technical_data["macd_status"] = (
                                    "Бычий" if macd > macd_signal else "Медвежий"
                                )
                            else:
                                technical_data["macd_status"] = "Нейтральный"
                        else:
                            technical_data["macd_status"] = "Нейтральный"

                        # Объем статус
                        if "volume_ratio" in df.columns:
                            volume_ratio = df["volume_ratio"].iloc[-1]
                            if not pd.isna(volume_ratio):
                                if volume_ratio > 1.5:
                                    technical_data["volume_status"] = "Очень высокий"
                                elif volume_ratio > 1.2:
                                    technical_data["volume_status"] = "Выше среднего"
                                elif volume_ratio > 0.8:
                                    technical_data["volume_status"] = "Средний"
                                else:
                                    technical_data["volume_status"] = "Ниже среднего"
                            else:
                                technical_data["volume_status"] = "Средний"
                        else:
                            technical_data["volume_status"] = "Средний"

                    except Exception as e:
                        logger.warning("⚠️ [%s] Ошибка расчета технических данных: %s", symbol, e)
                        technical_data = {
                            "rsi": 50.0,
                            "macd_status": "Нейтральный",
                            "volume_status": "Средний",
                        }
                else:
                    # Fallback значения
                    technical_data = {
                        "rsi": 50.0,
                        "macd_status": "Нейтральный",
                        "volume_status": "Средний",
                    }

                # Рассчитываем FGI (Fear & Greed Index)
                try:
                    if df is not None and len(df) > 25:
                        # Импортируем функцию расчета FGI
                        from archive.experimental.signal_live_PROTECTED import (
                            calculate_fear_greed_index,
                        )

                        fgi_val = calculate_fear_greed_index(df, len(df) - 1)

                        # Определяем текст статуса
                        if fgi_val < 25:
                            fgi_text = f"Крайний страх ({fgi_val:.1f})"
                        elif fgi_val < 45:
                            fgi_text = f"Страх ({fgi_val:.1f})"
                        elif fgi_val < 55:
                            fgi_text = f"Нейтрально ({fgi_val:.1f})"
                        elif fgi_val < 75:
                            fgi_text = f"Жадность ({fgi_val:.1f})"
                        else:
                            fgi_text = f"Крайняя жадность ({fgi_val:.1f})"
                    else:
                        fgi_val = 50.0
                        fgi_text = "Нейтрально (50.0)"
                except Exception as e:
                    logger.warning("⚠️ [%s] Ошибка расчета FGI: %s", symbol, e)
                    fgi_val = 50.0
                    fgi_text = "Нейтрально (50.0)"

                # Рассчитываем тренды основных монет (используется реальные данные BTC)
                try:
                    # 🆕 Получаем реальный тренд BTC для отображения в сообщении
                    # Это должно совпадать с check_btc_alignment
                    if HYBRID_DATA_MANAGER_AVAILABLE and HYBRID_DATA_MANAGER:
                        btc_df = await HYBRID_DATA_MANAGER.get_smart_data("BTCUSDT", "ohlc")
                        if btc_df is not None:
                            # Конвертируем список в DataFrame если нужно
                            if isinstance(btc_df, list):
                                if len(btc_df) > 0:
                                    btc_df = pd.DataFrame(btc_df)
                                    if "timestamp" in btc_df.columns:
                                        btc_df["timestamp"] = pd.to_datetime(
                                            btc_df["timestamp"], unit="ms", errors="coerce"
                                        )
                                        btc_df.set_index("timestamp", inplace=True)

                            # Определяем тренд BTC по EMA (как в check_btc_alignment)
                            if (
                                isinstance(btc_df, pd.DataFrame)
                                and not btc_df.empty
                                and len(btc_df) >= 50
                            ):
                                btc_ema_fast = (
                                    btc_df["ema_fast"].iloc[-1]
                                    if "ema_fast" in btc_df.columns
                                    else btc_df["close"].ewm(span=12).mean().iloc[-1]
                                )
                                btc_ema_slow = (
                                    btc_df["ema_slow"].iloc[-1]
                                    if "ema_slow" in btc_df.columns
                                    else btc_df["close"].ewm(span=26).mean().iloc[-1]
                                )
                                btc_trend_status = (
                                    btc_ema_fast > btc_ema_slow
                                )  # True = бычий, False = медвежий
                                logger.debug(
                                    "✅ [BTC TREND] %s: Реальный тренд BTC = %s (EMA fast=%.2f, slow=%.2f)",
                                    symbol,
                                    "🟢 БЫЧИЙ" if btc_trend_status else "🔴 МЕДВЕЖИЙ",
                                    btc_ema_fast,
                                    btc_ema_slow,
                                )
                            else:
                                # Fallback: если данных недостаточно, используем значение из check_btc_alignment
                                btc_trend_status = None
                                logger.debug(
                                    "⚠️ [BTC TREND] %s: Недостаточно данных BTC для определения тренда",
                                    symbol,
                                )
                        else:
                            btc_trend_status = None
                            logger.debug("⚠️ [BTC TREND] %s: Данные BTC недоступны", symbol)
                    else:
                        btc_trend_status = None
                        logger.debug("⚠️ [BTC TREND] %s: HybridDataManager недоступен", symbol)

                    # 🆕 Рассчитываем реальные тренды ETH и SOL (отдельно от BTC)
                    eth_trend_status = None
                    sol_trend_status = None

                    # ETH тренд
                    if HYBRID_DATA_MANAGER_AVAILABLE and HYBRID_DATA_MANAGER:
                        try:
                            eth_df = await HYBRID_DATA_MANAGER.get_smart_data("ETHUSDT", "ohlc")
                            if eth_df is not None:
                                if isinstance(eth_df, list):
                                    if len(eth_df) > 0:
                                        eth_df = pd.DataFrame(eth_df)
                                        if "timestamp" in eth_df.columns:
                                            eth_df["timestamp"] = pd.to_datetime(
                                                eth_df["timestamp"], unit="ms", errors="coerce"
                                            )
                                            eth_df.set_index("timestamp", inplace=True)

                                if (
                                    isinstance(eth_df, pd.DataFrame)
                                    and not eth_df.empty
                                    and len(eth_df) >= 50
                                ):
                                    eth_ema_fast = (
                                        eth_df["ema_fast"].iloc[-1]
                                        if "ema_fast" in eth_df.columns
                                        else eth_df["close"].ewm(span=12).mean().iloc[-1]
                                    )
                                    eth_ema_slow = (
                                        eth_df["ema_slow"].iloc[-1]
                                        if "ema_slow" in eth_df.columns
                                        else eth_df["close"].ewm(span=26).mean().iloc[-1]
                                    )
                                    eth_trend_status = eth_ema_fast > eth_ema_slow
                                    logger.debug(
                                        "✅ [ETH TREND] %s: Реальный тренд ETH = %s (EMA fast=%.2f, slow=%.2f)",
                                        symbol,
                                        "🟢 БЫЧИЙ" if eth_trend_status else "🔴 МЕДВЕЖИЙ",
                                        eth_ema_fast,
                                        eth_ema_slow,
                                    )
                        except Exception as eth_exc:
                            logger.debug(
                                "⚠️ [ETH TREND] %s: Ошибка определения тренда ETH: %s",
                                symbol,
                                eth_exc,
                            )

                    # SOL тренд
                    if HYBRID_DATA_MANAGER_AVAILABLE and HYBRID_DATA_MANAGER:
                        try:
                            sol_df = await HYBRID_DATA_MANAGER.get_smart_data("SOLUSDT", "ohlc")
                            if sol_df is not None:
                                if isinstance(sol_df, list):
                                    if len(sol_df) > 0:
                                        sol_df = pd.DataFrame(sol_df)
                                        if "timestamp" in sol_df.columns:
                                            sol_df["timestamp"] = pd.to_datetime(
                                                sol_df["timestamp"], unit="ms", errors="coerce"
                                            )
                                            sol_df.set_index("timestamp", inplace=True)

                                if (
                                    isinstance(sol_df, pd.DataFrame)
                                    and not sol_df.empty
                                    and len(sol_df) >= 50
                                ):
                                    sol_ema_fast = (
                                        sol_df["ema_fast"].iloc[-1]
                                        if "ema_fast" in sol_df.columns
                                        else sol_df["close"].ewm(span=12).mean().iloc[-1]
                                    )
                                    sol_ema_slow = (
                                        sol_df["ema_slow"].iloc[-1]
                                        if "ema_slow" in sol_df.columns
                                        else sol_df["close"].ewm(span=26).mean().iloc[-1]
                                    )
                                    sol_trend_status = sol_ema_fast > sol_ema_slow
                                    logger.debug(
                                        "✅ [SOL TREND] %s: Реальный тренд SOL = %s (EMA fast=%.2f, slow=%.2f)",
                                        symbol,
                                        "🟢 БЫЧИЙ" if sol_trend_status else "🔴 МЕДВЕЖИЙ",
                                        sol_ema_fast,
                                        sol_ema_slow,
                                    )
                        except Exception as sol_exc:
                            logger.debug(
                                "⚠️ [SOL TREND] %s: Ошибка определения тренда SOL: %s",
                                symbol,
                                sol_exc,
                            )
                except Exception as e:
                    logger.warning("⚠️ [BTC TREND] %s: Ошибка определения тренда BTC: %s", symbol, e)
                    btc_trend_status = None
                    eth_trend_status = None
                    sol_trend_status = None

                # Рассчитываем уверенность ИИ
                if ml_prediction and ml_prediction.get("success_probability"):
                    ai_confidence = ml_prediction["success_probability"] * 100
                    logger.info(
                        "🤖 [CONFIDENCE] Используем уверенность из ML модели: %.2f%%", ai_confidence
                    )
                else:
                    try:
                        if "rsi" in technical_data and technical_data["rsi"] != 50.0:
                            # Базовая уверенность на основе RSI и других факторов
                            rsi_confidence = 100 - abs(technical_data["rsi"] - 50) * 2
                            macd_confidence = 90 if technical_data["macd_status"] == "Бычий" else 70
                            volume_confidence = (
                                95 if "высокий" in technical_data["volume_status"].lower() else 80
                            )

                            ai_confidence = (
                                rsi_confidence * 0.4
                                + macd_confidence * 0.3
                                + volume_confidence * 0.3
                            )
                            ai_confidence = max(60, min(95, ai_confidence))  # Ограничиваем 60-95%
                        else:
                            ai_confidence = 85.0
                    except Exception:
                        ai_confidence = 85.0

                # РАСЧЕТ MTF НАКОПЛЕНИЯ - как в оригинале
                try:
                    mtf_accumulation_line = build_mtf_accumulation_line(
                        symbol, signal_type or "LONG", None
                    ).strip()
                    logger.debug(
                        "✅ %s: MTF накопление рассчитано: %s", symbol, mtf_accumulation_line
                    )
                except Exception as mtf_calc_error:
                    logger.warning(
                        "⚠️ Ошибка расчета MTF накопления для %s: %s", symbol, mtf_calc_error
                    )
                    mtf_accumulation_line = "• MTF накопление: 50/100"

                # Рассчитываем CONF сигнала (как в рабочей версии от 19 октября)
                conf_status = await calculate_conf_signal(symbol)

                # Рассчитываем FVG аномалии (как в рабочей версии от 19 октября)
                fvg_status = await calculate_fvg_anomalies(symbol, signal_type)

                judge_verdict_obj = lm_judge.judge_signal(
                    symbol=symbol,
                    side=signal_type,
                    risk_pct=risk_pct,
                    confidence=ai_confidence,
                    guidance_entries=guidance_summary,
                )
                judge_verdict = judge_verdict_obj.to_dict()
                if trace is not None:
                    trace.record(step="think", name="lm_judge_signal", metadata=judge_verdict)

                # 📰 ПРОВЕРКА НОВОСТЕЙ
                news_indicator = ""
                news_info_block = ""
                sentiment = "neutral"
                try:
                    # 🆕 ИСПОЛЬЗУЕМ УЖЕ ПОЛУЧЕННЫЙ АНАЛИЗ ИЗ МЕТАДАННЫХ (если есть)
                    news_analysis = None
                    if ml_prediction and isinstance(ml_prediction, dict):
                        news_analysis = ml_prediction.get("news_analysis")

                    # Если в метаданных нет, пробуем получить (fallback)
                    if not news_analysis and get_symbol_news_analysis:
                        news_analysis = await get_symbol_news_analysis(symbol)

                    if news_analysis:
                        sentiment = news_analysis.get("sentiment", "neutral")
                        top_news = news_analysis.get("top_news", [])
                        if top_news:
                            news_titles = [f"• {n['title'][:50]}..." for n in top_news[:2]]
                            news_info_block = "\n".join(news_titles)

                        if sentiment == "bullish":
                            news_indicator = "🚀"
                        elif sentiment == "bearish":
                            news_indicator = "⚠️"
                except Exception as news_err:
                    logger.debug("⚠️ Ошибка получения новостей для %s: %s", symbol, news_err)

                # 🛡️ ПРОВЕРКА: Минимальный размер ордера (5.0 USDT)
                if entry_amount_usdt is not None and entry_amount_usdt < 5.0:
                    logger.warning(
                        "🚫 [SEND_SIGNAL BLOCK] %s: Сумма входа %.2f USDT меньше минимума (5.0 USDT)",
                        symbol,
                        entry_amount_usdt,
                    )
                    return False

                # Формируем сообщение сигнала
                message = build_new_signal_message(
                    symbol=symbol,
                    side=signal_type.lower(),
                    signal_price=signal_price,
                    trade_mode=user_data.get("trade_mode", "spot"),
                    filter_mode=user_data.get("filter_mode", "soft"),
                    created_at_str=time.strftime("%d.%m.%Y %H:%M"),
                    news_indicator=news_indicator,
                    technical_data=technical_data,
                    fgi_val=int(fgi_val) if fgi_val is not None else 50,
                    fgi_text=fgi_text if fgi_text else "Neutral",
                    btc_trend_status=btc_trend_status,
                    eth_trend_status=eth_trend_status,
                    sol_trend_status=sol_trend_status,
                    whale_line=f"• CONF сигнала: {conf_status}",
                    anomalies_line=f"• FVG: {fvg_status}",
                    accumulation_line=mtf_accumulation_line,
                    news_info_block=news_info_block,
                    price_formatter=price_formatter,
                    risk_pct=risk_pct,
                    # Новые параметры для полного формата
                    quantity=quantity,
                    leverage=leverage,
                    entry_amount_usdt=entry_amount_usdt,
                    tp1_price=tp1_price,
                    tp2_price=tp2_price,
                    sl_price=sl_price,
                    tp1_pct=tp1_pct,
                    tp2_pct=tp2_pct,
                    sl_pct=sl_pct,
                    confidence=ai_confidence,
                    guidance_entries=guidance_summary,
                    judge_verdict=judge_verdict,
                    ai_factors=ml_prediction.get("ai_factors") if ml_prediction else None,
                )

                # Создаем клавиатуру: ПРИНЯТЬ + HITL-фидбек
                signal_token = time.strftime("%m%d%H%M")
                # Преобразуем направление: SELL -> short, BUY -> long
                signal_type_lower = (signal_type or "").lower()
                if signal_type_lower == "sell":
                    direction_norm = "short"
                elif signal_type_lower == "buy":
                    direction_norm = "long"
                else:
                    direction_norm = signal_type_lower  # fallback
                price_str = price_formatter(signal_price)

                # Форматируем количество с правильной точностью
                qty_precision = symbol_info.get("qty_precision", 4) if symbol_info else 4
                # Используем уже рассчитанное quantity
                qty_str = f"{quantity:.{qty_precision}f}".rstrip("0").rstrip(".")

                risk_str = str(round(float(risk_pct), 2))
                lev_str = f"{leverage:.1f}"

                cb_data = (
                    f"accept|{symbol}|{signal_token}|{price_str}|{qty_str}|"
                    f"{direction_norm}|{risk_str}|{lev_str}"
                )
                sizing_audit["signal_price"] = signal_price
                sizing_audit["signal_token"] = signal_token
                _log_position_sizing_event(sizing_audit)

                # Только кнопка "ПРИНЯТЬ" - система анализирует сигналы автоматически
                # через Judge verdict, PnL метрики, win rate и другие автоматические механизмы
                keyboard = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("ПРИНЯТЬ", callback_data=cb_data)]]
                )

                # ИСПРАВЛЕНО: Используем улучшенную систему доставки
                message_id_result = None
                # 🔧 ИСПРАВЛЕНО: Если сигнал уже был отправлен ранее, не отправляем повторно, но считаем успешной отправкой
                if signal_was_sent_earlier:
                    # Сигнал уже был отправлен - пропускаем отправку, но продолжаем для автоисполнения
                    logger.info(
                        "⏭️ [SEND_SIGNAL] %s %s: Пропускаем повторную отправку (уже был отправлен ранее), продолжаем для автоисполнения",
                        symbol,
                        signal_type,
                    )
                else:
                    signal_sent_successfully = False  # 🆕 Флаг успешной отправки сигнала (инициализируем только если не был отправлен ранее)
                    if ENHANCED_DELIVERY_AVAILABLE:
                        # 🆕 Отправляем в оба бота (DEV и PROD)
                        success = await notify_user_enhanced(
                            user_data.get("user_id"),
                            message,
                            reply_markup=keyboard,
                            _send_to_both_bots=True,
                        )
                        signal_sent_successfully = bool(success)  # 🆕 Сохраняем результат отправки
                        if success:
                            logger.info(
                                "📤 Сигнал отправлен в Telegram с кнопкой (enhanced): %s", symbol
                            )
                            # Получаем message_id из результата
                            if isinstance(success, dict) and "message_id" in success:
                                message_id_result = success.get("message_id")
                            elif isinstance(success, bool) and success:
                                # Если success=True, но нет message_id, попробуем получить позже
                                message_id_result = None
                            if trace is not None:
                                trace.record(
                                    step="act",
                                    name="telegram_delivery",
                                    status="success",
                                    metadata={
                                        "delivery": "enhanced",
                                        "chat_id": user_data.get("user_id"),
                                    },
                                )
                            # 🆕 Публикуем событие для координации агентов
                            try:
                                from observability.agent_coordinator import (
                                    EventType,
                                    publish_agent_event,
                                )

                                publish_agent_event(
                                    event_type=EventType.SIGNAL_GENERATED,
                                    agent="signal_live",
                                    data={
                                        "symbol": symbol,
                                        "signal_type": signal_type,
                                        "price": signal_price,
                                        "user_id": user_data.get("user_id"),
                                        "trade_mode": user_data.get("trade_mode"),
                                        "confidence": ai_confidence,
                                    },
                                )
                                logger.debug(
                                    "📡 [COORD] Событие SIGNAL_GENERATED опубликовано для %s",
                                    symbol,
                                )
                            except Exception as coord_exc:
                                logger.debug("⚠️ Ошибка координации: %s", coord_exc)
                        else:
                            logger.warning(
                                "⚠️ Не удалось отправить сигнал пользователю %s (enhanced)",
                                user_data.get("user_id"),
                            )
                            if trace is not None:
                                trace.record(
                                    step="act",
                                    name="telegram_delivery",
                                    status="error",
                                    metadata={
                                        "delivery": "enhanced",
                                        "chat_id": user_data.get("user_id"),
                                    },
                                )
                    else:
                        # Fallback на старую систему
                        # 🆕 Отправляем в оба бота (DEV и PROD)
                        result = await notify_user(
                            user_data.get("user_id"),
                            message,
                            reply_markup=keyboard,
                            _return_message=True,
                            _send_to_both_bots=True,
                        )
                        signal_sent_successfully = bool(result)  # 🆕 Сохраняем результат отправки
                        logger.info(
                            "📤 Сигнал отправлен в Telegram с кнопкой (fallback): %s", symbol
                        )
                        # Получаем message_id из результата
                        if isinstance(result, dict) and "message_id" in result:
                            message_id_result = result.get("message_id")
                        elif result:
                            message_id_result = None
                        if trace is not None:
                            trace.record(
                                step="act",
                                name="telegram_delivery",
                                status="success",
                                metadata={
                                    "delivery": "fallback",
                                    "chat_id": user_data.get("user_id"),
                                },
                            )

            except Exception as e:
                logger.error("❌ Ошибка отправки в Telegram: %s", e)
                # Логируем отправку как fallback
                logger.info("📤 Отправляем сигнал (fallback): %s", signal_data)
                message_id_result = None
                # 🔧 ИСПРАВЛЕНО: Не сбрасываем signal_sent_successfully, если сигнал уже был отправлен ранее
                if not signal_was_sent_earlier:
                    signal_sent_successfully = False  # 🆕 КРИТИЧНО: Устанавливаем False при ошибке только если сигнал не был отправлен ранее
                else:
                    logger.info(
                        "✅ [SEND_SIGNAL] %s %s: Ошибка отправки, но сигнал уже был отправлен ранее - сохраняем signal_sent_successfully=True",
                        symbol,
                        signal_type,
                    )
                if trace is not None:
                    trace.record(
                        step="act",
                        name="telegram_delivery",
                        status="error",
                        metadata={"error": str(e)},
                    )
        else:
            if sizing_audit["signal_token"] is None:
                sizing_audit["signal_price"] = signal_price
                sizing_audit["signal_token"] = f"offline-{int(time.time())}"
                _log_position_sizing_event(sizing_audit)
            logger.info("📤 Отправляем сигнал (Telegram отключен): %s", signal_data)
            message_id_result = None
            # 🔧 ИСПРАВЛЕНО: Не сбрасываем signal_sent_successfully, если сигнал уже был отправлен ранее
            if not signal_was_sent_earlier:
                signal_sent_successfully = (
                    False  # 🆕 КРИТИЧНО: Telegram отключен = сигнал НЕ отправлен
                )
            else:
                logger.info(
                    "✅ [SEND_SIGNAL] %s %s: Telegram отключен, но сигнал уже был отправлен ранее - сохраняем signal_sent_successfully=True",
                    symbol,
                    signal_type,
                )
            if trace is not None:
                trace.record(
                    step="act",
                    name="delivery_skipped",
                    metadata={"reason": "telegram_disabled"},
                )

        # 4. 🆕 СОХРАНЕНИЕ СИГНАЛА В БАЗУ ДАННЫХ (для ВСЕХ режимов)
        # Сохраняем сигнал при отправке, НЕ открывая позицию на бирже
        logger.info(
            "💾 [DB SAVE START] Начало сохранения сигнала %s %s в БД (price=%.8f, user=%s)",
            symbol,
            signal_type,
            signal_price,
            user_data.get("user_id"),
        )

        try:
            user_id_str = str(user_data.get("user_id", ""))
            chat_id_int = (
                int(user_data.get("user_id", 0)) if user_id_str and user_id_str.isdigit() else None
            )

            logger.info(
                "💾 [DB SAVE DEBUG] user_id_str=%s, chat_id_int=%s, message_id_result=%s, signal_sent=%s",
                user_id_str,
                chat_id_int,
                message_id_result,
                signal_sent_successfully,
            )

            # Сохранение в accepted_signals через signal_acceptance_manager
            if SIGNAL_ACCEPTANCE_AVAILABLE and signal_acceptance_manager:
                try:
                    from src.signals.acceptance_manager import SignalData

                    signal_data_obj = SignalData(
                        symbol=symbol,
                        direction=signal_type,
                        entry_price=signal_price,
                        signal_time=get_utc_now(),
                        user_id=user_id_str,
                        chat_id=chat_id_int,
                        message_id=message_id_result,
                        status="pending",  # Статус pending до принятия
                    )

                    # 🔧 УЛУЧШЕНО: Сохраняем даже если message_id нет (fallback сохранение)
                    if message_id_result and chat_id_int:
                        logger.info(
                            "💾 [DB SAVE] Сохранение в accepted_signals с message_id=%s, chat_id=%s",
                            message_id_result,
                            chat_id_int,
                        )
                        await signal_acceptance_manager.register_signal(
                            signal_data_obj, message_id_result, chat_id_int
                        )
                        logger.info(
                            "✅ [DB SAVE SUCCESS] Сигнал %s сохранен в accepted_signals (status: pending, message_id=%s)",
                            symbol,
                            message_id_result,
                        )
                    elif chat_id_int:
                        # Сохраняем без message_id (fallback)
                        logger.warning(
                            "⚠️ [DB SAVE] Сохранение БЕЗ message_id (message_id=%s, chat_id=%s) - используем fallback",
                            message_id_result,
                            chat_id_int,
                        )
                        signal_data_obj.message_id = None  # Обнуляем message_id
                        await signal_acceptance_manager.register_signal(
                            signal_data_obj,
                            None,  # message_id = None
                            chat_id_int,
                        )
                        logger.info(
                            "✅ [DB SAVE SUCCESS] Сигнал %s сохранен в accepted_signals БЕЗ message_id (fallback)",
                            symbol,
                        )
                    else:
                        logger.error(
                            "❌ [DB SAVE FAILED] Невозможно сохранить %s: chat_id_int=%s, message_id=%s, user_id_str=%s",
                            symbol,
                            chat_id_int,
                            message_id_result,
                            user_id_str,
                        )
                        logger.error(
                            "❌ [DB SAVE FAILED] Детали: user_data.user_id=%s, signal_sent=%s",
                            user_data.get("user_id"),
                            signal_sent_successfully,
                        )

                except Exception as e:
                    logger.error(
                        "❌ [DB SAVE ERROR] Ошибка сохранения %s в accepted_signals: %s",
                        symbol,
                        e,
                        exc_info=True,
                    )
                    import traceback

                    logger.error("❌ [DB SAVE ERROR] Traceback: %s", traceback.format_exc())
            else:
                logger.warning(
                    "⚠️ [DB SAVE] Signal acceptance manager недоступен (SIGNAL_ACCEPTANCE_AVAILABLE=%s)",
                    SIGNAL_ACCEPTANCE_AVAILABLE,
                )

            # Сохранение в signals_log
            try:
                logger.info("💾 [DB SAVE] Начало сохранения %s в signals_log...", symbol)
                from src.database.db import Database  # type: ignore

                # Создаем локальный экземпляр Database для сохранения
                signal_db = Database()
                entry_time_str = get_utc_now().isoformat()
                # Получаем quality_score из параметров функции
                quality_score_value = quality_score if quality_score and quality_score > 0 else None
                quality_meta_value = None

                # Если quality_score не передан, пытаемся получить из df.attrs
                if (
                    quality_score_value is None
                    and hasattr(df, "attrs")
                    and "quality_score" in df.attrs
                ):
                    quality_score_value = df.attrs.get("quality_score")

                user_id_for_log = (
                    int(user_id_str) if user_id_str and user_id_str.isdigit() else None
                )
                logger.info(
                    "💾 [DB SAVE] Данные для signals_log: symbol=%s, entry=%.8f, user_id=%s, quality_score=%s",
                    symbol,
                    signal_price,
                    user_id_for_log,
                    quality_score_value,
                )

                signal_db.insert_signal_log_entry(
                    {
                        "symbol": symbol,
                        "entry": signal_price,
                        "stop": sl_price,
                        "tp1": tp1_price,
                        "tp2": tp2_price,
                        "direction": signal_type.upper(),
                        "entry_time": entry_time_str,
                        "exit_time": None,
                        "result": "PENDING",  # Статус PENDING до принятия
                        "net_profit": None,
                        "qty_added": None,
                        "qty_closed": None,
                        "user_id": user_id_for_log,
                        "quality_score": quality_score_value,  # Добавляем quality_score
                        "quality_meta": quality_meta_value,  # Добавляем quality_meta
                    }
                )
                logger.info(
                    "✅ [DB SAVE SUCCESS] Сигнал %s сохранен в signals_log (result: PENDING, entry_time=%s)",
                    symbol,
                    entry_time_str,
                )
            except Exception as e:
                logger.error(
                    "❌ [DB SAVE ERROR] Ошибка сохранения %s в signals_log: %s",
                    symbol,
                    e,
                    exc_info=True,
                )
                import traceback

                logger.error("❌ [DB SAVE ERROR] Traceback: %s", traceback.format_exc())

        except Exception as e:
            logger.error(
                "❌ [DB SAVE CRITICAL ERROR] Критическая ошибка сохранения сигнала %s в БД: %s",
                symbol,
                e,
                exc_info=True,
            )
            import traceback

            logger.error("❌ [DB SAVE CRITICAL ERROR] Полный traceback: %s", traceback.format_exc())

        # 5. СОХРАНЕНИЕ В ИСТОРИЮ РИСКОВ
        if CORRELATION_MANAGER_AVAILABLE and correlation_manager:
            try:
                await correlation_manager.save_signal_to_history_async(
                    symbol=symbol,
                    signal_type=signal_type,
                    user_id=user_data.get("user_id"),
                    signal_price=signal_price,
                    df=df,  # Передаем данные для расчета корреляции
                )
                logger.debug("💾 [CORRELATION] Сигнал %s сохранен в историю корреляции", symbol)
            except Exception as e:
                logger.error("❌ Ошибка сохранения в историю корреляции: %s", e)

        # 6. ОБНОВЛЕНИЕ СТАНДАРТНОЙ ИСТОРИИ
        signal_history.append(signal_data)

        # 7. SETUP TRAILING STOP И PARTIAL TP
        try:
            # Setup Trailing Stop
            if TRAILING_STOP_AVAILABLE and trailing_manager:
                trailing_manager.setup_position(
                    symbol=symbol,
                    entry_price=signal_price,
                    initial_sl=sl_price,
                    side=signal_type,
                    tp1_price=tp1_price,
                )
                logger.debug("🎯 [TRAILING] %s: trailing stop настроен", symbol)

            # Setup Partial Take Profit (только для позиций >= 50 USDT)
            if PARTIAL_TP_AVAILABLE and partial_manager and entry_amount_usdt >= 50:
                partial_manager.setup_partial_take_profit(
                    symbol=symbol,
                    entry_price=signal_price,
                    position_size_usdt=entry_amount_usdt,
                    tp1_price=tp1_price,
                    tp2_price=tp2_price,
                    side=signal_type,
                    regime=regime_data.get("regime", "NEUTRAL") if regime_data else "NEUTRAL",
                )
                logger.debug("🎯 [PARTIAL TP] %s: partial TP настроен", symbol)
        except Exception as e:
            logger.error("❌ Ошибка setup trailing/partial для %s: %s", symbol, e)

        # 8. 🆕 СОХРАНЕНИЕ ПАТТЕРНА ПРИ ОТПРАВКЕ (для обучения ИИ)
        # Это решает проблему "замкнутого круга" - паттерны сохраняются даже если сигнал не будет принят
        try:
            if AI_INTEGRATION_AVAILABLE and ai_integration:
                await ai_integration.record_signal_pattern_on_send(
                    symbol=symbol,
                    side=signal_type,
                    entry_price=signal_price,
                    tp1_price=tp1_price,
                    tp2_price=tp2_price,
                    risk_pct=risk_pct,
                    leverage=leverage,
                    user_id=user_data.get("user_id"),
                    df=df,
                )
                logger.debug("🤖 ИИ: Паттерн сохранен при отправке сигнала для %s", symbol)
        except Exception as e:
            logger.debug("⚠️ Ошибка сохранения паттерна при отправке: %s", e)

        # 9. УСПЕШНАЯ ОТПРАВКА - логируем только если сигнал реально отправлен
        if signal_sent_successfully:
            logger.info(
                "✅ [PRODUCTION] %s %s отправлен пользователю %s",
                symbol,
                signal_type,
                user_data.get("user_id", "N/A"),
            )
        else:
            logger.warning(
                "⚠️ [PRODUCTION] %s %s НЕ был отправлен пользователю %s (signal_sent_successfully=False)",
                symbol,
                signal_type,
                user_data.get("user_id", "N/A"),
            )

        # 10. 🆕 AUTO-МОД: при включённом auto — открываем позицию автоматически после отправки
        # ⚠️ ВАЖНО: Переменные entry_amount_usdt и leverage должны быть определены выше в функции
        # Если они не определены, используем значения из сообщения или дефолтные
        try:
            adb = AcceptanceDatabase()
            user_id_local = user_data.get("user_id")
            logger.info(
                "🔍 [AUTO CHECK] Начало проверки автоисполнения для %s (user_id=%s, signal_sent=%s, message_id=%s)",
                symbol,
                user_id_local,
                signal_sent_successfully,
                message_id_result,
            )

            if user_id_local:
                mode = await adb.get_user_mode(int(user_id_local))
                logger.info(
                    "🔍 [AUTO CHECK] %s: режим пользователя = %s (env=%s)", symbol, mode, ATRA_ENV
                )

                # DEV/TEST окружения всегда работают в ручном режиме, даже если в БД стоит auto.
                # Авто-исполнение разрешено только в prod, чтобы dev-бот никогда сам не открывал сделки на бирже.
                if ATRA_ENV != "prod":
                    logger.info(
                        "⏭️ [AUTO] %s: окружение=%s, авто-исполнение отключено (только manual, через /accept)",
                        symbol,
                        ATRA_ENV,
                    )
                    return

                if mode == "auto":
                    logger.info(
                        "🔍 [AUTO CHECK] %s: режим пользователя = auto, проверяем условия автоисполнения",
                        symbol,
                    )
                    # 🛡️ КРИТИЧЕСКАЯ ПРОВЕРКА: Если сигнал НЕ был отправлен в Telegram, НЕ открываем позицию автоматически
                    # Проверяем, был ли сигнал успешно отправлен (переменная signal_sent_successfully должна быть установлена выше)
                    logger.debug(
                        "🔍 [AUTO CHECK] %s: signal_sent_successfully = %s, message_id_result = %s",
                        symbol,
                        signal_sent_successfully,
                        message_id_result,
                    )
                    if not signal_sent_successfully:
                        logger.warning(
                            "🚫 [AUTO_BLOCK] %s для user %s: Автоисполнение ЗАБЛОКИРОВАНО - сигнал НЕ был отправлен в Telegram "
                            "(notify_user вернул False/None, signal_sent_successfully=%s, message_id=%s). "
                            "Позиция НЕ будет открыта автоматически.",
                            symbol,
                            user_id_local,
                            signal_sent_successfully,
                            message_id_result,
                        )
                        return  # Блокируем автоисполнение, если сигнал не был отправлен
                    logger.info(
                        "✅ [AUTO CHECK] %s: сигнал успешно отправлен (signal_sent_successfully=True), продолжаем автоисполнение",
                        symbol,
                    )

                    # 🛡️ ПРОВЕРКА: Если биржа не подключена (нет ключей), пропускаем автоматическое открытие
                    keys = await adb.get_active_exchange_keys(int(user_id_local), "bitget")
                    if not keys or len(keys) == 0:
                        logger.info(
                            "⏭️ [AUTO] %s: Пропущено автоматическое открытие для пользователя %s "
                            "(биржа не подключена - нет ключей API, ручной режим)",
                            symbol,
                            user_id_local,
                        )
                        return  # Пропускаем автоисполнение, сигнал уже отправлен пользователю

                    # 🛡️ ПОЛУЧАЕМ ПЕРЕМЕННЫЕ: Используем переменные, определенные в начале функции
                    # Эти переменные должны быть установлены выше в коде (в блоке расчета параметров)
                    actual_entry_amount = entry_amount_usdt
                    actual_leverage = leverage
                    actual_trade_mode = (
                        trade_mode if trade_mode else user_data.get("trade_mode", "futures")
                    )
                    actual_sl_price = sl_price
                    actual_tp1_price = tp1_price
                    actual_tp2_price = tp2_price

                    # Если переменные не были установлены выше, используем fallback
                    if actual_entry_amount is None or actual_entry_amount <= 0:
                        deposit = user_data.get("deposit", 1000.0)
                        risk_pct = user_data.get("risk_pct", 2.0)
                        actual_entry_amount = deposit * (risk_pct / 100)
                        logger.warning(
                            "⚠️ [AUTO] %s: entry_amount_usdt не установлена выше, используем расчет: %.2f USDT",
                            symbol,
                            actual_entry_amount,
                        )

                    if actual_leverage is None or actual_leverage <= 0:
                        actual_leverage = (
                            user_data.get("leverage", 1.9)
                            if actual_trade_mode == "futures"
                            else 1.0
                        )
                        logger.warning(
                            "⚠️ [AUTO] %s: leverage не установлена выше, используем значение из user_data: %.1fx",
                            symbol,
                            actual_leverage,
                        )

                    if actual_trade_mode is None:
                        actual_trade_mode = user_data.get("trade_mode", "futures")

                    # Нормализуем значения
                    actual_entry_amount = float(actual_entry_amount)
                    actual_leverage = float(actual_leverage)

                    logger.info(
                        "🤖 [AUTO] %s: запуск автоисполнения для user %s", symbol, user_id_local
                    )
                    logger.info(
                        "🤖 [AUTO] %s: параметры - баланс=%.2f, сумма=%.2f USDT, плечо=%.1fx, цена=%.8f, режим=%s",
                        symbol,
                        user_data.get("deposit", 1000.0),
                        actual_entry_amount,
                        actual_leverage,
                        signal_price,
                        actual_trade_mode,
                    )

                    try:
                        from src.execution.auto_execution import AutoExecutionService

                        auto_exec = AutoExecutionService(adb)

                        # Получаем баланс пользователя
                        user_balance = user_data.get("deposit", 1000.0)

                        # 🚫 ПРОВЕРКА: В spot режиме SHORT недоступен
                        if actual_trade_mode == "spot" and signal_type.upper() == "SHORT":
                            logger.warning(
                                "❌ [AUTO] %s: SHORT сигнал заблокирован для spot режима (доступен только LONG)",
                                symbol,
                            )
                            return  # Пропускаем автоисполнение, сигнал уже отправлен

                        logger.info(
                            "🤖 [AUTO] %s: Вызов execute_and_open... (сумма=%.2f USDT, плечо=%dx)",
                            symbol,
                            actual_entry_amount,
                            actual_leverage,
                        )
                        success = await auto_exec.execute_and_open(
                            symbol=symbol,
                            direction=signal_type,
                            entry_price=signal_price,
                            user_id=int(user_id_local),
                            message_id=None,
                            chat_id=None,
                            signal_key=None,
                            quantity_usdt=actual_entry_amount,
                            user_balance=user_balance,
                            current_exposure=0.0,
                            leverage=actual_leverage,
                            sl_price=actual_sl_price,  # Передаём реальный SL
                            tp1_price=actual_tp1_price,  # Передаём TP1
                            tp2_price=actual_tp2_price,  # Передаём TP2
                            trade_mode=actual_trade_mode,  # Передаём режим торговли
                        )

                        if success:
                            logger.info("✅ [AUTO] %s успешно открыт автоматически", symbol)
                            # Проверяем, что позиция действительно открыта
                            try:
                                positions = await adb.get_active_positions_by_user(
                                    str(user_id_local)
                                )
                                if any(
                                    p.get("symbol", "").upper() == symbol.upper() for p in positions
                                ):
                                    logger.info("✅ [AUTO] %s: Позиция подтверждена в БД", symbol)
                                else:
                                    logger.warning(
                                        "⚠️ [AUTO] %s: Позиция не найдена в БД после открытия! Проверьте логи auto_execution.",
                                        symbol,
                                    )
                            except Exception as pos_check_exc:
                                logger.debug(
                                    "⚠️ [AUTO] %s: Ошибка проверки позиции в БД: %s",
                                    symbol,
                                    pos_check_exc,
                                )
                        else:
                            logger.warning(
                                "❌ [AUTO] %s не удалось открыть автоматически. Проверьте логи auto_execution для деталей.",
                                symbol,
                            )

                    except Exception as e:
                        logger.error(
                            "❌ [AUTO] Ошибка автоисполнения %s: %s", symbol, e, exc_info=True
                        )
                else:
                    logger.info(
                        "👤 [MANUAL] %s: пользователь в ручном режиме (mode=%s) - авто-исполнение НЕ будет вызвано",
                        symbol,
                        mode,
                    )
            else:
                logger.warning("⚠️ [AUTO CHECK] user_id отсутствует в user_data для %s", symbol)
        except Exception as e:
            logger.error("❌ AUTO mode check error для %s: %s", symbol, e, exc_info=True)

        # 🔧 ИСПРАВЛЕНО: Логируем успех только если сигнал реально был отправлен
        if signal_sent_successfully:
            logger.info(
                "✅ [SEND_SIGNAL SUCCESS] %s %s: Сигнал успешно отправлен пользователю %s (источник: send_signal в signal_live.py)",
                symbol,
                signal_type,
                user_data.get("user_id"),
            )
            if trace is not None:
                trace.finish(status="success")
        else:  # pylint: disable=unreachable
            logger.warning(
                "⚠️ [SEND_SIGNAL FAILED] %s %s: Сигнал НЕ был отправлен пользователю %s (signal_sent_successfully=False)",
                symbol,
                signal_type,
                user_data.get("user_id"),
            )
            if trace is not None:
                trace.finish(status="error", metadata={"reason": "not_sent"})

        # 🔧 ИСПРАВЛЕНО: Возвращаем True только если сигнал реально был отправлен
        return signal_sent_successfully
    except Exception as e:
        logger.error(
            "❌ [SEND_SIGNAL ERROR] КРИТИЧЕСКАЯ ОШИБКА в send_signal для %s %s: %s",
            symbol,
            signal_type,
            e,
        )
        import traceback

        logger.error("Traceback: %s", traceback.format_exc())
        # Не делаем fallback, чтобы не отправлять рискованные сигналы
        return False


def is_signal_already_sent(symbol: str, user_id: str, signal_history: List[Dict[str, Any]]) -> bool:
    """Проверка истории сигналов"""
    try:
        for signal in signal_history:
            if (
                signal.get("symbol") == symbol
                and signal.get("user_id") == user_id
                and time.time() - signal.get("timestamp", 0) < 300
            ):  # 5 минут
                logger.debug(
                    "🚫 Сигнал для %s уже был отправлен пользователю %s недавно.", symbol, user_id
                )
                return True
        return False
    except Exception as e:
        logger.error("Ошибка проверки истории сигналов: %s", e)
        return False


def check_ai_volume_filter(df: pd.DataFrame, ai_params: Dict[str, Any]) -> bool:
    """ИИ-оптимизированный фильтр по объему (с адаптивной регуляцией)."""
    if "volume" not in df.columns or df.empty:
        return False

    # Базовый порог по объему (в USD или единицах)
    min_volume_base = 10
    current_volume = df["volume"].iloc[-1]

    # 🆕 ИСПОЛЬЗУЕМ АДАПТИВНЫЙ VOLUME RATIO
    passed = True
    reason = None

    if ADAPTIVE_REGULATOR_AVAILABLE and get_adaptive_regulator:
        try:
            regulator = get_adaptive_regulator()
            # Получаем адаптивный порог ratio
            adaptive_ratio = regulator.get_adaptive_volume_ratio(
                df=df,
                market_volatility=float(df["volatility"].iloc[-1])
                if "volatility" in df.columns
                else None,
                filter_mode="soft",  # По умолчанию используем soft для объема
            )

            # Проверяем текущий volume_ratio против адаптивного порога
            if "volume_ratio" in df.columns:
                current_ratio = float(df["volume_ratio"].iloc[-1])
                if current_ratio < adaptive_ratio:
                    passed = False
                    reason = f"Adaptive Volume Ratio {current_ratio:.2f} < {adaptive_ratio:.2f}"

        except Exception as e:
            logger.debug("⚠️ Ошибка адаптивного фильтра объема: %s", e)

    # Fallback на базовый объем, если адаптивный прошел или недоступен
    if passed and current_volume < min_volume_base:
        passed = False
        reason = f"Volume {current_volume:.0f} < {min_volume_base:.0f}"

    # Логируем для диагностики
    if passed:
        logger.debug(
            "📊 [VOLUME PASS] %s: объем %.0f в норме",
            df.attrs.get("symbol", "UNKNOWN") if hasattr(df, "attrs") else "UNKNOWN",
            current_volume,
        )
    else:
        logger.debug(
            "📊 [VOLUME BLOCK] %s: %s",
            df.attrs.get("symbol", "UNKNOWN") if hasattr(df, "attrs") else "UNKNOWN",
            reason,
        )

    # Логируем результат в БД
    try:
        from src.utils.filter_logger import log_filter_check_async

        symbol = df.attrs.get("symbol", "UNKNOWN") if hasattr(df, "attrs") else "UNKNOWN"
        # asyncio.create_task(log_filter_check_async(
        #     symbol=symbol,
        #     filter_type='ai_volume',
        #     passed=passed,
        #     reason=reason
        # ))
    except (ImportError, Exception):
        pass

    return passed


async def check_ml_filter(
    symbol: str,
    signal_type: str,
    entry_price: float,
    df: pd.DataFrame,
    quality_score: float = 0.5,
    mtf_score: float = 0.5,
    tp1: float = None,
    tp2: float = None,
    risk_pct: float = 2.0,
    leverage: float = 1.0,
    regime_data: Dict[str, Any] = None,
) -> Tuple[bool, Optional[str], Optional[Dict[str, float]]]:
    """
    Проверяет сигнал через LightGBM ML модель (классификация + регрессия)

    Args:
        symbol: Торговый символ
        signal_type: Тип сигнала (BUY/SELL)
        entry_price: Цена входа
        df: DataFrame с OHLCV данными
        quality_score: Оценка качества сигнала
        mtf_score: Мультитаймфреймовая оценка
        tp1: Цена первого тейк-профита
        tp2: Цена второго тейк-профита
        risk_pct: Процент риска
        leverage: Плечо
        regime_data: Данные о рыночном режиме

    Returns:
        Tuple[bool, Optional[str], Optional[Dict]]:
        (passed, reason, prediction_dict) - True если ML фильтр пройден
    """
    # 🔧 ВРЕМЕННО ОТКЛЮЧАЕМ ML ФИЛЬТР ДЛЯ ТЕСТИРОВАНИЯ
    # TODO: Включить обратно после исправления проблем с prob=0.01%
    USE_ML_FILTER = True  # 🔧 ТЕСТ: включен для объяснимости факторов ИИ

    if not USE_ML_FILTER:
        logger.info("🔧 [ML CHECK] %s: ML фильтр ВРЕМЕННО ОТКЛЮЧЕН для тестирования", symbol)
        return True, "ML_DISABLED_FOR_TESTING", None

    if not LIGHTGBM_AVAILABLE or not lightgbm_predictor:
        logger.debug(
            "🔍 [ML CHECK] ML фильтр отключен: LIGHTGBM_AVAILABLE=%s, predictor=%s",
            LIGHTGBM_AVAILABLE,
            lightgbm_predictor is not None,
        )
        return True, "ML_DISABLED", None

    if not lightgbm_predictor.is_trained:
        logger.warning(
            "⚠️ [ML CHECK] Модель не обучена: is_trained=%s. "
            "Проверьте: 1) Обучены ли модели (python train_lightgbm_models.py), "
            "2) Загружены ли модели из ai_learning_data/lightgbm_models/",
            lightgbm_predictor.is_trained,
        )
        return True, "ML_NOT_TRAINED", None

    try:
        # Собираем индикаторы
        indicators = {}
        if "rsi" in df.columns:
            indicators["rsi"] = float(df["rsi"].iloc[-1])
        if "ema_fast" in df.columns:
            indicators["ema_fast"] = float(df["ema_fast"].iloc[-1])
        if "ema_slow" in df.columns:
            indicators["ema_slow"] = float(df["ema_slow"].iloc[-1])
        if "macd" in df.columns:
            indicators["macd"] = float(df["macd"].iloc[-1])
        if "bb_upper" in df.columns:
            indicators["bb_upper"] = float(df["bb_upper"].iloc[-1])
        if "bb_lower" in df.columns:
            indicators["bb_lower"] = float(df["bb_lower"].iloc[-1])
        if "bb_mid" in df.columns:
            indicators["bb_mid"] = float(df["bb_mid"].iloc[-1])
        if "atr" in df.columns:
            indicators["atr"] = float(df["atr"].iloc[-1])
        if "adx" in df.columns:
            indicators["adx"] = float(df["adx"].iloc[-1])

        # Собираем рыночные условия
        market_conditions = {}

        # BTC trend (из smart_rsi context или других источников)
        smart_rsi_ctx = df.attrs.get("smart_rsi", {})
        if isinstance(smart_rsi_ctx, dict):
            market_conditions["btc_trend"] = smart_rsi_ctx.get("btc_alignment", False)
        else:
            market_conditions["btc_trend"] = False

        # Volume ratio
        if "volume_ratio" in df.columns:
            market_conditions["volume_ratio"] = float(df["volume_ratio"].iloc[-1])
        else:
            # Рассчитываем volume_ratio
            if "volume" in df.columns and len(df) > 20:
                avg_volume = df["volume"].iloc[-20:].mean()
                current_volume = df["volume"].iloc[-1]
                market_conditions["volume_ratio"] = (
                    float(current_volume / avg_volume) if avg_volume > 0 else 1.0
                )
            else:
                market_conditions["volume_ratio"] = 1.0

        # Volatility
        if "volatility" in df.columns:
            volatility_value = float(df["volatility"].iloc[-1])
            market_conditions["volatility"] = volatility_value
            # 🔍 ДИАГНОСТИКА: проверяем экстремальные значения
            if volatility_value > 0.5:
                logger.warning(
                    "⚠️ [ML VOLATILITY] %s: volatility очень высокий (%.4f)! Проверьте расчет.",
                    symbol,
                    volatility_value,
                )
        elif regime_data:
            volatility_pct = regime_data.get("volatility_pct", 0.0)
            market_conditions["volatility"] = float(volatility_pct)
            logger.debug(
                "📊 [ML VOLATILITY] %s: volatility из regime_data: %.4f", symbol, volatility_pct
            )
        else:
            market_conditions["volatility"] = 0.0
            logger.debug("📊 [ML VOLATILITY] %s: volatility = 0.0 (fallback)", symbol)

        # Market cap и liquidity (если доступны)
        market_conditions["market_cap"] = 0.0
        market_conditions["liquidity"] = 0.0

        # Параметры сигнала
        signal_params = {
            "entry_price": entry_price,
            "tp1": tp1 if tp1 else entry_price * 1.02,  # Дефолт 2%
            "tp2": tp2 if tp2 else entry_price * 1.04,  # Дефолт 4%
            "risk_pct": risk_pct,
            "leverage": leverage,
            "quality_score": quality_score,
            "mtf_score": mtf_score,
            "spread_pct": 0.0,  # Можно добавить реальный спред
            "depth_usd": 0.0,  # Можно добавить реальную глубину
        }

        # 🔧 ВЫЧИСЛЯЕМ LAG FEATURES ИЗ DataFrame (для правильной работы ML модели)
        # Это критично для работы модели, обученной с lag features
        historical_indicators = {}
        try:
            if len(df) >= 3:
                # RSI lags
                if "rsi" in df.columns:
                    rsi_current = float(df["rsi"].iloc[-1])
                    historical_indicators["rsi_lag_1"] = (
                        float(df["rsi"].iloc[-2]) if len(df) >= 2 else rsi_current
                    )
                    historical_indicators["rsi_lag_2"] = (
                        float(df["rsi"].iloc[-3]) if len(df) >= 3 else rsi_current
                    )
                    historical_indicators["rsi_lag_3"] = (
                        float(df["rsi"].iloc[-4]) if len(df) >= 4 else rsi_current
                    )

                # MACD lags
                if "macd" in df.columns:
                    macd_current = float(df["macd"].iloc[-1])
                    historical_indicators["macd_lag_1"] = (
                        float(df["macd"].iloc[-2]) if len(df) >= 2 else macd_current
                    )
                    historical_indicators["macd_lag_2"] = (
                        float(df["macd"].iloc[-3]) if len(df) >= 3 else macd_current
                    )
                    historical_indicators["macd_lag_3"] = (
                        float(df["macd"].iloc[-4]) if len(df) >= 4 else macd_current
                    )

                # Volume ratio lags
                if "volume_ratio" in df.columns:
                    vol_current = float(df["volume_ratio"].iloc[-1])
                    historical_indicators["volume_ratio_lag_1"] = (
                        float(df["volume_ratio"].iloc[-2]) if len(df) >= 2 else vol_current
                    )
                    historical_indicators["volume_change_1"] = (
                        vol_current - historical_indicators.get("volume_ratio_lag_1", vol_current)
                    )

                # Volatility lags
                if "volatility" in df.columns:
                    vol_current = float(df["volatility"].iloc[-1])
                    historical_indicators["volatility_lag_1"] = (
                        float(df["volatility"].iloc[-2]) if len(df) >= 2 else vol_current
                    )

                # Price changes
                if "close" in df.columns:
                    price_current = float(df["close"].iloc[-1])
                    price_lag_1 = float(df["close"].iloc[-2]) if len(df) >= 2 else price_current
                    price_lag_3 = float(df["close"].iloc[-4]) if len(df) >= 4 else price_current
                    if price_lag_1 > 0:
                        historical_indicators["price_change_1"] = (
                            price_current - price_lag_1
                        ) / price_lag_1
                    else:
                        historical_indicators["price_change_1"] = 0.0
                    if price_lag_3 > 0:
                        historical_indicators["price_change_3"] = (
                            price_current - price_lag_3
                        ) / price_lag_3
                    else:
                        historical_indicators["price_change_3"] = 0.0

                logger.info(
                    "✅ [ML LAG FEATURES] %s: Вычислены lag features из DataFrame: %s",
                    symbol,
                    list(historical_indicators.keys())[:10],
                )
        except Exception as e:
            logger.warning(
                "⚠️ [ML LAG FEATURES] %s: Ошибка вычисления lag features: %s (используем fallback)",
                symbol,
                e,
            )
            # Fallback: используем текущие значения
            if "rsi" in indicators:
                historical_indicators["rsi_lag_1"] = indicators["rsi"]
                historical_indicators["rsi_lag_2"] = indicators["rsi"]
                historical_indicators["rsi_lag_3"] = indicators["rsi"]
            if "macd" in indicators:
                historical_indicators["macd_lag_1"] = indicators["macd"]
                historical_indicators["macd_lag_2"] = indicators["macd"]
                historical_indicators["macd_lag_3"] = indicators["macd"]
            historical_indicators["price_change_1"] = 0.0
            historical_indicators["price_change_3"] = 0.0

        # 🔍 ДИАГНОСТИКА: логируем что передается в модель
        logger.debug(
            "🔍 [ML INPUT] %s %s: indicators_count=%d, indicators_keys=%s, "
            "market_conditions_keys=%s, signal_params_keys=%s, historical_indicators_count=%d",
            symbol,
            signal_type,
            len(indicators),
            list(indicators.keys())[:10],
            list(market_conditions.keys())[:10],
            list(signal_params.keys())[:10],
            len(historical_indicators),
        )

        # Делаем предсказание (передаем historical_indicators через pattern)
        ml_start_time = time.time()

        # Используем внутренний метод _extract_features для правильного извлечения features
        # Но predict принимает отдельные параметры, поэтому нужно модифицировать predict
        # Или передать historical_indicators через indicators/market_conditions

        # Временное решение: передаем historical_indicators через indicators
        indicators_with_history = indicators.copy()
        indicators_with_history["_historical"] = historical_indicators  # Временный ключ

        prediction = lightgbm_predictor.predict(
            market_conditions=market_conditions,
            indicators=indicators_with_history,
            signal_params=signal_params,
        )
        ml_duration = time.time() - ml_start_time

        # 📊 Записываем ML метрики (Елена)
        if PROMETHEUS_METRICS_AVAILABLE:
            try:
                record_ml_prediction(
                    symbol=symbol,
                    signal_type=signal_type,
                    probability=prediction.get("success_probability", 0.0),
                    expected_profit=prediction.get("expected_profit_pct", 0.0),
                    duration=ml_duration,
                )
            except Exception as e:
                logger.debug("⚠️ Failed to record ML metrics: %s", e)

        # 🔍 ДИАГНОСТИКА: если prob=0%, детальное логирование
        success_prob = prediction.get("success_probability", 0.0)
        if success_prob == 0.0 or success_prob < 0.01:
            indicators_sample = {k: v for k, v in list(indicators.items())[:5]}
            market_sample = {k: v for k, v in list(market_conditions.items())[:5]}
            params_sample = {k: v for k, v in list(signal_params.items())[:5]}
            logger.error(
                "❌ [ML ZERO PROB] %s %s: success_probability = %.6f (%.2f%%)%%. "
                "ДЕТАЛИ ВХОДНЫХ ДАННЫХ: indicators=%s, market_conditions=%s, signal_params=%s. "
                "ПРОВЕРЬТЕ: 1) Корректность извлечения features, 2) Совпадение названий features, 3) Модель обучена",
                symbol,
                signal_type,
                success_prob,
                success_prob * 100,
                indicators_sample,
                market_sample,
                params_sample,
            )

        # Логируем предсказание
        prob_pct_log = prediction["success_probability"] * 100
        logger.info(
            "🤖 [ML PREDICTION] %s %s: success_prob=%.2f pct, expected_profit=%.2f pct, combined_score=%.3f, recommendation=%s",
            symbol,
            signal_type,
            prob_pct_log,
            prediction["expected_profit_pct"],
            prediction["combined_score"],
            prediction["recommendation"],
        )

        # 🤖 ML ОПТИМИЗАЦИЯ ПОРОГОВ: Автоматическая оптимизация на основе исторических результатов
        try:
            from src.ai.filter_optimizer import get_filter_optimizer

            optimizer = get_filter_optimizer()
            metrics = await optimizer.get_recent_performance()
            optimized_thresholds = optimizer.optimize_ml_filter_thresholds(metrics)

            min_success_prob = optimized_thresholds.get("min_success_prob", 0.45)
            min_expected_profit = optimized_thresholds.get("min_expected_profit", 0.35)
            min_combined_score = optimized_thresholds.get("min_combined_score", 0.20)

            logger.info(
                "🤖 [ML_THRESHOLDS] %s: Используем адаптивные пороги: prob=%.2f, profit=%.2f%%, score=%.2f",
                symbol,
                min_success_prob,
                min_expected_profit,
                min_combined_score,
            )
        except Exception as e:
            logger.debug(
                "⚠️ [ML_THRESHOLDS] Ошибка оптимизации порогов, используем дефолтные: %s", e
            )
            min_success_prob = 0.45
            min_expected_profit = 0.35
            min_combined_score = 0.20

        # 📊 ДИАГНОСТИКА: проверяем, что вероятность в разумном диапазоне
        success_prob = prediction["success_probability"]
        if success_prob < 0.0 or success_prob > 1.0:
            logger.warning(
                "⚠️ [ML DIAGNOSTIC] %s: success_probability вне диапазона [0,1]: %.6f. "
                "Возможно проблема с моделью или features.",
                symbol,
                success_prob,
            )
            # Нормализуем к разумному значению
            success_prob = max(0.0, min(1.0, success_prob))
            prediction["success_probability"] = success_prob

        # 📊 ДИАГНОСТИКА: логируем детали, если prob = 0%
        if success_prob == 0.0 or success_prob < 0.01:
            prob_pct_warn = success_prob * 100
            # 🔧 FIX: показываем правильное количество features (15), а не len(indicators) (8)
            # lightgbm_predictor использует 15 features после _extract_features()
            actual_features_count = (
                len(lightgbm_predictor.feature_names)
                if lightgbm_predictor and hasattr(lightgbm_predictor, "feature_names")
                else 15
            )
            logger.warning(
                "⚠️ [ML DIAGNOSTIC] %s: success_probability = %.6f pct. "
                "Возможные причины: 1) модель считает сигнал очень плохим, "
                "2) features не совпадают с обучающими, 3) модель не обучена правильно. "
                "Features count: %d, Model is_trained: %s",
                symbol,
                prob_pct_warn,
                actual_features_count,
                lightgbm_predictor.is_trained if lightgbm_predictor else False,
            )
            # 🔧 FALLBACK: если prob = 0% и это выглядит подозрительно (слишком часто 0%),
            # лучше пропустить фильтр, чем заблокировать все сигналы
            # Для интрадей на крипторынке 0% часто означает проблему с моделью, а не реальную оценку
            if success_prob == 0.0:
                logger.warning(
                    "⚠️ [ML FALLBACK] %s: success_probability = 0.00 pct. "
                    "Это подозрительно низкое значение. Возможно проблема с моделью или features. "
                    "Используем более мягкий порог для проверки.",
                    symbol,
                )
                # 🔧 Используем более мягкий порог для случая 0%: проверяем только expected_profit
                # Если expected_profit > 0, позволяем сигнал (модель может быть неточной)
                if prediction["expected_profit_pct"] > 0.1:  # Если ожидаемая прибыль положительная
                    prob_val = prediction["success_probability"] * 100
                    logger.info(
                        "✅ [ML FALLBACK] %s: prob=0.00 pct, но expected_profit=%.2f pct > 0.1 pct. "
                        "Пропускаем сигнал (fallback для случая prob=0)",
                        symbol,
                        prediction["expected_profit_pct"],
                    )
                    passed = True
                    reason = f"ML_PASSED_FALLBACK (prob={prob_val:.2f}%, profit={prediction['expected_profit_pct']:.2f}%, fallback due to prob=0%)"
                    return passed, reason, prediction

        passed = (
            prediction["success_probability"] >= min_success_prob
            and prediction["expected_profit_pct"] >= min_expected_profit
            and prediction["combined_score"] >= min_combined_score
        )

        if passed:
            prob_pct_passed = prediction["success_probability"] * 100
            reason = f"ML_PASSED (prob={prob_pct_passed:.2f}%, profit={prediction['expected_profit_pct']:.2f}%)"
            # 📊 Записываем метрику принятия сигнала (Елена)
            if PROMETHEUS_METRICS_AVAILABLE:
                try:
                    record_signal_accepted(symbol=symbol, signal_type=signal_type)
                except Exception:
                    pass
        else:
            prob_pct_blocked = prediction["success_probability"] * 100
            reason = f"ML_BLOCKED (prob={prob_pct_blocked:.2f}%, profit={prediction['expected_profit_pct']:.2f}%, score={prediction['combined_score']:.3f})"
            # 📊 Записываем метрику отклонения сигнала (Елена)
            if PROMETHEUS_METRICS_AVAILABLE:
                try:
                    record_signal_rejected(
                        symbol=symbol, signal_type=signal_type, reason="ML_BLOCKED"
                    )
                except Exception:
                    pass

        # Логируем результат ML фильтра в БД
        try:
            from src.utils.filter_logger import log_filter_check_async
            # asyncio.create_task(log_filter_check_async(
            #     symbol=symbol,
            #     filter_type='ml_filter',
            #     passed=passed,
            #     reason=reason if not passed else None
            # ))
        except (ImportError, Exception):
            pass  # Логирование недоступно, продолжаем

        return passed, reason, prediction

    except Exception as e:
        logger.error("❌ Ошибка ML фильтра для %s: %s", symbol, e, exc_info=True)
        # При ошибке пропускаем сигнал (fail-safe)
        return True, f"ML_ERROR: {str(e)}", None


async def check_new_filters(
    symbol: str, signal_type: str, entry_price: float, df: pd.DataFrame, strict_mode: bool = True
) -> Tuple[bool, Optional[str]]:
    """
    Проверяет новые фильтры: Dominance Trend, Interest Zone, Fibonacci, Volume Imbalance

    Args:
        symbol: Торговый символ
        signal_type: Тип сигнала (BUY/SELL)
        entry_price: Цена входа
        df: DataFrame с OHLCV данными
        strict_mode: Режим строгости (True - строгий, False - мягкий)

    Returns:
        Tuple[bool, Optional[str]]: (passed, reason) - True если фильтры пройдены, False если заблокированы
    """
    if not NEW_FILTERS_AVAILABLE:
        return True, "FILTERS_DISABLED"

    # В мягком режиме часть фильтров может быть пропущена или ослаблена
    if not strict_mode:
        logger.debug(
            "🔓 [check_new_filters] %s: Используется МЯГКИЙ РЕЖИМ (ослабленная фильтрация)", symbol
        )

    signal_data_base = {
        "direction": signal_type,
        "symbol": symbol,
        "entry_price": entry_price,
        "df": df,
    }

    # Импортируем утилиту логирования
    try:
        from src.utils.filter_logger import log_filter_check_async

        LOGGING_AVAILABLE = True
    except ImportError:
        LOGGING_AVAILABLE = False

    # Проверка фильтра доминации BTC
    if dominance_filter:
        try:
            # 🔓 В МЯГКОМ РЕЖИМЕ пропускаем фильтр доминации
            if not strict_mode:
                logger.debug(
                    "🔓 [check_new_filters] %s: Пропускаем DominanceTrendFilter в мягком режиме",
                    symbol,
                )
            else:
                signal_data_for_filter = {k: v for k, v in signal_data_base.items() if k != "df"}
                dominance_result = await dominance_filter.filter_signal(signal_data_for_filter)

                # Логируем результат фильтра
                if LOGGING_AVAILABLE:
                    pass
                    # asyncio.create_task(log_filter_check_async(
                    #     symbol=symbol,
                    #     filter_type='dominance_trend',
                    #     passed=dominance_result.passed if hasattr(dominance_result, 'passed') else bool(dominance_result),
                    #     reason=dominance_result.reason if hasattr(dominance_result, 'reason') else None
                    # ))

                if not dominance_result:
                    return False, f"DominanceTrendFilter: {dominance_result.reason}"
        except Exception as e:
            logger.warning(
                "⚠️ Ошибка DominanceTrendFilter для %s: %s (пропускаем фильтр)", symbol, e
            )

    # Проверка фильтра зон интереса
    if interest_zone_filter:
        try:
            # 🔓 В МЯГКОМ РЕЖИМЕ пропускаем фильтр зон интереса
            if not strict_mode:
                logger.debug(
                    "🔓 [check_new_filters] %s: Пропускаем InterestZoneFilter в мягком режиме",
                    symbol,
                )
            else:
                interest_zone_result = await interest_zone_filter.filter_signal(signal_data_base)

                # Логируем результат фильтра
                if LOGGING_AVAILABLE:
                    pass
                    # asyncio.create_task(log_filter_check_async(
                    #     symbol=symbol,
                    #     filter_type='interest_zone',
                    #     passed=interest_zone_result.passed if hasattr(interest_zone_result, 'passed') else bool(interest_zone_result),
                    #     reason=interest_zone_result.reason if hasattr(interest_zone_result, 'reason') else None
                    # ))

                if not interest_zone_result:
                    return False, f"InterestZoneFilter: {interest_zone_result.reason}"
        except Exception as e:
            logger.warning("⚠️ Ошибка InterestZoneFilter для %s: %s (пропускаем фильтр)", symbol, e)

    # Проверка фильтра Фибоначчи
    if fibonacci_filter:
        try:
            fibonacci_result = await fibonacci_filter.filter_signal(signal_data_base)

            # Логируем результат фильтра
            if LOGGING_AVAILABLE:
                pass
                # asyncio.create_task(log_filter_check_async(
                #     symbol=symbol,
                #     filter_type='fibonacci_zone',
                #     passed=fibonacci_result.passed if hasattr(fibonacci_result, 'passed') else bool(fibonacci_result),
                #     reason=fibonacci_result.reason if hasattr(fibonacci_result, 'reason') else None
                # ))

            if not fibonacci_result:
                return False, f"FibonacciZoneFilter: {fibonacci_result.reason}"
        except Exception as e:
            logger.warning("⚠️ Ошибка FibonacciZoneFilter для %s: %s (пропускаем фильтр)", symbol, e)

    # Проверка фильтра имбалансов объема
    # 🔧 Проверяем флаг USE_VOLUME_IMBALANCE_FILTER перед проверкой фильтра
    if volume_imbalance_filter and USE_VOLUME_IMBALANCE_FILTER:
        logger.debug("🔧 [check_new_filters] Volume Imbalance фильтр ВКЛЮЧЕН, проверяем...")
    else:
        logger.debug(
            "🔧 [check_new_filters] Volume Imbalance фильтр ОТКЛЮЧЕН (filter=%s, flag=%s), пропускаем",
            volume_imbalance_filter is not None,
            USE_VOLUME_IMBALANCE_FILTER,
        )

    if volume_imbalance_filter and USE_VOLUME_IMBALANCE_FILTER:
        try:
            volume_imbalance_result = await volume_imbalance_filter.filter_signal(signal_data_base)

            # Логируем результат фильтра
            if LOGGING_AVAILABLE and volume_imbalance_result is not None:
                pass
                # asyncio.create_task(log_filter_check_async(
                #     symbol=symbol,
                #     filter_type='volume_imbalance',
                #     passed=volume_imbalance_result.passed if hasattr(volume_imbalance_result, 'passed') else bool(volume_imbalance_result),
                #     reason=volume_imbalance_result.reason if hasattr(volume_imbalance_result, 'reason') else None
                # ))

            # 🔧 ИСПРАВЛЕНО: FilterResult.__bool__ возвращает self.passed, поэтому проверяем is None явно
            if volume_imbalance_result is None:
                logger.warning(
                    "⚠️ [VolumeImbalance] %s: Фильтр вернул None (пропускаем проверку)", symbol
                )
            elif not volume_imbalance_result.passed:
                # Детальное логирование для диагностики
                details = volume_imbalance_result.details if volume_imbalance_result.details else {}
                volume_ratio = details.get("volume_ratio", 0)
                min_required = details.get("min_required", 1.2)
                reason = volume_imbalance_result.reason or "UNKNOWN"

                # Если volume_ratio = 0, пытаемся получить из imbalance_info
                if volume_ratio == 0 and "imbalance_info" in details:
                    imbalance_info = details.get("imbalance_info", {})
                    volume_ratio = imbalance_info.get("volume_ratio", 0)

                logger.info(
                    "📊 [VolumeImbalance] %s: Блокировка - ratio=%.3f, требуется=%.2f, причина=%s",
                    symbol,
                    volume_ratio if isinstance(volume_ratio, (int, float)) else 0,
                    min_required if isinstance(min_required, (int, float)) else 1.2,
                    reason,
                )
                return False, f"VolumeImbalanceFilter: {reason}"
        except Exception as e:
            logger.error(
                "❌ Ошибка VolumeImbalanceFilter для %s: %s (пропускаем фильтр)",
                symbol,
                e,
                exc_info=True,
            )
            # При ошибке разрешаем сигнал (graceful degradation)
            # Не возвращаем False, чтобы не блокировать сигнал из-за ошибки фильтра

    # Проверка Institutional Patterns фильтра (синхронный)
    if INSTITUTIONAL_PATTERNS_FILTER_AVAILABLE and check_institutional_patterns_filter:
        try:
            if USE_INSTITUTIONAL_PATTERNS_FILTER and len(df) > 0:
                i = len(df) - 1
                side = "long" if signal_type.upper() in ["BUY", "LONG"] else "short"
                min_quality = INSTITUTIONAL_PATTERNS_FILTER_CONFIG.get("min_quality_score", 0.6)

                ip_ok, ip_reason = check_institutional_patterns_filter(
                    df, i, side, strict_mode=strict_mode, min_quality_score=min_quality
                )

                if LOGGING_AVAILABLE:
                    pass
                    # asyncio.create_task(log_filter_check_async(
                    #     symbol=symbol,
                    #     filter_type='institutional_patterns',
                    #     passed=ip_ok,
                    #     reason=ip_reason
                    # ))

                if not ip_ok:
                    logger.info("📊 [InstitutionalPatterns] %s: Блокировка - %s", symbol, ip_reason)
                    return False, f"InstitutionalPatternsFilter: {ip_reason}"
        except Exception as e:
            logger.warning(
                "⚠️ Ошибка InstitutionalPatternsFilter для %s: %s (пропускаем фильтр)", symbol, e
            )

    return True, "ALL_FILTERS_PASSED"


async def check_all_trend_alignments(symbol: str, signal_type: str, df: Any = None) -> bool:
    """
    Проверяет соответствие сигнала трендам BTC, ETH и SOL

    🆕 УМНАЯ ЛОГИКА: Проверяет только релевантный тренд на основе корреляционной группы
    - Если монета в группе SOL_HIGH → проверяет только SOL тренд
    - Если монета в группе BTC_HIGH → проверяет только BTC тренд
    - Если монета в группе ETH_HIGH → проверяет только ETH тренд
    - Если группа не определена → проверяет все три тренда (fallback)

    Args:
        symbol: Торговый символ
        signal_type: Тип сигнала (BUY/SELL)
        df: DataFrame с данными (опционально, для определения корреляционной группы)

    Returns:
        True если сигнал соответствует тренду, False если нет
    """
    # 🆕 Используем SmartTrendFilter если доступен
    if SMART_TREND_FILTER_AVAILABLE and smart_trend_filter:
        try:
            return await smart_trend_filter.check_trend_alignment(symbol, signal_type, df)
        except Exception as e:
            logger.warning(
                "⚠️ [TREND_CHECK] %s: ошибка SmartTrendFilter: %s, используем fallback", symbol, e
            )
            # Fallback на старую логику

    # Fallback: проверяем все три тренда (старая логика)
    logger.debug(
        "⚠️ [TREND_CHECK] %s: SmartTrendFilter недоступен, проверяем все три тренда", symbol
    )

    # Проверка BTC (всегда активна)
    if not await check_btc_alignment(symbol, signal_type):
        return False

    # Проверка ETH (всегда активна)
    if not await check_eth_alignment(symbol, signal_type):
        return False

    # Проверка SOL (всегда активна)
    if not await check_sol_alignment(symbol, signal_type):
        return False

    return True


async def check_btc_alignment(symbol: str, signal_type: str) -> bool:
    """Проверяет соответствие сигнала тренду BTC"""
    try:
        # Получаем данные BTC через гибридный менеджер
        if not HYBRID_DATA_MANAGER_AVAILABLE or not HYBRID_DATA_MANAGER:
            return True  # Если менеджер недоступен, пропускаем проверку

        btc_df = await HYBRID_DATA_MANAGER.get_smart_data("BTCUSDT", "ohlc")

        # Проверяем тип данных и валидность
        if btc_df is None:
            logger.debug("⚠️ [%s] Нет данных BTC для проверки тренда (None)", symbol)
            return True  # Если данные недоступны, пропускаем проверку

        # Если это список словарей, конвертируем в DataFrame
        if isinstance(btc_df, list):
            if len(btc_df) == 0:
                logger.debug(
                    "⚠️ [%s] Данные BTC - пустой список, пропускаем проверку тренда", symbol
                )
                return True

            # Конвертируем список словарей в DataFrame
            try:
                btc_df = pd.DataFrame(btc_df)
                # Конвертируем timestamp в datetime если нужно
                if "timestamp" in btc_df.columns:
                    btc_df["timestamp"] = pd.to_datetime(
                        btc_df["timestamp"], unit="ms", errors="coerce"
                    )
                    btc_df.set_index("timestamp", inplace=True)
                logger.debug(
                    "✅ [%s] Данные BTC конвертированы из списка в DataFrame (%d строк)",
                    symbol,
                    len(btc_df),
                )
            except Exception as e:
                logger.warning("⚠️ [%s] Ошибка конвертации списка BTC в DataFrame: %s", symbol, e)
                return True

        # Проверяем, что это DataFrame и он не пустой
        if not isinstance(btc_df, pd.DataFrame):
            logger.debug(
                "⚠️ [%s] Данные BTC не являются DataFrame (тип: %s), пропускаем",
                symbol,
                type(btc_df),
            )
            return True

        if btc_df.empty or len(btc_df) < 50:
            logger.debug("⚠️ [%s] Нет данных BTC для проверки тренда (пусто или < 50 строк)", symbol)
            return True  # Если данные недоступны, пропускаем проверку

        # 🔧 ОСЛАБЛЕНО ДЛЯ ИНТРАДЕЙ: Используем более короткие EMA и допуск для быстрой реакции
        # Для интрадей используем EMA 10/22 (как в ETH/SOL) вместо 12/26 для более быстрой реакции
        ema_fast_period = 10  # Оптимизировано для интрадей
        ema_slow_period = 22  # Оптимизировано для интрадей

        btc_ema_fast = (
            btc_df["ema_fast"].iloc[-1]
            if "ema_fast" in btc_df.columns
            else btc_df["close"].ewm(span=ema_fast_period).mean().iloc[-1]
        )
        btc_ema_slow = (
            btc_df["ema_slow"].iloc[-1]
            if "ema_slow" in btc_df.columns
            else btc_df["close"].ewm(span=ema_slow_period).mean().iloc[-1]
        )

        # 🔧 Проверяем силу тренда (как в ETH/SOL)
        min_trend_strength = 0.002  # 0.2% - слабый тренд, разрешаем торговлю
        trend_strength = abs(btc_ema_fast - btc_ema_slow) / btc_ema_slow if btc_ema_slow > 0 else 0

        if trend_strength < min_trend_strength:
            # Слабый тренд (боковик) - разрешаем все сигналы
            logger.debug(
                "✅ [BTC FILTER] %s: слабый тренд (%.3f%% < %.3f%%) - разрешаем торговлю в боковике",
                symbol,
                trend_strength * 100,
                min_trend_strength * 100,
            )
            return True

        btc_trend = "BUY" if btc_ema_fast > btc_ema_slow else "SELL"

        # 🔧 Блокируем только сильные противотрендовые сигналы (> 1% разница)
        strong_trend_threshold = 0.01  # 1% - сильный тренд

        if signal_type == "BUY" and btc_trend == "SELL":
            if trend_strength > strong_trend_threshold:
                logger.warning(
                    "🚫 [BTC FILTER] %s: LONG против сильного BTC тренда (strength=%.3f%%) - блокируем",
                    symbol,
                    trend_strength * 100,
                )
                # Логируем блокировку
                try:
                    from src.utils.filter_logger import log_filter_check_async  # type: ignore
                    # asyncio.create_task(log_filter_check_async(
                    #     symbol=symbol,
                    #     filter_type='btc_trend',
                    #     passed=False,
                    #     reason=f"LONG против сильного BTC тренда (strength={trend_strength*100:.3f}%)"
                    # ))
                except (ImportError, Exception):
                    pass
                return False
            else:
                logger.debug(
                    "⚠️ [BTC FILTER] %s: LONG против слабого BTC тренда (strength=%.3f%%) - разрешаем",
                    symbol,
                    trend_strength * 100,
                )
                return True

        if signal_type == "SELL" and btc_trend == "BUY":
            if trend_strength > strong_trend_threshold:
                logger.warning(
                    "🚫 [BTC FILTER] %s: SHORT против сильного BTC тренда (strength=%.3f%%) - блокируем",
                    symbol,
                    trend_strength * 100,
                )
                # Логируем блокировку
                try:
                    from src.utils.filter_logger import log_filter_check_async  # type: ignore
                    # asyncio.create_task(log_filter_check_async(
                    #     symbol=symbol,
                    #     filter_type='btc_trend',
                    #     passed=False,
                    #     reason=f"SHORT против сильного BTC тренда (strength={trend_strength*100:.3f}%)"
                    # ))
                except (ImportError, Exception):
                    pass
                return False
            else:
                logger.debug(
                    "⚠️ [BTC FILTER] %s: SHORT против слабого BTC тренда (strength=%.3f%%) - разрешаем",
                    symbol,
                    trend_strength * 100,
                )
                return True

        logger.debug(
            "✅ [BTC FILTER] %s: тренд совпадает с BTC (%s, strength=%.3f%%)",
            symbol,
            btc_trend,
            trend_strength * 100,
        )

        # Логируем результат проверки BTC тренда
        try:
            from src.utils.filter_logger import log_filter_check_async
            # asyncio.create_task(log_filter_check_async(
            #     symbol=symbol,
            #     filter_type='btc_trend',
            #     passed=True,
            #     reason=None
            # ))
        except (ImportError, Exception):
            pass

        return True
    except Exception as e:
        logger.debug("⚠️ Ошибка проверки BTC тренда для %s: %s (пропускаем)", symbol, e)
        return True


def calculate_direction_confidence(
    df: pd.DataFrame,
    signal_type: str,
    trade_mode: str = "spot",
    filter_mode: str = "soft",
) -> bool:
    """Подсчитывает подтверждения по индикаторам.

    Для всех режимов требуем как минимум 3 из 4 подтверждений.
    Для строгого фильтра (`strict`) требуется 4/4.
    Параметр trade_mode используется только для логирования.
    """
    try:
        if df.empty or len(df) < 1:
            return False

        confirmations = 0

        if signal_type == "BUY":
            # Проверка 1: EMA Fast > EMA Slow
            if "ema_fast" in df.columns and "ema_slow" in df.columns:
                if df["ema_fast"].iloc[-1] > df["ema_slow"].iloc[-1]:
                    confirmations += 1
                    logger.debug("✅ [BUY CONFIRM] EMA alignment")

            # Проверка 2: Price > EMA Fast
            if "close" in df.columns and "ema_fast" in df.columns:
                if df["close"].iloc[-1] > df["ema_fast"].iloc[-1]:
                    confirmations += 1
                    logger.debug("✅ [BUY CONFIRM] Price above EMA")

            # Проверка 3: RSI < 55 (не перекуплен, смягчено для интрадей)
            if "rsi" in df.columns:
                rsi = df["rsi"].iloc[-1]
                if not pd.isna(rsi) and rsi < 55:
                    confirmations += 1
                    logger.debug("✅ [BUY CONFIRM] RSI %.1f < 55", rsi)

            # Проверка 4: MACD > MACD Signal
            if "macd" in df.columns and "macd_signal" in df.columns:
                macd = df["macd"].iloc[-1]
                macd_signal = df["macd_signal"].iloc[-1]
                if not pd.isna(macd) and not pd.isna(macd_signal) and macd > macd_signal:
                    confirmations += 1
                    logger.debug("✅ [BUY CONFIRM] MACD above signal")

        else:  # SELL
            # Проверка 1: EMA Fast < EMA Slow
            if "ema_fast" in df.columns and "ema_slow" in df.columns:
                if df["ema_fast"].iloc[-1] < df["ema_slow"].iloc[-1]:
                    confirmations += 1
                    logger.debug("✅ [SELL CONFIRM] EMA alignment")

            # Проверка 2: Price < EMA Fast
            if "close" in df.columns and "ema_fast" in df.columns:
                if df["close"].iloc[-1] < df["ema_fast"].iloc[-1]:
                    confirmations += 1
                    logger.debug("✅ [SELL CONFIRM] Price below EMA")

            # Проверка 3: RSI > 45 (не перепродан, смягчено для интрадей)
            if "rsi" in df.columns:
                rsi = df["rsi"].iloc[-1]
                if not pd.isna(rsi) and rsi > 45:
                    confirmations += 1
                    logger.debug("✅ [SELL CONFIRM] RSI %.1f > 45", rsi)

            # Проверка 4: MACD < MACD Signal
            if "macd" in df.columns and "macd_signal" in df.columns:
                macd = df["macd"].iloc[-1]
                macd_signal = df["macd_signal"].iloc[-1]
                if not pd.isna(macd) and not pd.isna(macd_signal) and macd < macd_signal:
                    confirmations += 1
                    logger.debug("✅ [SELL CONFIRM] MACD below signal")

        # ✅ ОСЛАБЛЕННЫЕ ТРЕБОВАНИЯ: для soft режима достаточно 2 из 4 подтверждений
        mode = (filter_mode or "").lower()
        if mode == "strict":
            min_confirmations = 4  # Строгий режим: все 4 подтверждения
        else:
            min_confirmations = 2  # ✅ ОСЛАБЛЕНО: было 3, стало 2 для soft режима
        result = confirmations >= min_confirmations
        if not result:
            # Детальное логирование отсутствующих проверок
            missing_checks = []
            if signal_type == "BUY":
                if (
                    "ema_fast" not in df.columns
                    or "ema_slow" not in df.columns
                    or df["ema_fast"].iloc[-1] <= df["ema_slow"].iloc[-1]
                ):
                    missing_checks.append("EMA alignment")
                if (
                    "close" not in df.columns
                    or "ema_fast" not in df.columns
                    or df["close"].iloc[-1] <= df["ema_fast"].iloc[-1]
                ):
                    missing_checks.append("Price > EMA")
                if (
                    "rsi" not in df.columns
                    or pd.isna(df["rsi"].iloc[-1])
                    or df["rsi"].iloc[-1] >= 55
                ):
                    missing_checks.append("RSI < 55")
                if "macd" not in df.columns or "macd_signal" not in df.columns:
                    missing_checks.append("MACD (колонки отсутствуют)")
                elif (
                    pd.isna(df["macd"].iloc[-1])
                    or pd.isna(df["macd_signal"].iloc[-1])
                    or df["macd"].iloc[-1] <= df["macd_signal"].iloc[-1]
                ):
                    missing_checks.append("MACD > Signal")
            else:  # SELL
                if (
                    "ema_fast" not in df.columns
                    or "ema_slow" not in df.columns
                    or df["ema_fast"].iloc[-1] >= df["ema_slow"].iloc[-1]
                ):
                    missing_checks.append("EMA alignment")
                if (
                    "close" not in df.columns
                    or "ema_fast" not in df.columns
                    or df["close"].iloc[-1] >= df["ema_fast"].iloc[-1]
                ):
                    missing_checks.append("Price < EMA")
                if (
                    "rsi" not in df.columns
                    or pd.isna(df["rsi"].iloc[-1])
                    or df["rsi"].iloc[-1] <= 45
                ):
                    missing_checks.append("RSI > 45")
                if "macd" not in df.columns or "macd_signal" not in df.columns:
                    missing_checks.append("MACD (колонки отсутствуют)")
                elif (
                    pd.isna(df["macd"].iloc[-1])
                    or pd.isna(df["macd_signal"].iloc[-1])
                    or df["macd"].iloc[-1] >= df["macd_signal"].iloc[-1]
                ):
                    missing_checks.append("MACD < Signal")

            logger.warning(
                "🚫 [DIRECTION CHECK] %s (%s): недостаточно подтверждений (%d/4, требуется %d). Отсутствуют: %s",
                signal_type,
                trade_mode,
                confirmations,
                min_confirmations,
                ", ".join(missing_checks) if missing_checks else "неизвестно",
            )
        else:
            logger.info(
                "✅ [DIRECTION CHECK] %s (%s): %d/4 подтверждений (требуется %d)",
                signal_type,
                trade_mode,
                confirmations,
                min_confirmations,
            )

        return result
    except Exception as e:
        logger.error("❌ Ошибка расчета направления для %s: %s", signal_type, e)
        return False


async def check_rsi_warning(df: pd.DataFrame, signal_type: str) -> bool:
    """Проверяет RSI c учетом контекста (умный фильтр + legacy режим)."""
    try:
        if "rsi" not in df.columns or df.empty:
            return True

        rsi_value = df["rsi"].iloc[-1]
        if pd.isna(rsi_value):
            return True

        ctx = df.attrs.get("smart_rsi", {})
        symbol = ctx.get("symbol", "UNKNOWN")
        group = ctx.get("ab_group", "B")
        btc_alignment = ctx.get("btc_alignment")
        if btc_alignment is None:
            btc_alignment = True

        # Для логирования преобразуем timestamp
        ts_raw = ctx.get("timestamp")
        try:
            ts_obj = datetime.fromisoformat(ts_raw) if ts_raw else get_utc_now()
        except (ValueError, TypeError):
            ts_obj = get_utc_now()

        log_entry = {
            "timestamp": ts_obj.isoformat(),
            "group": group,
            "symbol": symbol,
            "direction": signal_type,
            "rsi": round(float(rsi_value), 2),
            "decision": "pass",
            "reason": "legacy",
            "trend_strength": round(float(ctx.get("trend_strength", 0.0)), 2),
            "volume_ratio": round(float(ctx.get("volume_ratio", 1.0)), 2),
            "ai_confidence": round(float(ctx.get("ai_confidence", 0.0)), 2),
            "btc_alignment": btc_alignment,
            "adjustments": "",
        }

        if group != "A":
            # 🆕 УЛУЧШЕННАЯ ЛОГИКА: Адаптивные пороги (вместо фиксированных 70/30)
            rsi_long = 70.0
            rsi_short = 30.0

            if ADAPTIVE_REGULATOR_AVAILABLE and get_adaptive_regulator:
                try:
                    regulator = get_adaptive_regulator()
                    rsi_long, rsi_short = await regulator.get_adaptive_rsi_thresholds(
                        df=df,
                        market_volatility=float(df["volatility"].iloc[-1])
                        if "volatility" in df.columns
                        else None,
                        volume_ratio=float(df["volume_ratio"].iloc[-1])
                        if "volume_ratio" in df.columns
                        else None,
                    )
                    log_entry["reason"] = "adaptive"
                    log_entry["adjustments"] = {"rsi_long": rsi_long, "rsi_short": rsi_short}
                except Exception as e:
                    logger.debug("⚠️ Ошибка получения адаптивных RSI порогов: %s", e)

            if signal_type == "BUY" and rsi_value > rsi_long:
                ctx["decision"] = "reject"
                ctx["reason"] = f"Adaptive RSI {rsi_value:.1f} > {rsi_long:.1f}"
                ctx["adjustments"] = None
                log_entry["decision"] = "reject"
                log_entry["reason"] = ctx["reason"]
                _log_smart_rsi(log_entry)
                return False
            if signal_type == "SELL" and rsi_value < rsi_short:
                ctx["decision"] = "reject"
                ctx["reason"] = f"Adaptive RSI {rsi_value:.1f} < {rsi_short:.1f}"
                ctx["adjustments"] = None
                log_entry["decision"] = "reject"
                log_entry["reason"] = ctx["reason"]
                _log_smart_rsi(log_entry)
                return False

            # Проход по адаптивной логике
            ctx["decision"] = "pass"
            ctx["reason"] = f"Adaptive pass (L:{rsi_long:.1f}, S:{rsi_short:.1f})"
            ctx["adjustments"] = None
            log_entry["reason"] = ctx["reason"]
            _log_smart_rsi(log_entry)
            return True

        # Smart режим
        trend_strength = float(ctx.get("trend_strength", 0.0))
        volume_ratio = float(ctx.get("volume_ratio", 1.0))
        ai_confidence = float(ctx.get("ai_confidence", 0.0))

        # pylint: disable=too-many-function-args,unexpected-keyword-arg,no-value-for-parameter
        result = SMART_RSI_FILTER.evaluate(
            rsi=float(rsi_value),
            direction=signal_type,
            trend_strength=trend_strength,
            volume_ratio=volume_ratio,
            ai_confidence=ai_confidence,
            btc_alignment=btc_alignment,
        )

        ctx["decision"] = result["decision"]
        ctx["reason"] = result["reason"]
        ctx["adjustments"] = result["adjustments"]
        log_entry["decision"] = result["decision"]
        log_entry["reason"] = result["reason"]
        if result["adjustments"]:
            log_entry["adjustments"] = json.dumps(result["adjustments"])

        _log_smart_rsi(log_entry)

        passed = result["decision"] != "reject"

        # Логируем результат в БД
        try:
            from src.utils.filter_logger import log_filter_check_async

            symbol = ctx.get("symbol", "UNKNOWN")
            reason = None if passed else result.get("reason", "RSI не прошел проверку")
            # asyncio.create_task(log_filter_check_async(
            #     symbol=symbol,
            #     filter_type='rsi_warning',
            #     passed=passed,
            #     reason=reason
            # ))
        except (ImportError, Exception):
            pass  # Логирование недоступно, продолжаем

        return passed
    except Exception as e:
        logger.debug("⚠️ Ошибка проверки RSI для %s: %s (пропускаем)", signal_type, e)
        return True


def check_ai_volatility_filter(df: pd.DataFrame, ai_params: Dict[str, Any]) -> bool:
    """ИИ-оптимизированный фильтр по волатильности."""
    if "volatility" not in df.columns or df.empty:
        return False

    # Получаем параметры из ai_params
    # ВАЖНО: volatility в DataFrame уже в ПРОЦЕНТАХ (ATR / close * 100)
    # ai_params хранит в долях (0.005 = 0.5%), поэтому умножаем на 100
    min_volatility_pct = ai_params.get("min_volatility_pct", 0.005) * 100  # 0.005 → 0.5%
    max_volatility_pct = ai_params.get("max_volatility_pct", 0.15) * 100  # 0.15 → 15%
    current_volatility = df["volatility"].iloc[-1]

    logger.debug(
        "📊 Волатильность: текущая=%.2f%%, диапазон=[%.2f%%, %.2f%%]",
        current_volatility,
        min_volatility_pct,
        max_volatility_pct,
    )

    result = min_volatility_pct <= current_volatility <= max_volatility_pct

    if not result:
        logger.info(
            "❌ [%s] Волатильность ОТКЛОНЕНА: текущая=%.4f (%.2f%%), диапазон=[%.4f-%.4f] ([%.2f%%-%.2f%%])",
            df.get("symbol", ["N/A"])[0] if hasattr(df, "get") else "N/A",
            current_volatility,
            current_volatility * 100 if current_volatility < 1 else current_volatility,
            min_volatility_pct,
            max_volatility_pct,
            min_volatility_pct * 100 if min_volatility_pct < 1 else min_volatility_pct,
            max_volatility_pct * 100 if max_volatility_pct < 1 else max_volatility_pct,
        )

    # Логируем результат в БД
    try:
        from src.utils.filter_logger import log_filter_check_async

        symbol = df.attrs.get("symbol", "UNKNOWN") if hasattr(df, "attrs") else "UNKNOWN"
        reason = (
            None
            if result
            else f"Волатильность {current_volatility:.2f}% вне диапазона [{min_volatility_pct:.2f}%, {max_volatility_pct:.2f}%]"
        )
        # asyncio.create_task(log_filter_check_async(
        #     symbol=symbol,
        #     filter_type='ai_volatility',
        #     passed=result,
        #     reason=reason
        # ))
    except (ImportError, Exception):
        pass  # Логирование недоступно, продолжаем

    return result


async def send_with_retry(
    user_id: str, message: str, reply_markup=None, trace_id: str = None, max_retries: int = 3
) -> bool:
    """Отправка с retry логикой"""
    for attempt in range(max_retries):
        try:
            # Проверяем rate limiting
            await rate_limiter.wait_if_needed(user_id)

            # Отправляем сообщение
            success = await notify_user(user_id, message, reply_markup=reply_markup)
            if success:
                logger.info(
                    "✅ [%s] Сообщение отправлено (попытка %d/%d)",
                    trace_id,
                    attempt + 1,
                    max_retries,
                )
                return True
            else:
                logger.warning(
                    "⚠️ [%s] Попытка %d/%d неудачна, повторяем через %ds",
                    trace_id,
                    attempt + 1,
                    max_retries,
                    2**attempt,
                )
                await asyncio.sleep(2**attempt)  # Exponential backoff
        except Exception as e:
            logger.error(
                "❌ [%s] Ошибка отправки (попытка %d/%d): %s", trace_id, attempt + 1, max_retries, e
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(2**attempt)

    logger.error("❌ [%s] Все попытки отправки исчерпаны", trace_id)
    return False


async def send_with_retry_fallback(
    user_id: str, message: str, reply_markup=None, trace_id: str = None, max_retries: int = 2
) -> bool:
    """Fallback отправка с retry логикой"""
    for attempt in range(max_retries):
        try:
            await notify_user(user_id, message, reply_markup=reply_markup)
            logger.info(
                "✅ [%s] Fallback сообщение отправлено (попытка %d/%d)",
                trace_id,
                attempt + 1,
                max_retries,
            )
            return True
        except Exception as e:
            logger.error(
                "❌ [%s] Fallback ошибка (попытка %d/%d): %s", trace_id, attempt + 1, max_retries, e
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(1)

    logger.error("❌ [%s] Все fallback попытки исчерпаны", trace_id)
    return False


async def calculate_conf_signal(symbol: str) -> str:
    """
    Рассчитывает CONF (подтверждение) сигнала на основе крупных сделок с бирж.
    Логика взята из рабочей версии signal_live.py от 19 октября.
    """
    try:
        # Импортируем настройки CONF
        try:
            from config import CONF_MIN_THRESHOLD_USD

            _conf_min_threshold_usd = float(CONF_MIN_THRESHOLD_USD)
        except ImportError:
            _conf_min_threshold_usd = 5000.0

        # Получаем данные с бирж
        try:
            # Функции возвращают общий объем, делим пополам на buy/sell
            b_total = _binance_recent_notional(symbol)
            y_total = _bybit_recent_notional(symbol)
            o_total = _okx_recent_notional(symbol)
            k_total = _kucoin_recent_notional(symbol)

            # Делим пополам, предполагая равномерное распределение
            buy_notional = (b_total + y_total + o_total + k_total) / 2
            sell_notional = (b_total + y_total + o_total + k_total) / 2

            # Улучшенная логика CONF: более гибкие пороги (как в рабочей версии)
            min_conf = float(_conf_min_threshold_usd)
            effective_min_conf = max(100.0, min_conf * 0.1)  # Снижаем порог еще больше
            dyn_threshold = effective_min_conf

            total_window = buy_notional + sell_notional
            logger.info(
                "[CONF] %s: buy=%.0f, sell=%.0f, total=%.0f, threshold=%.0f",
                symbol,
                buy_notional,
                sell_notional,
                total_window,
                dyn_threshold,
            )

            if total_window >= dyn_threshold:
                # Более мягкие условия для определения направления (как в рабочей версии)
                logger.info(
                    "[CONF] %s: buy=%.0f, sell=%.0f, ratio=%.3f",
                    symbol,
                    buy_notional,
                    sell_notional,
                    buy_notional / sell_notional if sell_notional > 0 else 0,
                )
                if buy_notional >= sell_notional * 1.02:  # 2% разница
                    logger.info("[CONF] %s: БЫЧИЙ сигнал (buy >= sell * 1.02)", symbol)
                    return "🟢 ПОДТВЕРЖДЕНИЕ"
                elif sell_notional >= buy_notional * 1.02:  # 2% разница
                    logger.info("[CONF] %s: МЕДВЕЖИЙ сигнал (sell >= buy * 1.02)", symbol)
                    return "🔴 ПРОТИВОРЕЧИЕ"
                else:
                    logger.info("[CONF] %s: НЕЙТРАЛЬНО (разница < 2%%)", symbol)
                    return "⚪ НЕЙТРАЛЬНО"
            else:
                logger.info("[CONF] %s: недостаточный объем для подтверждения", symbol)
                return "⚪ НЕТ ДАННЫХ"

        except ImportError as e:
            logger.error("Ошибка импорта функций CONF: %s", e)
            return "⚪ НЕТ ДАННЫХ"

    except Exception as e:
        logger.error("Ошибка расчета CONF для %s: %s", symbol, e)
        return "⚪ НЕТ ДАННЫХ"


async def calculate_fvg_anomalies(symbol: str, signal_type: str = "LONG") -> str:
    """
    Рассчитывает FVG (Fair Value Gap) аномалии на основе объема и капитализации.
    Логика взята из рабочей версии signal_live.py от 19 октября.
    """
    try:
        # Рассчитываем аномалии (как в рабочей версии)
        try:
            (
                circles_count,
                activity_description,
                risk_display,
                data_ok,
            ) = await calculate_anomaly_circles_with_fallback(symbol, signal_type)

            logger.info(
                "[FVG] %s: circles=%s, activity=%s, risk=%s, data_ok=%s",
                symbol,
                circles_count,
                activity_description,
                risk_display,
                data_ok,
            )

            if data_ok and circles_count is not None:
                if circles_count > 0:
                    # Есть аномалии - определяем уровень активности
                    _ = get_anomaly_emoji(
                        circles_count / 5.0
                    )  # emoji - не используется в текущей версии

                    # Маппинг уровней активности (как в рабочей версии)
                    if circles_count >= 5:
                        activity_level = "МАКСИМАЛЬНАЯ АКТИВНОСТЬ"
                        color_emoji = "🔴"
                    elif circles_count >= 4:
                        activity_level = "КРИТИЧЕСКАЯ АКТИВНОСТЬ"
                        color_emoji = "🟠"
                    elif circles_count >= 3:
                        activity_level = "АНОМАЛЬНАЯ АКТИВНОСТЬ"
                        color_emoji = "🟠"
                    elif circles_count >= 2:
                        activity_level = "ВЫСОКАЯ АКТИВНОСТЬ"
                        color_emoji = "🟢"
                    else:  # circles_count == 1
                        activity_level = "ПОВЫШЕННАЯ АКТИВНОСТЬ"
                        color_emoji = "🟡"

                    logger.info(
                        "[FVG] %s: обнаружены аномалии уровня %d - %s",
                        symbol,
                        circles_count,
                        activity_level,
                    )
                    return f"{color_emoji} {activity_level}"
                else:
                    # Нет аномалий, но данные есть
                    logger.info("[FVG] %s: нет аномалий (нормальная активность)", symbol)
                    return "⚪ НОРМАЛЬНАЯ АКТИВНОСТЬ"
            else:
                # Нет данных для расчета
                logger.info("[FVG] %s: нет данных для расчета аномалий", symbol)
                return "⚪ НЕТ ДАННЫХ"

        except ImportError as e:
            logger.error("Ошибка импорта функций FVG: %s", e)
            return "⚪ НЕТ ДАННЫХ"

    except Exception as e:
        logger.error("Ошибка расчета FVG для %s: %s", symbol, e)
        return "⚪ НЕТ ДАННЫХ"


async def initialize_signal_acceptance_system():
    """
    Инициализирует систему принятия сигналов
    """
    try:
        if not SIGNAL_ACCEPTANCE_AVAILABLE:
            logger.warning("⚠️ Система принятия сигналов недоступна (модули не импортированы)")
            return False

        # Инициализируем компоненты системы принятия сигналов
        global signal_acceptance_manager

        try:
            acceptance_db = AcceptanceDatabase()
            logger.debug("✅ AcceptanceDatabase создана")
        except Exception as e:
            logger.error("❌ Ошибка создания AcceptanceDatabase: %s", e)
            return False

        try:
            telegram_updater = TelegramMessageUpdater()
            logger.debug("✅ TelegramMessageUpdater создан")
        except Exception as e:
            logger.error("❌ Ошибка создания TelegramMessageUpdater: %s", e)
            return False

        try:
            position_manager = ImprovedPositionManager(acceptance_db, telegram_updater)
            logger.debug("✅ ImprovedPositionManager создан")
        except Exception as e:
            logger.error("❌ Ошибка создания ImprovedPositionManager: %s", e)
            return False

        try:
            signal_acceptance_manager = SignalAcceptanceManager(
                acceptance_db, telegram_updater, position_manager
            )
            logger.debug("✅ SignalAcceptanceManager создан")
        except Exception as e:
            logger.error("❌ Ошибка создания SignalAcceptanceManager: %s", e)
            return False

        # Загружаем существующие сигналы
        try:
            await signal_acceptance_manager.load_existing_signals()
            logger.debug("✅ Существующие сигналы загружены")
        except Exception as e:
            logger.warning("⚠️ Ошибка загрузки существующих сигналов: %s", e)
            # Не критично, продолжаем работу

        logger.info("✅ Система принятия сигналов инициализирована")
        logger.info("✅ signal_acceptance_manager создан: %s", signal_acceptance_manager)
        return True

    except Exception as e:
        logger.error("❌ Критическая ошибка инициализации системы принятия сигналов: %s", e)
        import traceback

        logger.error("Трассировка: %s", traceback.format_exc())
        return False


async def _run_hybrid_signal_system_fixed_impl():
    """
    Основная функция для запуска исправленной гибридной системы сигналов.
    """
    logger.info("🚀 Запуск PRODUCTION системы с корреляционными рисками")

    # Redundant Telegram bot start removed. Bot is started by main.py or specialized entry point.
    logger.info("ℹ️ Резервный запуск Telegram бота пропущен (управление в main.py)")
    # Даем время на инициализацию систем
    await asyncio.sleep(1)

    # Инициализируем систему принятия сигналов
    try:
        await initialize_signal_acceptance_system()
        logger.info("✅ Система принятия сигналов инициализирована")
    except Exception as e:
        logger.error("❌ Ошибка инициализации системы принятия сигналов: %s", e)

    # Запускаем периодический health check для корреляций
    try:
        asyncio.create_task(periodic_health_check_correlations())
        logger.info("✅ Health check корреляций запущен")
    except Exception as e:
        logger.error("❌ Ошибка запуска health check корреляций: %s", e)

    # Запускаем мониторинг рисков портфеля
    try:
        asyncio.create_task(periodic_risk_monitoring())
        logger.info("✅ Мониторинг рисков портфеля запущен")
    except Exception as e:
        logger.error("❌ Ошибка запуска мониторинга рисков: %s", e)

    # 🏥 Запускаем систему Self-Healing (Автолечение)
    if SELF_HEALING_AVAILABLE and SelfHealingManager:
        try:
            sh_manager = SelfHealingManager()
            asyncio.create_task(sh_manager.monitor_health())
            logger.info("✅ Система Self-Healing запущена")
        except Exception as e:
            logger.error("❌ Ошибка запуска Self-Healing: %s", e)
    else:
        logger.warning("⚠️ Self-Healing недоступен, пропускаем")

    # 🛡️ Запускаем Stuck Position Monitor (ARS)
    if STUCK_MONITOR_AVAILABLE:
        try:
            # Получаем всех пользователей и запускаем монитор для каждого
            user_data_dict = await load_user_data()
            for user_id, _ in user_data_dict.items():
                try:
                    monitor = StuckPositionMonitor()
                    asyncio.create_task(monitor.run_monitor(int(user_id)))
                    logger.info(
                        "✅ [ARS] Монитор зависших сделок запущен для пользователя %s", user_id
                    )
                except Exception as e:
                    logger.error(
                        "❌ [ARS] Ошибка запуска монитора для пользователя %s: %s", user_id, e
                    )
        except Exception as e:
            logger.error("❌ [ARS] Ошибка запуска ARS: %s", e)
    else:
        logger.warning("⚠️ [ARS] StuckPositionMonitor недоступен, пропускаем")

    signal_history: List[Dict[str, Any]] = []
    cycle_count = 0

    while True:
        cycle_start_time = time.time()
        cycle_count += 1

        try:
            logger.info("🔍 Цикл #%d: Начинаем оптимизированную проверку сигналов...", cycle_count)
            logger.debug(
                "🔍 [CYCLE DEBUG] Цикл #%d начат в %s",
                cycle_count,
                time.strftime("%Y-%m-%d %H:%M:%S"),
            )

            if RISK_FLAGS_AVAILABLE and risk_flags_manager:
                if risk_flags_manager.is_active("emergency_stop"):
                    logger.warning(
                        "🚫 Цикл #%d: emergency_stop активен, пропускаем генерацию сигналов.",
                        cycle_count,
                    )
                    await asyncio.sleep(60)
                    continue
                if risk_flags_manager.is_active("weak_setup_stop"):
                    logger.warning(
                        "🚫 Цикл #%d: weak_setup_stop активен, пропускаем генерацию сигналов.",
                        cycle_count,
                    )
                    await asyncio.sleep(60)
                    continue

            # 0. ОПРЕДЕЛЯЕМ РЫНОЧНЫЙ РЕЖИМ (для адаптации параметров)
            regime_data = None
            regime_multipliers = None
            if REGIME_DETECTOR_AVAILABLE and regime_detector:
                try:
                    # Получаем данные BTC для определения режима (с кешированием)
                    btc_data = await get_symbol_data("BTCUSDT", force_fresh=False)
                    if btc_data is None:
                        # Fallback: прямой доступ к API
                        if get_ohlc_with_fallback is None:
                            logger.error("❌ get_ohlc_with_fallback недоступен для BTCUSDT")
                            btc_data = None
                        else:
                            btc_data = await get_ohlc_with_fallback("BTCUSDT", "1h", limit=250)

                    # Проверяем наличие данных и их валидность (исправлено: не используем DataFrame в булевом контексте)
                    btc_df = None
                    if btc_data is not None:
                        if isinstance(btc_data, pd.DataFrame) and len(btc_data) >= 200:
                            btc_df = btc_data
                        elif isinstance(btc_data, list) and len(btc_data) >= 200:
                            btc_df = pd.DataFrame(btc_data)

                    if btc_df is not None and len(btc_df) >= 200:
                        # 🚀 ИСПРАВЛЕНО: Умный вызов для исключения RuntimeWarning
                        res = regime_detector.detect_regime(btc_df)
                        if asyncio.iscoroutine(res):
                            regime_data = await res
                        else:
                            regime_data = res

                        regime_multipliers = regime_detector.get_regime_multipliers(
                            regime_data["regime"], regime_data["confidence"]
                        )
                        logger.info(
                            "📊 Рыночный режим: %s (уверенность: %.0f%%)",
                            regime_data["regime"],
                            regime_data["confidence"] * 100,
                        )
                    else:
                        logger.warning("⚠️ Недостаточно данных BTC для определения режима")
                except Exception as e:
                    logger.error("❌ Ошибка определения режима: %s", e)

            # 1. Получаем СВЕЖИЕ данные пользователей из базы данных (перезагружаем каждый раз!)
            logger.info("🔍 [CYCLE DEBUG] Загрузка пользователей...")
            user_data_dict = await load_user_data()
            logger.info(
                "🔍 [CYCLE DEBUG] Загружено пользователей: %d",
                len(user_data_dict) if user_data_dict else 0,
            )
            if not user_data_dict:
                logger.warning("⚠️ Нет данных пользователей для отправки сигналов")
                await asyncio.sleep(60)
                continue

            logger.debug(
                "🔄 [REFRESH] Загружено %d пользователей (баланс обновлён)", len(user_data_dict)
            )

            # 2. Получаем символы для анализа
            logger.info("🔍 [CYCLE DEBUG] Получение символов для анализа...")
            symbols = await get_symbols()
            logger.info("🔍 [CYCLE DEBUG] Получено символов: %d", len(symbols) if symbols else 0)
            if not symbols:
                logger.warning("⚠️ Нет символов для анализа")
                await asyncio.sleep(60)
                continue

            logger.info(
                "📊 Анализируем %d символов для %d пользователей", len(symbols), len(user_data_dict)
            )

            # 3. Обрабатываем каждый символ
            processed_count = 0
            signals_sent = 0

            for symbol in symbols:
                try:
                    # Получаем данные символа
                    df = await get_symbol_data(symbol)
                    if df is None:
                        logger.debug("Данные для %s не готовы, пропускаем", symbol)
                        continue

                    # Обрабатываем сигналы для символа с учетом режима
                    symbol_signals = await process_symbol_signals(
                        symbol, df, user_data_dict, signal_history, regime_data, regime_multipliers
                    )

                    signals_sent += symbol_signals
                    processed_count += 1

                    # Небольшая пауза между символами
                    await asyncio.sleep(0.1)

                except Exception as e:
                    logger.error("Ошибка обработки %s: %s", symbol, e)
                    continue

            cycle_duration = time.time() - cycle_start_time
            logger.info(
                "✅ Цикл #%d завершен за %.2fс: обработано %d символов, отправлено %d сигналов",
                cycle_count,
                cycle_duration,
                processed_count,
                signals_sent,
            )

            # Периодический мониторинг и health check (каждый 5-й цикл)
            if cycle_count % 5 == 0:
                # Health check: проверяем количество сигналов
                if signals_sent == 0:
                    logger.warning("⚠️ HEALTH CHECK: Нет сигналов за последние 5 циклов")

                # Мониторинг производительности
                if cycle_duration > 60:
                    logger.warning("⚠️ HEALTH CHECK: Медленный цикл %.2fс", cycle_duration)

                # Статистика очереди
                queue_stats = signal_queue.get_queue_stats()
                logger.info(
                    "📊 HEALTH CHECK: Очередь %d/%d, TTL %ds",
                    queue_stats["queue_size"],
                    queue_stats["max_size"],
                    queue_stats["ttl"],
                )

                # НОВЫЙ: Детальная статистика pipeline
                pipeline_monitor.print_stats()

            # Периодический вывод статистики доставки Telegram
            if ENHANCED_DELIVERY_AVAILABLE:
                print_telegram_delivery_stats()

            # Очищаем старые сигналы из истории (старше 1 часа)
            one_hour_ago = time.time() - 3600
            signal_history[:] = [s for s in signal_history if s.get("timestamp", 0) > one_hour_ago]
            await asyncio.sleep(30)  # Пауза между циклами проверки

        except asyncio.CancelledError:
            logger.info("🛑 Исправленная система сигналов остановлена")
            break
        except Exception as e:
            logger.error("❌ Критическая ошибка в исправленной обработке: %s", e)
            await asyncio.sleep(60)  # Ждем минуту при ошибке


async def health_check_correlations():
    """Проверка здоровья системы корреляций"""
    if not CORRELATION_MANAGER_AVAILABLE or correlation_manager is None:
        return {"status": "CRITICAL", "message": "CorrelationManager не инициализирован"}

    try:
        # Проверяем БД
        stats = correlation_manager.get_statistics_report()

        # Проверяем доступность данных
        test_symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        data_availability = {}

        for symbol in test_symbols:
            try:
                data = await correlation_manager._get_ohlc_data(symbol)  # pylint: disable=protected-access
                data_availability[symbol] = len(data) if data is not None else 0
            except Exception:
                data_availability[symbol] = 0

        # Получаем историю безопасно
        history_count = 0
        try:
            history_count = (
                len(correlation_manager.signal_history_cache)
                if hasattr(correlation_manager, "signal_history_cache")
                else 0
            )
        except Exception:
            pass

        return {
            "status": "HEALTHY",
            "stats": stats,
            "data_availability": data_availability,
            "signal_history_count": history_count,
        }

    except Exception as e:
        return {"status": "ERROR", "message": str(e)}


# Периодическая проверка здоровья системы корреляций
async def periodic_health_check_correlations():
    """Периодическая проверка здоровья системы корреляций (каждые 5 минут)"""
    while True:
        try:
            await asyncio.sleep(300)  # Каждые 5 минут

            health = await health_check_correlations()
            if health["status"] != "HEALTHY":
                logger.warning("⚠️ Проблемы с системой корреляций: %s", health)
            else:
                logger.debug(
                    "✅ Система корреляций здорова: %s сигналов в истории",
                    health.get("signal_history_count", 0),
                )

        except Exception as e:
            logger.error("❌ Ошибка health check корреляций: %s", e)
            await asyncio.sleep(60)


async def periodic_risk_monitoring():
    """
    Периодический мониторинг рисков портфеля (каждые 30 минут)
    Проверяет корреляцию к SOL, концентрацию позиций, генерирует алерты
    """
    while True:
        try:
            await asyncio.sleep(1800)  # Каждые 30 минут

            if not CORRELATION_MANAGER_AVAILABLE or correlation_manager is None:
                logger.debug("⚠️ CorrelationManager недоступен для мониторинга рисков")
                continue

            # Получаем активные сигналы
            current_time = int(time.time())
            cooldown = 3600  # 1 час
            active_signals = [
                s
                for s in correlation_manager.signal_history_cache
                if (current_time - s.get("timestamp", 0)) < cooldown
            ]

            # Проверяем риски портфеля
            portfolio_risk = await correlation_manager.check_portfolio_correlation_risk(
                active_signals
            )

            # Получаем алерты
            alerts = await correlation_manager.get_risk_alerts(active_signals)

            # Логируем результаты
            logger.info(
                "📊 Мониторинг рисков: SOL позиций=%d, корреляция=%.3f, уровень=%s",
                portfolio_risk.get("sol_positions_count", 0),
                portfolio_risk.get("correlation_to_sol", 0.0),
                portfolio_risk.get("risk_level", "UNKNOWN"),
            )

            # Обрабатываем критические алерты
            critical_alerts = [a for a in alerts if a.get("level") == "CRITICAL"]
            warning_alerts = [a for a in alerts if a.get("level") == "WARNING"]

            if critical_alerts:
                logger.warning("🚨 КРИТИЧЕСКИЕ РИСКИ ПОРТФЕЛЯ:")
                for alert in critical_alerts:
                    logger.warning("  %s", alert.get("message", "N/A"))
                    logger.warning("  Действие: %s", alert.get("action", "N/A"))

                # Отправляем уведомление администратору
                await send_risk_alert_to_admin(critical_alerts, portfolio_risk)

                # Автоматическое снижение лимита при критических условиях
                await apply_automatic_risk_reduction(portfolio_risk, critical_alerts)

            elif warning_alerts:
                logger.warning("⚠️ Предупреждения по рискам портфеля:")
                for alert in warning_alerts[:3]:  # Показываем только первые 3
                    logger.warning("  %s", alert.get("message", "N/A"))

        except Exception as e:
            logger.error("❌ Ошибка мониторинга рисков: %s", e)
            await asyncio.sleep(300)  # Ждем 5 минут при ошибке


async def send_risk_alert_to_admin(alerts: List[Dict[str, Any]], portfolio_risk: Dict[str, Any]):
    """
    Отправляет критические алерты администратору через Telegram
    """
    try:
        if not TELEGRAM_INTEGRATION_AVAILABLE:
            return

        from config import TELEGRAM_CHAT_IDS, TOKEN

        if not TELEGRAM_CHAT_IDS or not TOKEN:
            logger.warning("⚠️ Telegram токен или chat IDs не настроены для отправки алертов")
            return

        # Формируем сообщение
        message_lines = [
            "🚨 <b>КРИТИЧЕСКИЕ РИСКИ ПОРТФЕЛЯ</b>",
            "",
            "📊 <b>Метрики:</b>",
            f"  • Позиций SOL_HIGH: {portfolio_risk.get('sol_positions_count', 0)}",
            f"  • Корреляция к SOL: {portfolio_risk.get('correlation_to_sol', 0.0):.3f}",
            f"  • Уровень риска: {portfolio_risk.get('risk_level', 'UNKNOWN')}",
            "",
            "🚨 <b>Критические алерты:</b>",
        ]

        for alert in alerts:
            message_lines.append(f"  • {alert.get('message', 'N/A')}")
            if alert.get("action"):
                message_lines.append(f"    → {alert.get('action')}")

        message = "\n".join(message_lines)

        # Отправляем в первый чат из списка (обычно это администратор)
        chat_ids = [cid.strip() for cid in TELEGRAM_CHAT_IDS.split(",") if cid.strip()]
        if not chat_ids:
            return

        admin_chat_id = chat_ids[0]  # Первый чат = администратор

        async with aiohttp.ClientSession() as session:
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            data = {"chat_id": admin_chat_id, "text": message, "parse_mode": "HTML"}

            async with session.post(
                url, json=data, timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                if response.status == 200:
                    logger.info("✅ Критический алерт отправлен администратору")
                else:
                    logger.warning(
                        "⚠️ Не удалось отправить алерт администратору: статус %d", response.status
                    )

    except Exception as e:
        logger.error("❌ Ошибка отправки алерта администратору: %s", e)


async def apply_automatic_risk_reduction(
    portfolio_risk: Dict[str, Any], critical_alerts: List[Dict[str, Any]]
):
    """
    Применяет автоматическое снижение лимита при критических условиях
    """
    try:
        if not CORRELATION_MANAGER_AVAILABLE or correlation_manager is None:
            return

        correlation = portfolio_risk.get("correlation_to_sol", 0.0)
        sol_positions = portfolio_risk.get("sol_positions_count", 0)

        # Критическая корреляция (>0.9) → снижаем лимит SOL_HIGH до 6
        if correlation > 0.9:
            original_limit = correlation_manager.sector_limits["SOL_HIGH"]["max_signals"]
            if original_limit > 6:
                correlation_manager.sector_limits["SOL_HIGH"]["max_signals"] = 6
                logger.warning(
                    "🔧 АВТОМАТИЧЕСКОЕ СНИЖЕНИЕ: Лимит SOL_HIGH снижен с %d до 6 (корреляция %.3f > 0.9)",
                    original_limit,
                    correlation,
                )
                return

        # Высокая концентрация (8+ позиций) при высокой корреляции → снижаем до 7
        if sol_positions >= 8 and correlation > 0.85:
            original_limit = correlation_manager.sector_limits["SOL_HIGH"]["max_signals"]
            if original_limit > 7:
                correlation_manager.sector_limits["SOL_HIGH"]["max_signals"] = 7
                logger.warning(
                    "🔧 АВТОМАТИЧЕСКОЕ СНИЖЕНИЕ: Лимит SOL_HIGH снижен с %d до 7 (позиций=%d, корреляция=%.3f)",
                    original_limit,
                    sol_positions,
                    correlation,
                )

    except Exception as e:
        logger.error("❌ Ошибка автоматического снижения лимита: %s", e)


# Регистрация функций для ядра сигналов (устраняет циклический импорт)
try:
    # pylint: disable=ungrouped-imports
    from src.signals.core import (
        generate_signal_base,
        register_signal_live_functions,
    )
    from src.signals.core import (
        run_hybrid_signal_system_fixed as _core_run_hybrid_signal_system_fixed,
    )

    register_signal_live_functions(_generate_signal_impl, _run_hybrid_signal_system_fixed_impl)

    generate_signal = generate_signal_base
    run_hybrid_signal_system_fixed = _core_run_hybrid_signal_system_fixed
except Exception as core_register_err:  # noqa: BLE001
    logger.error("❌ Не удалось зарегистрировать функции ядра сигналов: %s", core_register_err)

    # Fallback: сохраняем локальные реализации
    async def generate_signal(*args, **kwargs):
        """Fallback функция generate_signal, если регистрация не удалась."""
        return await _generate_signal_impl(*args, **kwargs)

    async def run_hybrid_signal_system_fixed():
        """Fallback функция run_hybrid_signal_system_fixed, если регистрация не удалась."""
        return await _run_hybrid_signal_system_fixed_impl()


if __name__ == "__main__":
    # Для запуска вне основного event loop (например, для отладки)
    logger.info("🎯 ТОЧКА ВХОДА: Запуск signal_live.py")
    logger.info("🎯 Проверка доступности функции _run_hybrid_signal_system_fixed_impl")
    try:
        # Проверяем, что функция доступна
        if "_run_hybrid_signal_system_fixed_impl" in globals():
            logger.info("✅ Функция _run_hybrid_signal_system_fixed_impl доступна в globals()")
        else:
            logger.error("❌ Функция _run_hybrid_signal_system_fixed_impl НЕ найдена в globals()")

        logger.info("🎯 Вызов asyncio.run(_run_hybrid_signal_system_fixed_impl())")
        asyncio.run(_run_hybrid_signal_system_fixed_impl())
    except KeyboardInterrupt:
        logger.info("Система остановлена пользователем.")
    except RuntimeError as e:
        if "cannot run an event loop while another event loop is running" in str(e):
            logger.warning("Обнаружен запущенный event loop. Запускаем систему в текущем loop.")
            event_loop = asyncio.get_event_loop()
            event_loop.create_task(_run_hybrid_signal_system_fixed_impl())
            # Если это основной скрипт, то loop должен быть запущен где-то еще
            # или нужно использовать loop.run_forever()
        else:
            raise

"""
AMT Filter - фильтр на основе Auction Market Theory

Фильтрует сигналы на основе фаз рынка:
- Balance: блокирует входы (консолидация)
- Imbalance: разрешает входы (готовность к движению)
- Auction: нейтрально (активное движение)
"""

import logging
import time
from typing import Tuple, Optional

import pandas as pd

logger = logging.getLogger(__name__)

# Попытка импорта метрик
try:
    from src.metrics.decorators import record_filter_metrics, FilterType
    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False

# Импорт Prometheus метрик
try:
    from src.monitoring.prometheus import (
        record_filter_check,
        record_amt_phase,
        record_indicator_processing_time,
    )
    PROMETHEUS_METRICS_AVAILABLE = True
except ImportError:
    PROMETHEUS_METRICS_AVAILABLE = False

# Импорты с fallback
try:
    from src.analysis.auction_market_theory import AuctionMarketTheory, MarketPhase
    AMT_AVAILABLE = True
except ImportError:
    AMT_AVAILABLE = False
    logger.warning("Auction Market Theory модуль недоступен")


def check_amt_filter(
    df: pd.DataFrame,
    i: int,
    side: str,
    strict_mode: bool = True,
) -> Tuple[bool, Optional[str]]:
    """
    Проверяет, соответствует ли сигнал AMT фильтрам
    
    Логика:
    - Balance: блокирует все входы (консолидация, неопределенность)
    - Imbalance: разрешает входы в направлении дисбаланса
    - Auction: в строгом режиме блокирует, в мягком разрешает
    
    Args:
        df: DataFrame с данными OHLCV
        i: Индекс текущей свечи
        side: "long" или "short"
        strict_mode: True для строгого режима (более жесткие фильтры)
    
    Returns:
        Tuple[passed, reason]
    """
    try:
        if not AMT_AVAILABLE:
            return True, None  # Если модуль недоступен, пропускаем фильтр
        
        if i >= len(df):
            return False, "Индекс выходит за границы DataFrame"
        
        start_time = time.time()
        
        # Инициализируем AMT
        # Оптимизированные параметры: lookback=20, balance=0.3, imbalance=0.5
        amt = AuctionMarketTheory(
            lookback=20,
            balance_threshold=0.3,
            imbalance_threshold=0.5,  # Оптимизировано: было 0.6/0.5, стало 0.5 для всех режимов
        )
        
        # Определяем фазу рынка
        phase, details = amt.detect_market_phase(df, i)
        
        processing_time = time.time() - start_time
        
        # Записываем Prometheus метрики
        if PROMETHEUS_METRICS_AVAILABLE:
            try:
                symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                if phase is not None and details is not None:
                    balance_score = details.get('balance_score', 0.5)
                    record_amt_phase(symbol, phase.value, balance_score)
                record_indicator_processing_time('amt', processing_time)
            except Exception as e:
                logger.debug(f"Ошибка записи Prometheus метрик AMT: {e}")
        
        if phase is None or details is None:
            # Если не удалось определить фазу, пропускаем фильтр
            return True, None
        
        balance_score = details.get('balance_score')
        if balance_score is None:
            return True, None
        
        # Логика фильтрации по фазам
        if phase == MarketPhase.BALANCE:
            # Balance: блокируем все входы (консолидация)
            result = (False, f"AMT: рынок в фазе баланса (balance_score={balance_score:.3f}), входы блокированы")
            # Логирование метрик
            if METRICS_AVAILABLE:
                try:
                    record_filter_metrics(
                        filter_type=FilterType.ORDER_FLOW,
                        passed=False,
                        processing_time=processing_time,
                        rejection_reason="AMT_BALANCE_PHASE"
                    )
                except Exception:
                    pass
            # Prometheus метрики
            if PROMETHEUS_METRICS_AVAILABLE:
                try:
                    symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                    record_filter_check('amt', symbol, False)
                except Exception:
                    pass
            return result
        
        elif phase == MarketPhase.IMBALANCE:
            # Imbalance: разрешаем входы в направлении дисбаланса
            if side.lower() == "long":
                # LONG разрешен только при преобладании покупателей
                if balance_score > 0.5:
                    result = (True, None)
                    if METRICS_AVAILABLE:
                        try:
                            record_filter_metrics(
                                filter_type=FilterType.ORDER_FLOW,
                                passed=True,
                                processing_time=processing_time,
                            )
                        except Exception:
                            pass
                    # Prometheus метрики
                    if PROMETHEUS_METRICS_AVAILABLE:
                        try:
                            symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                            record_filter_check('amt', symbol, True)
                        except Exception:
                            pass
                    return result
                else:
                    result = (False, f"AMT: дисбаланс в пользу продавцов (balance_score={balance_score:.3f}), LONG блокирован")
                    if METRICS_AVAILABLE:
                        try:
                            record_filter_metrics(
                                filter_type=FilterType.ORDER_FLOW,
                                passed=False,
                                processing_time=processing_time,
                                rejection_reason="AMT_IMBALANCE_WRONG_DIRECTION"
                            )
                        except Exception:
                            pass
                    # Prometheus метрики
                    if PROMETHEUS_METRICS_AVAILABLE:
                        try:
                            symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                            record_filter_check('amt', symbol, False)
                        except Exception:
                            pass
                    return result
            
            elif side.lower() == "short":
                # SHORT разрешен только при преобладании продавцов
                if balance_score < 0.5:
                    result = (True, None)
                    if METRICS_AVAILABLE:
                        try:
                            record_filter_metrics(
                                filter_type=FilterType.ORDER_FLOW,
                                passed=True,
                                processing_time=processing_time,
                            )
                        except Exception:
                            pass
                    # Prometheus метрики
                    if PROMETHEUS_METRICS_AVAILABLE:
                        try:
                            symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                            record_filter_check('amt', symbol, True)
                        except Exception:
                            pass
                    return result
                else:
                    result = (False, f"AMT: дисбаланс в пользу покупателей (balance_score={balance_score:.3f}), SHORT блокирован")
                    if METRICS_AVAILABLE:
                        try:
                            record_filter_metrics(
                                filter_type=FilterType.ORDER_FLOW,
                                passed=False,
                                processing_time=processing_time,
                                rejection_reason="AMT_IMBALANCE_WRONG_DIRECTION"
                            )
                        except Exception:
                            pass
                    # Prometheus метрики
                    if PROMETHEUS_METRICS_AVAILABLE:
                        try:
                            symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                            record_filter_check('amt', symbol, False)
                        except Exception:
                            pass
                    return result
        
        elif phase == MarketPhase.AUCTION:
            # Auction: в строгом режиме блокируем, в мягком разрешаем
            if strict_mode:
                result = (False, f"AMT: рынок в фазе аукциона (balance_score={balance_score:.3f}), входы блокированы в строгом режиме")
                if METRICS_AVAILABLE:
                    try:
                        record_filter_metrics(
                            filter_type=FilterType.ORDER_FLOW,
                            passed=False,
                            processing_time=processing_time,
                            rejection_reason="AMT_AUCTION_STRICT_MODE"
                        )
                    except Exception:
                        pass
                # Prometheus метрики
                if PROMETHEUS_METRICS_AVAILABLE:
                    try:
                        symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                        record_filter_check('amt', symbol, False)
                    except Exception:
                        pass
                return result
            else:
                # В мягком режиме проверяем направление
                if side.lower() == "long" and balance_score > 0.5:
                    result = (True, None)
                    if METRICS_AVAILABLE:
                        try:
                            record_filter_metrics(
                                filter_type=FilterType.ORDER_FLOW,
                                passed=True,
                                processing_time=processing_time,
                            )
                        except Exception:
                            pass
                    # Prometheus метрики
                    if PROMETHEUS_METRICS_AVAILABLE:
                        try:
                            symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                            record_filter_check('amt', symbol, True)
                        except Exception:
                            pass
                    return result
                elif side.lower() == "short" and balance_score < 0.5:
                    result = (True, None)
                    if METRICS_AVAILABLE:
                        try:
                            record_filter_metrics(
                                filter_type=FilterType.ORDER_FLOW,
                                passed=True,
                                processing_time=processing_time,
                            )
                        except Exception:
                            pass
                    # Prometheus метрики
                    if PROMETHEUS_METRICS_AVAILABLE:
                        try:
                            symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                            record_filter_check('amt', symbol, True)
                        except Exception:
                            pass
                    return result
                else:
                    result = (False, f"AMT: аукцион не подтверждает {side.upper()} (balance_score={balance_score:.3f})")
                    if METRICS_AVAILABLE:
                        try:
                            record_filter_metrics(
                                filter_type=FilterType.ORDER_FLOW,
                                passed=False,
                                processing_time=processing_time,
                                rejection_reason="AMT_AUCTION_NO_CONFIRMATION"
                            )
                        except Exception:
                            pass
                    # Prometheus метрики
                    if PROMETHEUS_METRICS_AVAILABLE:
                        try:
                            symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                            record_filter_check('amt', symbol, False)
                        except Exception:
                            pass
                    return result
        
        result = (True, None)
        if METRICS_AVAILABLE:
            try:
                record_filter_metrics(
                    filter_type=FilterType.ORDER_FLOW,
                    passed=True,
                    processing_time=processing_time,
                )
            except Exception:
                pass
        # Prometheus метрики
        if PROMETHEUS_METRICS_AVAILABLE:
            try:
                symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                record_filter_check('amt', symbol, True)
            except Exception:
                pass
        return result
        
    except Exception as e:
        logger.error("Ошибка в check_amt_filter: %s", e)
        return True, None  # В случае ошибки пропускаем фильтр


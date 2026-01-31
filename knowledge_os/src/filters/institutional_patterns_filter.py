"""
Institutional Patterns Filter - фильтр на основе обнаруженных паттернов институционалов

Фильтрует сигналы на основе:
- Iceberg Orders (скрытые крупные ордера)
- Spoofing (ложные заявки)
- Оценки качества сигнала
"""

import logging
import time
from typing import Tuple, Optional

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
        record_institutional_pattern,
        record_indicator_processing_time,
    )
    PROMETHEUS_METRICS_AVAILABLE = True
except ImportError:
    PROMETHEUS_METRICS_AVAILABLE = False

# Импорты с fallback
try:
    from src.analysis.institutional_patterns import InstitutionalPatternDetector
    INSTITUTIONAL_PATTERNS_AVAILABLE = True
except ImportError:
    INSTITUTIONAL_PATTERNS_AVAILABLE = False
    logger.warning("Institutional Patterns модуль недоступен")


def check_institutional_patterns_filter(
    df: pd.DataFrame,
    i: int,
    side: str,
    strict_mode: bool = True,
    min_quality_score: float = 0.6,  # Оптимизировано: 0.6 (уже оптимальное значение)
) -> Tuple[bool, Optional[str]]:
    """
    Проверяет, соответствует ли сигнал Institutional Patterns фильтрам
    
    Логика:
    - Spoofing обнаружен → блокируем сигнал (ложные заявки)
    - Iceberg обнаружен → может подтверждать или ослаблять сигнал
    - Низкое качество сигнала → блокируем в строгом режиме
    
    Args:
        df: DataFrame с данными OHLCV
        i: Индекс текущей свечи
        side: "long" или "short"
        strict_mode: True для строгого режима (более жесткие фильтры)
        min_quality_score: Минимальный балл качества сигнала (0.0-1.0)
    
    Returns:
        Tuple[passed, reason]
    """
    try:
        if not INSTITUTIONAL_PATTERNS_AVAILABLE:
            return True, None  # Если модуль недоступен, пропускаем фильтр

        if i >= len(df):
            return False, "Индекс выходит за границы DataFrame"

        start_time = time.time()

        # Инициализируем детектор
        detector = InstitutionalPatternDetector()

        # Оцениваем качество сигнала
        start_time = time.time()
        quality = detector.get_signal_quality(df, i, side)
        processing_time = time.time() - start_time

        # Записываем метрики обнаруженных паттернов
        if PROMETHEUS_METRICS_AVAILABLE:
            try:
                symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                patterns = detector.detect_patterns(df, i)
                for pattern in patterns:
                    record_institutional_pattern(symbol, pattern.pattern_type, pattern.confidence)
                record_indicator_processing_time('institutional_patterns', processing_time)
            except Exception as e:
                logger.debug("Ошибка записи метрик Institutional Patterns: %s", e)

        quality_score = quality.get('quality_score', 1.0)
        patterns_detected = quality.get('patterns_detected', [])
        recommendation = quality.get('recommendation', 'neutral')

        processing_time = time.time() - start_time
        
        # Проверяем на Spoofing (критично - всегда блокируем)
        if 'spoofing' in patterns_detected:
            spoofing_patterns = [p for p in detector.detect_patterns(df, i) if p.pattern_type == 'spoofing']
            if spoofing_patterns:
                max_spoofing_confidence = max(p.confidence for p in spoofing_patterns)
                result = (False, (
                    f"Institutional Patterns: обнаружен Spoofing (confidence={max_spoofing_confidence:.2f}), "
                    f"сигнал заблокирован (ложные заявки)"
                ))
                if METRICS_AVAILABLE:
                    try:
                        record_filter_metrics(
                            filter_type=FilterType.INSTITUTIONAL_PATTERNS_FILTER,
                            passed=False,
                            processing_time=processing_time,
                            rejection_reason="INSTITUTIONAL_PATTERNS_SPOOFING_DETECTED"
                        )
                    except Exception:
                        pass
                # Prometheus метрики
                if PROMETHEUS_METRICS_AVAILABLE:
                    try:
                        symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                        record_filter_check('institutional_patterns', symbol, False)
                    except Exception:
                        pass
                return result

        # Проверяем качество сигнала
        adjusted_min_quality = min_quality_score * (0.8 if strict_mode else 1.0)

        if quality_score < adjusted_min_quality:
            result = (False, (
                f"Institutional Patterns: низкое качество сигнала (score={quality_score:.2f}, "
                f"требуется={adjusted_min_quality:.2f}), recommendation={recommendation}"
            ))
            if METRICS_AVAILABLE:
                try:
                    record_filter_metrics(
                        filter_type=FilterType.INSTITUTIONAL_PATTERNS_FILTER,
                        passed=False,
                        processing_time=processing_time,
                        rejection_reason="INSTITUTIONAL_PATTERNS_LOW_QUALITY"
                    )
                except Exception:
                    pass
            # Prometheus метрики
            if PROMETHEUS_METRICS_AVAILABLE:
                try:
                    symbol = df.get('symbol', 'unknown') if hasattr(df, 'get') else 'unknown'
                    record_filter_check('institutional_patterns', symbol, False)
                except Exception:
                    pass
            return result

        # В строгом режиме требуем более высокое качество
        if strict_mode and recommendation == 'weak':
            result = (False, (
                f"Institutional Patterns: слабый сигнал (recommendation=weak, score={quality_score:.2f}), "
                f"блокирован в строгом режиме"
            ))
            if METRICS_AVAILABLE:
                try:
                    record_filter_metrics(
                        filter_type=FilterType.INSTITUTIONAL_PATTERNS_FILTER,
                        passed=False,
                        processing_time=processing_time,
                        rejection_reason="INSTITUTIONAL_PATTERNS_WEAK_SIGNAL"
                    )
                except Exception:
                    pass
            return result

        # Если recommendation = 'reject', всегда блокируем
        if recommendation == 'reject':
            result = (False, (
                f"Institutional Patterns: сигнал отклонен паттернами (score={quality_score:.2f}, "
                f"patterns={patterns_detected})"
            ))
            if METRICS_AVAILABLE:
                try:
                    record_filter_metrics(
                        filter_type=FilterType.INSTITUTIONAL_PATTERNS_FILTER,
                        passed=False,
                        processing_time=processing_time,
                        rejection_reason="INSTITUTIONAL_PATTERNS_REJECTED"
                    )
                except Exception:
                    pass
            return result

        result = (True, None)
        if METRICS_AVAILABLE:
            try:
                record_filter_metrics(
                    filter_type=FilterType.INSTITUTIONAL_PATTERNS_FILTER,
                    passed=True,
                    processing_time=processing_time,
                )
            except Exception:
                pass
        return result

    except Exception as e:
        logger.error("Ошибка в check_institutional_patterns_filter: %s", e)
        return True, None  # В случае ошибки пропускаем фильтр
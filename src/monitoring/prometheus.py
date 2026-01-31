#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📊 Prometheus Metrics для ATRA Trading System

Экспортирует метрики в формате Prometheus для мониторинга системы.
"""

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Histogram, Gauge, start_http_server, generate_latest
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    # Не используем заглушки - если prometheus_client не установлен, метрики просто не работают
    Counter = None
    Histogram = None
    Gauge = None
    start_http_server = None
    generate_latest = None


# ==================== METRICS DEFINITIONS ====================

# Signals metrics
signals_generated_total = Counter(
    'atra_signals_generated_total',
    'Total number of signals generated',
    ['symbol', 'signal_type', 'pattern_type']
) if PROMETHEUS_AVAILABLE else None

signals_accepted_total = Counter(
    'atra_signals_accepted_total',
    'Total number of signals accepted',
    ['symbol', 'signal_type']
) if PROMETHEUS_AVAILABLE else None

signals_rejected_total = Counter(
    'atra_signals_rejected_total',
    'Total number of signals rejected',
    ['symbol', 'signal_type', 'rejection_reason']
) if PROMETHEUS_AVAILABLE else None

# ML metrics
ml_predictions_total = Counter(
    'atra_ml_predictions_total',
    'Total number of ML predictions',
    ['symbol', 'signal_type']
) if PROMETHEUS_AVAILABLE else None

ml_prediction_probability = Histogram(
    'atra_ml_prediction_probability',
    'ML prediction probability distribution',
    ['symbol', 'signal_type'],
    buckets=[0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
) if PROMETHEUS_AVAILABLE else None

ml_prediction_expected_profit = Histogram(
    'atra_ml_prediction_expected_profit',
    'ML prediction expected profit distribution',
    ['symbol', 'signal_type'],
    buckets=[-5.0, -2.0, -1.0, -0.5, 0.0, 0.5, 1.0, 2.0, 5.0, 10.0]
) if PROMETHEUS_AVAILABLE else None

# Trading metrics
active_positions = Gauge(
    'atra_active_positions',
    'Number of active trading positions',
    ['symbol']
) if PROMETHEUS_AVAILABLE else None

position_pnl = Gauge(
    'atra_position_pnl',
    'Current PnL of position',
    ['symbol', 'signal_type']
) if PROMETHEUS_AVAILABLE else None

# Performance metrics
signal_generation_duration = Histogram(
    'atra_signal_generation_duration_seconds',
    'Time taken to generate signal',
    ['symbol', 'pattern_type'],
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
) if PROMETHEUS_AVAILABLE else None

ml_prediction_duration = Histogram(
    'atra_ml_prediction_duration_seconds',
    'Time taken for ML prediction',
    ['symbol'],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
) if PROMETHEUS_AVAILABLE else None

# System metrics
system_health = Gauge(
    'atra_system_health',
    'System health status (1=healthy, 0=unhealthy)'
) if PROMETHEUS_AVAILABLE else None

database_size_bytes = Gauge(
    'atra_database_size_bytes',
    'Size of trading database in bytes'
) if PROMETHEUS_AVAILABLE else None

# Error metrics
errors_total = Counter(
    'atra_errors_total',
    'Total number of errors',
    ['error_type', 'component']
) if PROMETHEUS_AVAILABLE else None

# Alert metrics (Елена + Сергей - To 10/10)
alerts_total = Counter(
    'atra_alerts_total',
    'Total number of alerts',
    ['alert_type', 'severity']
) if PROMETHEUS_AVAILABLE else None

alerts_active = Gauge(
    'atra_alerts_active',
    'Number of active alerts',
    ['alert_type', 'severity']
) if PROMETHEUS_AVAILABLE else None

# Institutional Indicators metrics (Елена - мониторинг новых индикаторов)
amt_phase_detected = Counter(
    'atra_amt_phase_detected_total',
    'Total number of AMT phase detections',
    ['symbol', 'phase']  # phase: auction, balance, imbalance
) if PROMETHEUS_AVAILABLE else None

amt_balance_score = Histogram(
    'atra_amt_balance_score',
    'AMT balance score distribution',
    ['symbol'],
    buckets=[0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 1.0]
) if PROMETHEUS_AVAILABLE else None

tpo_poc_detected = Counter(
    'atra_tpo_poc_detected_total',
    'Total number of TPO POC detections',
    ['symbol']
) if PROMETHEUS_AVAILABLE else None

institutional_patterns_detected = Counter(
    'atra_institutional_patterns_detected_total',
    'Total number of institutional patterns detected',
    ['symbol', 'pattern_type']  # pattern_type: iceberg, spoofing
) if PROMETHEUS_AVAILABLE else None

institutional_patterns_confidence = Histogram(
    'atra_institutional_patterns_confidence',
    'Institutional patterns confidence distribution',
    ['symbol', 'pattern_type'],
    buckets=[0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
) if PROMETHEUS_AVAILABLE else None

cdv_divergence_detected = Counter(
    'atra_cdv_divergence_detected_total',
    'Total number of CDV divergences detected',
    ['symbol', 'divergence_type']  # divergence_type: bullish, bearish
) if PROMETHEUS_AVAILABLE else None

price_level_imbalance_zones = Gauge(
    'atra_price_level_imbalance_zones',
    'Number of price level imbalance zones detected',
    ['symbol']
) if PROMETHEUS_AVAILABLE else None

vwt_poc_detected = Counter(
    'atra_vwt_poc_detected_total',
    'Total number of VWT POC detections',
    ['symbol']
) if PROMETHEUS_AVAILABLE else None

# Filter metrics for new indicators
filter_amt_checks = Counter(
    'atra_filter_amt_checks_total',
    'Total number of AMT filter checks',
    ['symbol', 'result']  # result: passed, rejected
) if PROMETHEUS_AVAILABLE else None

filter_market_profile_checks = Counter(
    'atra_filter_market_profile_checks_total',
    'Total number of Market Profile filter checks',
    ['symbol', 'result']
) if PROMETHEUS_AVAILABLE else None

filter_institutional_patterns_checks = Counter(
    'atra_filter_institutional_patterns_checks_total',
    'Total number of Institutional Patterns filter checks',
    ['symbol', 'result']
) if PROMETHEUS_AVAILABLE else None

# Indicator processing time metrics
indicator_processing_time = Histogram(
    'atra_indicator_processing_time_seconds',
    'Time taken to process indicators',
    ['indicator_type'],  # indicator_type: amt, tpo, institutional_patterns, cdv, price_level_imbalance, vwt
    buckets=[0.001, 0.005, 0.01, 0.05, 0.1, 0.5, 1.0, 2.0]
) if PROMETHEUS_AVAILABLE else None


# ==================== HELPER FUNCTIONS ====================

def record_signal_generated(symbol: str, signal_type: str, pattern_type: str) -> None:
    """Записывает метрику генерации сигнала"""
    if PROMETHEUS_AVAILABLE:
        signals_generated_total.labels(
            symbol=symbol,
            signal_type=signal_type,
            pattern_type=pattern_type
        ).inc()


def record_signal_accepted(symbol: str, signal_type: str) -> None:
    """Записывает метрику принятия сигнала"""
    if PROMETHEUS_AVAILABLE:
        signals_accepted_total.labels(
            symbol=symbol,
            signal_type=signal_type
        ).inc()


def record_signal_rejected(symbol: str, signal_type: str, reason: str) -> None:
    """Записывает метрику отклонения сигнала"""
    if PROMETHEUS_AVAILABLE:
        signals_rejected_total.labels(
            symbol=symbol,
            signal_type=signal_type,
            rejection_reason=reason
        ).inc()


def record_ml_prediction(
    symbol: str,
    signal_type: str,
    probability: float,
    expected_profit: float,
    duration: float
) -> None:
    """Записывает метрики ML предсказания"""
    if PROMETHEUS_AVAILABLE:
        ml_predictions_total.labels(
            symbol=symbol,
            signal_type=signal_type
        ).inc()
        
        ml_prediction_probability.labels(
            symbol=symbol,
            signal_type=signal_type
        ).observe(probability)
        
        ml_prediction_expected_profit.labels(
            symbol=symbol,
            signal_type=signal_type
        ).observe(expected_profit)
        
        ml_prediction_duration.labels(symbol=symbol).observe(duration)


def update_active_positions(symbol: str, count: int) -> None:
    """Обновляет количество активных позиций"""
    if PROMETHEUS_AVAILABLE:
        active_positions.labels(symbol=symbol).set(count)


def update_position_pnl(symbol: str, signal_type: str, pnl: float) -> None:
    """Обновляет PnL позиции"""
    if PROMETHEUS_AVAILABLE:
        position_pnl.labels(
            symbol=symbol,
            signal_type=signal_type
        ).set(pnl)


def record_signal_generation_time(symbol: str, pattern_type: str, duration: float) -> None:
    """Записывает время генерации сигнала"""
    if PROMETHEUS_AVAILABLE:
        signal_generation_duration.labels(
            symbol=symbol,
            pattern_type=pattern_type
        ).observe(duration)


def update_system_health(healthy: bool) -> None:
    """Обновляет статус здоровья системы"""
    if PROMETHEUS_AVAILABLE:
        system_health.set(1 if healthy else 0)


def update_database_size(size_bytes: int) -> None:
    """Обновляет размер базы данных"""
    if PROMETHEUS_AVAILABLE:
        database_size_bytes.set(size_bytes)


def record_error(error_type: str, component: str) -> None:
    """Записывает ошибку"""
    if PROMETHEUS_AVAILABLE:
        errors_total.labels(
            error_type=error_type,
            component=component
        ).inc()


def record_alert(alert_type: str, severity: str, message: str = "") -> None:
    """
    Записывает метрику алерта (Елена + Сергей - To 10/10)
    
    Args:
        alert_type: Тип алерта (например, 'NO_SIGNALS')
        severity: Серьёзность (LOW, MEDIUM, HIGH, CRITICAL)
        message: Сообщение алерта (опционально)
    """
    if PROMETHEUS_AVAILABLE:
        alerts_total.labels(
            alert_type=alert_type,
            severity=severity
        ).inc()
        
        # Устанавливаем активный алерт
        alerts_active.labels(
            alert_type=alert_type,
            severity=severity
        ).set(1)


# ==================== INSTITUTIONAL INDICATORS METRICS ====================

def record_amt_phase(symbol: str, phase: str, balance_score: float) -> None:
    """Записывает метрику фазы AMT"""
    if PROMETHEUS_AVAILABLE:
        amt_phase_detected.labels(symbol=symbol, phase=phase).inc()
        amt_balance_score.labels(symbol=symbol).observe(balance_score)


def record_tpo_poc(symbol: str) -> None:
    """Записывает метрику обнаружения TPO POC"""
    if PROMETHEUS_AVAILABLE:
        tpo_poc_detected.labels(symbol=symbol).inc()


def record_institutional_pattern(
    symbol: str,
    pattern_type: str,
    confidence: float
) -> None:
    """Записывает метрику обнаруженного институционального паттерна"""
    if PROMETHEUS_AVAILABLE:
        institutional_patterns_detected.labels(
            symbol=symbol,
            pattern_type=pattern_type
        ).inc()
        institutional_patterns_confidence.labels(
            symbol=symbol,
            pattern_type=pattern_type
        ).observe(confidence)


def record_cdv_divergence(symbol: str, divergence_type: str) -> None:
    """Записывает метрику обнаруженной дивергенции CDV"""
    if PROMETHEUS_AVAILABLE:
        cdv_divergence_detected.labels(
            symbol=symbol,
            divergence_type=divergence_type
        ).inc()


def update_price_level_imbalance_zones(symbol: str, zones_count: int) -> None:
    """Обновляет количество зон дисбаланса по уровням цены"""
    if PROMETHEUS_AVAILABLE:
        price_level_imbalance_zones.labels(symbol=symbol).set(zones_count)


def record_vwt_poc(symbol: str) -> None:
    """Записывает метрику обнаружения VWT POC"""
    if PROMETHEUS_AVAILABLE:
        vwt_poc_detected.labels(symbol=symbol).inc()


def record_filter_check(
    filter_type: str,
    symbol: str,
    passed: bool
) -> None:
    """Записывает метрику проверки фильтра"""
    if not PROMETHEUS_AVAILABLE:
        return
    
    result = "passed" if passed else "rejected"
    
    if filter_type == "amt":
        filter_amt_checks.labels(symbol=symbol, result=result).inc()
    elif filter_type == "market_profile":
        filter_market_profile_checks.labels(symbol=symbol, result=result).inc()
    elif filter_type == "institutional_patterns":
        filter_institutional_patterns_checks.labels(symbol=symbol, result=result).inc()


def record_indicator_processing_time(
    indicator_type: str,
    duration: float
) -> None:
    """Записывает время обработки индикатора"""
    if PROMETHEUS_AVAILABLE:
        indicator_processing_time.labels(indicator_type=indicator_type).observe(duration)


# Глобальная переменная для порта метрик
METRICS_SERVER_PORT = int(os.getenv("PROMETHEUS_METRICS_PORT", "8000"))


def start_metrics_server(port: Optional[int] = None) -> None:
    """
    Запускает HTTP сервер для экспорта метрик Prometheus (Елена + Сергей - To 10/10)
    
    Args:
        port: Порт для метрик (по умолчанию из переменной окружения или 8000)
    """
    if not PROMETHEUS_AVAILABLE:
        logger.warning("⚠️ Prometheus client не установлен. Метрики недоступны.")
        return
    
    if port is None:
        port = METRICS_SERVER_PORT
    
    try:
        start_http_server(port)
        logger.info("✅ Prometheus metrics server started on port %d", port)
        logger.info("   Metrics endpoint: http://localhost:%d/metrics", port)
    except Exception as e:
        logger.error("❌ Failed to start Prometheus metrics server: %s", e)


def get_metrics() -> bytes:
    """
    Возвращает метрики в формате Prometheus
    
    Returns:
        Метрики в формате Prometheus (bytes)
    """
    if not PROMETHEUS_AVAILABLE:
        return b"# Prometheus client not available\n"
    
    return generate_latest()


# ==================== USAGE EXAMPLE ====================

# Example usage:
#
# from prometheus_metrics import (
#     record_signal_generated,
#     record_signal_accepted,
#     record_ml_prediction,
#     start_metrics_server
# )
#
# # Start metrics server (once at startup)
# start_metrics_server(port=8000)
#
# # Record metrics
# record_signal_generated("BTCUSDT", "LONG", "classic")
# record_signal_accepted("BTCUSDT", "LONG")
# record_ml_prediction("BTCUSDT", "LONG", 0.85, 2.5, 0.05)
#
# # Access metrics at http://localhost:8000/metrics


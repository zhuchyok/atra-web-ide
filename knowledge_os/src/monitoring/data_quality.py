#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Система мониторинга качества данных.

Отслеживает качество данных, детектирует аномалии, генерирует алерты
и предоставляет метрики для анализа производительности источников данных.
"""

import asyncio
import logging
import time
import statistics
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from src.shared.utils.datetime_utils import get_utc_now
from collections import deque
import pandas as pd

logger = logging.getLogger(__name__)

@dataclass
class QualityMetric:
    """Метрика качества данных"""
    timestamp: datetime
    symbol: str
    source: str
    metric_type: str  # 'price_accuracy', 'volume_consistency', 'latency', 'availability'
    value: float
    threshold: float
    is_healthy: bool
    details: Dict = field(default_factory=dict)

@dataclass
class AnomalyAlert:
    """Алерт об аномалии в данных"""
    timestamp: datetime
    symbol: str
    source: str
    alert_type: str  # 'price_spike', 'volume_anomaly', 'missing_data', 'source_down'
    severity: str  # 'low', 'medium', 'high', 'critical'
    message: str
    data: Dict = field(default_factory=dict)

class DataQualityMonitor:
    """Монитор качества данных"""

    def __init__(self):
        self.metrics_history = deque(maxlen=10000)  # Храним последние 10000 метрик
        self.alerts_history = deque(maxlen=1000)    # Храним последние 1000 алертов
        self.source_stats = {}  # Статистика по источникам
        self.symbol_stats = {}  # Статистика по символам

        # Пороги для детекции аномалий
        self.thresholds = {
            'price_deviation_pct': 5.0,      # 5% отклонение цены
            'volume_deviation_pct': 100.0,   # 100% отклонение объема
            'latency_ms': 5000,              # 5 секунд задержка
            'missing_data_pct': 10.0,        # 10% пропущенных данных
            'error_rate_pct': 20.0           # 20% ошибок
        }

        # Конфигурация мониторинга
        self.monitoring_enabled = True
        self.alert_cooldown = {}  # Кулдаун для алертов

    def add_metric(self, metric: QualityMetric):
        """Добавляет метрику качества"""
        if not self.monitoring_enabled:
            return

        self.metrics_history.append(metric)

        # Обновляем статистику по источникам
        if metric.source not in self.source_stats:
            self.source_stats[metric.source] = {
                'total_metrics': 0,
                'healthy_metrics': 0,
                'last_update': None
            }

        stats = self.source_stats[metric.source]
        stats['total_metrics'] += 1
        if metric.is_healthy:
            stats['healthy_metrics'] += 1
        stats['last_update'] = metric.timestamp

        # Обновляем статистику по символам
        if metric.symbol not in self.symbol_stats:
            self.symbol_stats[metric.symbol] = {
                'total_metrics': 0,
                'healthy_metrics': 0,
                'last_update': None
            }

        stats = self.symbol_stats[metric.symbol]
        stats['total_metrics'] += 1
        if metric.is_healthy:
            stats['healthy_metrics'] += 1
        stats['last_update'] = metric.timestamp

        # Проверяем на аномалии
        self._check_for_anomalies(metric)

    def add_alert(self, alert: AnomalyAlert):
        """Добавляет алерт"""
        # Проверяем кулдаун
        alert_key = f"{alert.source}_{alert.alert_type}_{alert.symbol}"
        now = time.time()

        if alert_key in self.alert_cooldown:
            if now - self.alert_cooldown[alert_key] < 300:  # 5 минут кулдаун
                return

        self.alert_cooldown[alert_key] = now
        self.alerts_history.append(alert)

        # Логируем алерт
        logger.warning(f"DATA QUALITY ALERT [{alert.severity.upper()}]: {alert.message}")

        # Отправляем критические алерты в Telegram (если настроено)
        if alert.severity in ['high', 'critical']:
            self._send_critical_alert(alert)

    def _check_for_anomalies(self, metric: QualityMetric):
        """Проверяет метрику на аномалии"""
        # Проверяем отклонение цены
        if metric.metric_type == 'price_accuracy':
            if not metric.is_healthy and metric.value > self.thresholds['price_deviation_pct']:
                self.add_alert(AnomalyAlert(
                    timestamp=metric.timestamp,
                    symbol=metric.symbol,
                    source=metric.source,
                    alert_type='price_spike',
                    severity='medium' if metric.value < 10.0 else 'high',
                    message=f"Price deviation {metric.value:.2f}% exceeds threshold for {metric.symbol}",
                    data={'deviation_pct': metric.value, 'threshold': metric.threshold}
                ))

        # Проверяем отклонение объема
        elif metric.metric_type == 'volume_consistency':
            if not metric.is_healthy and metric.value > self.thresholds['volume_deviation_pct']:
                self.add_alert(AnomalyAlert(
                    timestamp=metric.timestamp,
                    symbol=metric.symbol,
                    source=metric.source,
                    alert_type='volume_anomaly',
                    severity='medium',
                    message=f"Volume deviation {metric.value:.2f}% exceeds threshold for {metric.symbol}",
                    data={'deviation_pct': metric.value, 'threshold': metric.threshold}
                ))

        # Проверяем задержку
        elif metric.metric_type == 'latency':
            if not metric.is_healthy and metric.value > self.thresholds['latency_ms']:
                self.add_alert(AnomalyAlert(
                    timestamp=metric.timestamp,
                    symbol=metric.symbol,
                    source=metric.source,
                    alert_type='high_latency',
                    severity='low',
                    message=f"High latency {metric.value:.0f}ms for {metric.source}",
                    data={'latency_ms': metric.value, 'threshold': metric.threshold}
                ))

        # Проверяем доступность
        elif metric.metric_type == 'availability':
            if not metric.is_healthy:
                self.add_alert(AnomalyAlert(
                    timestamp=metric.timestamp,
                    symbol=metric.symbol,
                    source=metric.source,
                    alert_type='source_down',
                    severity='high',
                    message=f"Data source {metric.source} is down",
                    data={'availability': metric.value}
                ))

    def _send_critical_alert(self, alert: AnomalyAlert):
        """Отправляет критический алерт"""
        try:
            # Здесь можно добавить отправку в Telegram или другие системы мониторинга
            # Пока просто логируем
            logger.critical(f"CRITICAL DATA QUALITY ISSUE: {alert.message}")

            # TODO: Интегрировать с системой уведомлений
            # await send_telegram_alert(alert)

        except Exception as e:
            logger.error(f"Error sending critical alert: {e}")

    def get_source_health_score(self, source: str) -> float:
        """Возвращает оценку здоровья источника (0.0 - 1.0)"""
        if source not in self.source_stats:
            return 0.0

        stats = self.source_stats[source]
        if stats['total_metrics'] == 0:
            return 0.0

        health_score = stats['healthy_metrics'] / stats['total_metrics']

        # Штрафуем за давние обновления
        if stats['last_update']:
            time_since_update = get_utc_now() - stats['last_update']
            if time_since_update > timedelta(minutes=10):
                health_score *= 0.5  # 50% штраф за отсутствие обновлений > 10 минут
            elif time_since_update > timedelta(minutes=5):
                health_score *= 0.8  # 20% штраф за отсутствие обновлений > 5 минут

        return health_score

    def get_symbol_health_score(self, symbol: str) -> float:
        """Возвращает оценку здоровья символа (0.0 - 1.0)"""
        if symbol not in self.symbol_stats:
            return 0.0

        stats = self.symbol_stats[symbol]
        if stats['total_metrics'] == 0:
            return 0.0

        return stats['healthy_metrics'] / stats['total_metrics']

    def get_recent_alerts(self, hours: int = 24) -> List[AnomalyAlert]:
        """Возвращает недавние алерты"""
        cutoff_time = get_utc_now() - timedelta(hours=hours)
        return [alert for alert in self.alerts_history if alert.timestamp >= cutoff_time]

    def get_health_report(self) -> Dict:
        """Возвращает отчет о здоровье системы"""
        now = get_utc_now()

        # Статистика по источникам
        source_health = {}
        for source in self.source_stats:
            source_health[source] = {
                'health_score': self.get_source_health_score(source),
                'total_metrics': self.source_stats[source]['total_metrics'],
                'healthy_metrics': self.source_stats[source]['healthy_metrics'],
                'last_update': self.source_stats[source]['last_update'].isoformat() if self.source_stats[source]['last_update'] else None
            }

        # Статистика по символам
        symbol_health = {}
        for symbol in self.symbol_stats:
            symbol_health[symbol] = {
                'health_score': self.get_symbol_health_score(symbol),
                'total_metrics': self.symbol_stats[symbol]['total_metrics'],
                'healthy_metrics': self.symbol_stats[symbol]['healthy_metrics']
            }

        # Недавние алерты
        recent_alerts = self.get_recent_alerts(24)
        alerts_by_severity = {}
        for alert in recent_alerts:
            if alert.severity not in alerts_by_severity:
                alerts_by_severity[alert.severity] = 0
            alerts_by_severity[alert.severity] += 1

        # Общая оценка здоровья системы
        overall_health = 0.0
        if source_health:
            overall_health = statistics.mean([s['health_score'] for s in source_health.values()])

        return {
            'timestamp': now.isoformat(),
            'overall_health_score': overall_health,
            'source_health': source_health,
            'symbol_health': symbol_health,
            'recent_alerts_24h': {
                'total': len(recent_alerts),
                'by_severity': alerts_by_severity
            },
            'monitoring_enabled': self.monitoring_enabled,
            'thresholds': self.thresholds
        }

    def update_thresholds(self, new_thresholds: Dict[str, float]):
        """Обновляет пороги для детекции аномалий"""
        for key, value in new_thresholds.items():
            if key in self.thresholds:
                self.thresholds[key] = value
                logger.info(f"Updated threshold {key}: {value}")

    def reset_statistics(self):
        """Сбрасывает статистику"""
        self.metrics_history.clear()
        self.alerts_history.clear()
        self.source_stats.clear()
        self.symbol_stats.clear()
        self.alert_cooldown.clear()
        logger.info("Data quality statistics reset")

class DataQualityAnalyzer:
    """Анализатор качества данных"""

    def __init__(self, monitor: DataQualityMonitor):
        self.monitor = monitor

    def analyze_price_consistency(self, symbol: str, hours: int = 24) -> Dict:
        """Анализирует консистентность цен"""
        cutoff_time = get_utc_now() - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.monitor.metrics_history
            if m.symbol == symbol and m.metric_type == 'price_accuracy' and m.timestamp >= cutoff_time
        ]

        if not recent_metrics:
            return {'error': 'No price data available'}

        deviations = [m.value for m in recent_metrics]
        healthy_count = sum(1 for m in recent_metrics if m.is_healthy)

        return {
            'symbol': symbol,
            'period_hours': hours,
            'total_measurements': len(recent_metrics),
            'healthy_measurements': healthy_count,
            'health_rate': healthy_count / len(recent_metrics) if recent_metrics else 0,
            'avg_deviation': statistics.mean(deviations) if deviations else 0,
            'max_deviation': max(deviations) if deviations else 0,
            'min_deviation': min(deviations) if deviations else 0,
            'std_deviation': statistics.stdev(deviations) if len(deviations) > 1 else 0
        }

    def analyze_source_reliability(self, source: str, hours: int = 24) -> Dict:
        """Анализирует надежность источника"""
        cutoff_time = get_utc_now() - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.monitor.metrics_history
            if m.source == source and m.timestamp >= cutoff_time
        ]

        if not recent_metrics:
            return {'error': 'No data available'}

        # Группируем по типам метрик
        metrics_by_type = {}
        for metric in recent_metrics:
            if metric.metric_type not in metrics_by_type:
                metrics_by_type[metric.metric_type] = []
            metrics_by_type[metric.metric_type].append(metric)

        # Анализируем каждый тип
        analysis = {
            'source': source,
            'period_hours': hours,
            'total_measurements': len(recent_metrics),
            'metrics_by_type': {}
        }

        for metric_type, metrics in metrics_by_type.items():
            healthy_count = sum(1 for m in metrics if m.is_healthy)
            values = [m.value for m in metrics]

            analysis['metrics_by_type'][metric_type] = {
                'total': len(metrics),
                'healthy': healthy_count,
                'health_rate': healthy_count / len(metrics) if metrics else 0,
                'avg_value': statistics.mean(values) if values else 0,
                'std_value': statistics.stdev(values) if len(values) > 1 else 0
            }

        # Общая оценка надежности
        overall_healthy = sum(1 for m in recent_metrics if m.is_healthy)
        analysis['overall_reliability'] = overall_healthy / len(recent_metrics) if recent_metrics else 0

        return analysis

    def detect_trending_issues(self, hours: int = 24) -> List[Dict]:
        """Детектирует нарастающие проблемы"""
        cutoff_time = get_utc_now() - timedelta(hours=hours)
        recent_metrics = [
            m for m in self.monitor.metrics_history
            if m.timestamp >= cutoff_time
        ]

        # Группируем по источникам и символам
        source_issues = {}
        symbol_issues = {}

        for metric in recent_metrics:
            if not metric.is_healthy:
                # Проблемы по источникам
                if metric.source not in source_issues:
                    source_issues[metric.source] = []
                source_issues[metric.source].append(metric)

                # Проблемы по символам
                if metric.symbol not in symbol_issues:
                    symbol_issues[metric.symbol] = []
                symbol_issues[metric.symbol].append(metric)

        trending_issues = []

        # Анализируем источники с проблемами
        for source, issues in source_issues.items():
            if len(issues) >= 5:  # Минимум 5 проблем за период
                issue_rate = len(issues) / hours  # Проблем в час
                if issue_rate >= 0.5:  # Более 0.5 проблем в час
                    trending_issues.append({
                        'type': 'source_degradation',
                        'entity': source,
                        'issue_count': len(issues),
                        'issue_rate_per_hour': issue_rate,
                        'severity': 'high' if issue_rate >= 2.0 else 'medium'
                    })

        # Анализируем символы с проблемами
        for symbol, issues in symbol_issues.items():
            if len(issues) >= 3:  # Минимум 3 проблемы за период
                issue_rate = len(issues) / hours
                if issue_rate >= 0.3:  # Более 0.3 проблем в час
                    trending_issues.append({
                        'type': 'symbol_issues',
                        'entity': symbol,
                        'issue_count': len(issues),
                        'issue_rate_per_hour': issue_rate,
                        'severity': 'high' if issue_rate >= 1.0 else 'medium'
                    })

        return trending_issues

# Глобальный экземпляр монитора
data_quality_monitor = DataQualityMonitor()

# Удобные функции
def add_price_accuracy_metric(symbol: str, source: str, deviation_pct: float, threshold: float = 1.0):
    """Добавляет метрику точности цены"""
    metric = QualityMetric(
        timestamp=get_utc_now(),
        symbol=symbol,
        source=source,
        metric_type='price_accuracy',
        value=deviation_pct,
        threshold=threshold,
        is_healthy=deviation_pct <= threshold
    )
    data_quality_monitor.add_metric(metric)

def add_volume_consistency_metric(symbol: str, source: str, deviation_pct: float, threshold: float = 50.0):
    """Добавляет метрику консистентности объема"""
    metric = QualityMetric(
        timestamp=get_utc_now(),
        symbol=symbol,
        source=source,
        metric_type='volume_consistency',
        value=deviation_pct,
        threshold=threshold,
        is_healthy=deviation_pct <= threshold
    )
    data_quality_monitor.add_metric(metric)

def add_latency_metric(symbol: str, source: str, latency_ms: float, threshold: float = 1000.0):
    """Добавляет метрику задержки"""
    metric = QualityMetric(
        timestamp=get_utc_now(),
        symbol=symbol,
        source=source,
        metric_type='latency',
        value=latency_ms,
        threshold=threshold,
        is_healthy=latency_ms <= threshold
    )
    data_quality_monitor.add_metric(metric)

def add_availability_metric(symbol: str, source: str, is_available: bool):
    """Добавляет метрику доступности"""
    metric = QualityMetric(
        timestamp=get_utc_now(),
        symbol=symbol,
        source=source,
        metric_type='availability',
        value=1.0 if is_available else 0.0,
        threshold=0.5,
        is_healthy=is_available
    )
    data_quality_monitor.add_metric(metric)

def get_health_report() -> Dict:
    """Возвращает отчет о здоровье данных"""
    return data_quality_monitor.get_health_report()

def get_source_health_score(source: str) -> float:
    """Возвращает оценку здоровья источника"""
    return data_quality_monitor.get_source_health_score(source)

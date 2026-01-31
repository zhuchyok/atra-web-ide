#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📊 РАСШИРЕННЫЙ МОНИТОРИНГ ПРОИЗВОДИТЕЛЬНОСТИ
P95/P99 latency tracking, throughput monitoring, memory usage, CPU utilization
"""

import asyncio
import logging
import psutil
import time
import statistics
from collections import deque, defaultdict
from datetime import datetime
from src.shared.utils.datetime_utils import get_utc_now
from typing import Dict, Any, Optional
import json

logger = logging.getLogger(__name__)

class PerformanceMetrics:
    """Класс для хранения метрик производительности"""
    
    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        
        # Latency метрики
        self.latency_samples = deque(maxlen=window_size)
        self.p95_latency = 0.0
        self.p99_latency = 0.0
        self.avg_latency = 0.0
        
        # Throughput метрики
        self.requests_per_second = deque(maxlen=60)  # 60 секунд
        self.current_rps = 0.0
        self.peak_rps = 0.0
        
        # Memory метрики
        self.memory_usage = deque(maxlen=window_size)
        self.peak_memory = 0.0
        self.current_memory = 0.0
        
        # CPU метрики
        self.cpu_usage = deque(maxlen=window_size)
        self.avg_cpu = 0.0
        self.peak_cpu = 0.0
        
        # Error метрики
        self.error_count = 0
        self.error_rate = 0.0
        self.last_error_time = None
        
        # Timestamps
        self.last_update = get_utc_now()
        self.start_time = get_utc_now()

class ComponentPerformanceTracker:
    """Трекер производительности для отдельного компонента"""
    
    def __init__(self, component_name: str):
        self.component_name = component_name
        self.metrics = PerformanceMetrics()
        self.operation_times = defaultdict(list)
        self.operation_counts = defaultdict(int)
        self.operation_errors = defaultdict(int)
        
    def record_operation(self, operation_name: str, duration: float, success: bool = True):
        """Записывает метрику операции"""
        self.operation_times[operation_name].append(duration)
        self.operation_counts[operation_name] += 1
        
        if not success:
            self.operation_errors[operation_name] += 1
            self.metrics.error_count += 1
            self.metrics.last_error_time = get_utc_now()
        
        # Обновляем общие метрики
        self.metrics.latency_samples.append(duration)
        self._update_percentiles()
        
    def _update_percentiles(self):
        """Обновляет перцентили latency"""
        if len(self.metrics.latency_samples) > 0:
            sorted_latencies = sorted(self.metrics.latency_samples)
            n = len(sorted_latencies)
            
            self.metrics.p95_latency = sorted_latencies[int(n * 0.95)]
            self.metrics.p99_latency = sorted_latencies[int(n * 0.99)]
            self.metrics.avg_latency = statistics.mean(sorted_latencies)
    
    def get_operation_stats(self, operation_name: str) -> Dict[str, Any]:
        """Возвращает статистику по операции"""
        if operation_name not in self.operation_times:
            return {}
        
        times = self.operation_times[operation_name]
        if not times:
            return {}
        
        return {
            'count': self.operation_counts[operation_name],
            'avg_duration': statistics.mean(times),
            'min_duration': min(times),
            'max_duration': max(times),
            'p95_duration': sorted(times)[int(len(times) * 0.95)] if len(times) > 0 else 0,
            'error_count': self.operation_errors[operation_name],
            'error_rate': self.operation_errors[operation_name] / self.operation_counts[operation_name] if self.operation_counts[operation_name] > 0 else 0
        }

class AdvancedPerformanceMonitor:
    """Расширенный мониторинг производительности системы"""
    
    def __init__(self, update_interval: float = 1.0):
        self.update_interval = update_interval
        self.components: Dict[str, ComponentPerformanceTracker] = {}
        self.system_metrics = PerformanceMetrics()
        
        # Фоновые задачи
        self.monitoring_task = None
        self.is_running = False
        
        # Статистика
        self.stats = {
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'uptime': 0,
            'last_reset': get_utc_now()
        }
        
        # Алерты
        self.alert_thresholds = {
            'p95_latency': 5.0,  # 5 секунд
            'p99_latency': 10.0,  # 10 секунд
            'error_rate': 0.05,  # 5%
            'memory_usage': 0.9,  # 90%
            'cpu_usage': 0.9  # 90%
        }
        
        self.active_alerts = set()
        
    def register_component(self, component_name: str) -> ComponentPerformanceTracker:
        """Регистрирует компонент для мониторинга"""
        if component_name not in self.components:
            self.components[component_name] = ComponentPerformanceTracker(component_name)
            logger.info("Зарегистрирован компонент для мониторинга: %s", component_name)
        return self.components[component_name]
    
    def record_operation(self, component_name: str, operation_name: str, 
                        duration: float, success: bool = True):
        """Записывает операцию компонента"""
        if component_name not in self.components:
            self.register_component(component_name)
        
        self.components[component_name].record_operation(operation_name, duration, success)
        
        # Обновляем общую статистику
        self.stats['total_operations'] += 1
        if success:
            self.stats['successful_operations'] += 1
        else:
            self.stats['failed_operations'] += 1
    
    def _update_system_metrics(self):
        """Обновляет системные метрики"""
        try:
            # Memory usage
            memory_info = psutil.virtual_memory()
            memory_percent = memory_info.percent / 100.0
            self.system_metrics.current_memory = memory_percent
            self.system_metrics.memory_usage.append(memory_percent)
            
            if memory_percent > self.system_metrics.peak_memory:
                self.system_metrics.peak_memory = memory_percent
            
            # CPU usage
            cpu_percent = psutil.cpu_percent() / 100.0
            self.system_metrics.cpu_usage.append(cpu_percent)
            self.system_metrics.avg_cpu = statistics.mean(self.system_metrics.cpu_usage)
            
            if cpu_percent > self.system_metrics.peak_cpu:
                self.system_metrics.peak_cpu = cpu_percent
            
            # Error rate
            if self.stats['total_operations'] > 0:
                self.system_metrics.error_rate = self.stats['failed_operations'] / self.stats['total_operations']
            
            self.system_metrics.last_update = get_utc_now()
            
        except Exception as e:
            logger.error("Ошибка обновления системных метрик: %s", e)
    
    def _check_alerts(self):
        """Проверяет пороги алертов"""
        alerts = []
        
        # Проверяем системные метрики
        if self.system_metrics.current_memory > self.alert_thresholds['memory_usage']:
            alert = f"HIGH_MEMORY_USAGE: {self.system_metrics.current_memory:.1%}"
            if alert not in self.active_alerts:
                alerts.append(alert)
                self.active_alerts.add(alert)
        
        if self.system_metrics.avg_cpu > self.alert_thresholds['cpu_usage']:
            alert = f"HIGH_CPU_USAGE: {self.system_metrics.avg_cpu:.1%}"
            if alert not in self.active_alerts:
                alerts.append(alert)
                self.active_alerts.add(alert)
        
        if self.system_metrics.error_rate > self.alert_thresholds['error_rate']:
            alert = f"HIGH_ERROR_RATE: {self.system_metrics.error_rate:.1%}"
            if alert not in self.active_alerts:
                alerts.append(alert)
                self.active_alerts.add(alert)
        
        # Проверяем метрики компонентов
        for component_name, tracker in self.components.items():
            if tracker.metrics.p95_latency > self.alert_thresholds['p95_latency']:
                alert = f"HIGH_P95_LATENCY_{component_name}: {tracker.metrics.p95_latency:.2f}s"
                if alert not in self.active_alerts:
                    alerts.append(alert)
                    self.active_alerts.add(alert)
            
            if tracker.metrics.p99_latency > self.alert_thresholds['p99_latency']:
                alert = f"HIGH_P99_LATENCY_{component_name}: {tracker.metrics.p99_latency:.2f}s"
                if alert not in self.active_alerts:
                    alerts.append(alert)
                    self.active_alerts.add(alert)
        
        # Очищаем старые алерты
        self.active_alerts.clear()
        for alert in alerts:
            self.active_alerts.add(alert)
        
        return alerts
    
    async def _monitoring_loop(self):
        """Основной цикл мониторинга"""
        logger.info("Запуск расширенного мониторинга производительности")
        
        while self.is_running:
            try:
                # Обновляем системные метрики
                self._update_system_metrics()
                
                # Проверяем алерты
                alerts = self._check_alerts()
                if alerts:
                    for alert in alerts:
                        logger.warning("🚨 PERFORMANCE ALERT: %s", alert)
                
                # Обновляем uptime
                self.stats['uptime'] = (get_utc_now() - self.stats['last_reset']).total_seconds()
                
                await asyncio.sleep(self.update_interval)
                
            except Exception as e:
                logger.error("Ошибка в цикле мониторинга: %s", e)
                await asyncio.sleep(self.update_interval)
    
    async def start_monitoring(self):
        """Запускает мониторинг"""
        if self.is_running:
            logger.warning("Мониторинг уже запущен")
            return
        
        self.is_running = True
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("✅ Расширенный мониторинг производительности запущен")
    
    async def stop_monitoring(self):
        """Останавливает мониторинг"""
        self.is_running = False
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Расширенный мониторинг производительности остановлен")
    
    def get_comprehensive_report(self) -> Dict[str, Any]:
        """Возвращает комплексный отчет о производительности"""
        report = {
            'timestamp': get_utc_now().isoformat(),
            'system_metrics': {
                'memory_usage': {
                    'current': self.system_metrics.current_memory,
                    'peak': self.system_metrics.peak_memory,
                    'avg': statistics.mean(self.system_metrics.memory_usage) if self.system_metrics.memory_usage else 0
                },
                'cpu_usage': {
                    'current': self.system_metrics.cpu_usage[-1] if self.system_metrics.cpu_usage else 0,
                    'avg': self.system_metrics.avg_cpu,
                    'peak': self.system_metrics.peak_cpu
                },
                'error_rate': self.system_metrics.error_rate,
                'uptime_seconds': self.stats['uptime']
            },
            'components': {},
            'operations': {
                'total': self.stats['total_operations'],
                'successful': self.stats['successful_operations'],
                'failed': self.stats['failed_operations'],
                'success_rate': (self.stats['successful_operations'] / self.stats['total_operations'] * 100) if self.stats['total_operations'] > 0 else 0
            },
            'active_alerts': list(self.active_alerts)
        }
        
        # Добавляем метрики компонентов
        for component_name, tracker in self.components.items():
            report['components'][component_name] = {
                'latency': {
                    'avg': tracker.metrics.avg_latency,
                    'p95': tracker.metrics.p95_latency,
                    'p99': tracker.metrics.p99_latency
                },
                'operations': {}
            }
            
            # Добавляем статистику операций
            for operation_name in tracker.operation_counts:
                report['components'][component_name]['operations'][operation_name] = tracker.get_operation_stats(operation_name)
        
        return report
    
    def save_report_to_file(self, filename: Optional[str] = None):
        """Сохраняет отчет в файл"""
        if filename is None:
            timestamp = get_utc_now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_report_{timestamp}.json"
        
        report = self.get_comprehensive_report()
        
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info("Отчет о производительности сохранен: %s", filename)
        except Exception as e:
            logger.error("Ошибка сохранения отчета: %s", e)
    
    def reset_metrics(self):
        """Сбрасывает все метрики"""
        for tracker in self.components.values():
            tracker.metrics = PerformanceMetrics()
            tracker.operation_times.clear()
            tracker.operation_counts.clear()
            tracker.operation_errors.clear()
        
        self.system_metrics = PerformanceMetrics()
        self.stats.update({
            'total_operations': 0,
            'successful_operations': 0,
            'failed_operations': 0,
            'last_reset': get_utc_now()
        })
        self.active_alerts.clear()
        
        logger.info("Метрики производительности сброшены")

# Глобальный экземпляр мониторинга
advanced_performance_monitor = AdvancedPerformanceMonitor()

# Декораторы для автоматического мониторинга
def monitor_performance(component_name: str, operation_name: str):
    """Декоратор для автоматического мониторинга производительности"""
    def decorator(func):
        async def async_wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start_time
                advanced_performance_monitor.record_operation(component_name, operation_name, duration, success)
        
        def sync_wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration = time.time() - start_time
                advanced_performance_monitor.record_operation(component_name, operation_name, duration, success)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

# Контекстный менеджер для мониторинга
class PerformanceContext:
    """Контекстный менеджер для мониторинга производительности"""
    
    def __init__(self, component_name: str, operation_name: str):
        self.component_name = component_name
        self.operation_name = operation_name
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time
            success = exc_type is None
            advanced_performance_monitor.record_operation(
                self.component_name, self.operation_name, duration, success
            )

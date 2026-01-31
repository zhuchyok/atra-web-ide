"""
Метрики для Prometheus - Victoria Enhanced
Экспорт метрик использования компонентов
"""

import time
from typing import Dict, Optional
from collections import defaultdict
from datetime import datetime, timezone

try:
    from prometheus_client import Counter, Histogram, Gauge, start_http_server
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False

class EnhancedMetrics:
    """Метрики для Victoria Enhanced"""
    
    def __init__(self, port: int = 9091):
        self.port = port
        self.enabled = PROMETHEUS_AVAILABLE
        
        if not self.enabled:
            return
        
        # Счетчики
        self.tasks_total = Counter(
            'victoria_enhanced_tasks_total',
            'Total number of tasks processed',
            ['category', 'method', 'status']
        )
        
        self.method_selections = Counter(
            'victoria_enhanced_method_selections_total',
            'Total method selections',
            ['method', 'category']
        )
        
        # Гистограммы (время выполнения)
        self.task_duration = Histogram(
            'victoria_enhanced_task_duration_seconds',
            'Task processing duration',
            ['category', 'method'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0]
        )
        
        self.method_duration = Histogram(
            'victoria_enhanced_method_duration_seconds',
            'Method execution duration',
            ['method'],
            buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0]
        )
        
        # Gauges (текущие значения)
        self.active_tasks = Gauge(
            'victoria_enhanced_active_tasks',
            'Currently active tasks'
        )
        
        self.component_availability = Gauge(
            'victoria_enhanced_component_available',
            'Component availability',
            ['component']
        )
        
        # Статистика использования
        self.usage_stats = defaultdict(int)
        
        # Запуск HTTP сервера для метрик
        try:
            start_http_server(self.port)
            print(f"✅ Prometheus metrics server started on port {self.port}")
        except Exception as e:
            print(f"⚠️ Failed to start metrics server: {e}")
    
    def record_task(
        self,
        category: str,
        method: str,
        duration: float,
        status: str = "success"
    ):
        """Записать метрику задачи"""
        if not self.enabled:
            return
        
        self.tasks_total.labels(
            category=category,
            method=method,
            status=status
        ).inc()
        
        self.task_duration.labels(
            category=category,
            method=method
        ).observe(duration)
        
        self.usage_stats[f"{category}:{method}"] += 1
    
    def record_method_selection(self, method: str, category: str):
        """Записать выбор метода"""
        if not self.enabled:
            return
        
        self.method_selections.labels(
            method=method,
            category=category
        ).inc()
    
    def record_method_execution(self, method: str, duration: float):
        """Записать выполнение метода"""
        if not self.enabled:
            return
        
        self.method_duration.labels(method=method).observe(duration)
    
    def set_component_availability(self, component: str, available: bool):
        """Установить доступность компонента"""
        if not self.enabled:
            return
        
        self.component_availability.labels(component=component).set(1 if available else 0)
    
    def increment_active_tasks(self):
        """Увеличить счетчик активных задач"""
        if not self.enabled:
            return
        self.active_tasks.inc()
    
    def decrement_active_tasks(self):
        """Уменьшить счетчик активных задач"""
        if not self.enabled:
            return
        self.active_tasks.dec()
    
    def get_usage_stats(self) -> Dict[str, int]:
        """Получить статистику использования"""
        return dict(self.usage_stats)

# Глобальный экземпляр
_metrics_instance: Optional[EnhancedMetrics] = None

def get_metrics() -> EnhancedMetrics:
    """Получить глобальный экземпляр метрик"""
    global _metrics_instance
    if _metrics_instance is None:
        port = int(os.getenv("METRICS_PORT", "9091"))
        _metrics_instance = EnhancedMetrics(port=port)
    return _metrics_instance

"""
Мониторинг производительности системы
"""

import time
import psutil
import threading
import logging
from typing import Dict, List, Any, Optional, Callable
from dataclasses import dataclass, field
from collections import deque
import json
from datetime import datetime, timedelta
from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetrics:
    """Метрики производительности"""
    timestamp: datetime = field(default_factory=get_utc_now)
    cpu_percent: float = 0.0
    memory_usage_mb: float = 0.0
    memory_available_mb: float = 0.0
    disk_usage_percent: float = 0.0
    network_io_bytes: int = 0
    active_threads: int = 0
    active_processes: int = 0
    load_average: float = 0.0


@dataclass
class ApplicationMetrics:
    """Метрики приложения"""
    timestamp: datetime = field(default_factory=get_utc_now)
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    max_response_time: float = 0.0
    min_response_time: float = float('inf')
    requests_per_second: float = 0.0
    error_rate: float = 0.0


class PerformanceMonitor:
    """Монитор производительности"""
    
    def __init__(self, monitoring_interval: int = 5, max_history: int = 1000):
        self.monitoring_interval = monitoring_interval
        self.max_history = max_history
        self.is_monitoring = False
        self.monitor_thread = None
        
        # История метрик
        self.performance_history: deque = deque(maxlen=max_history)
        self.application_history: deque = deque(maxlen=max_history)
        
        # Текущие метрики
        self.current_performance = PerformanceMetrics()
        self.current_application = ApplicationMetrics()
        
        # Счетчики
        self.request_times: List[float] = []
        self.error_count = 0
        self.success_count = 0
        
        # Алерты
        self.alert_thresholds = {
            'cpu_percent': 80.0,
            'memory_usage_mb': 1024.0,
            'disk_usage_percent': 90.0,
            'error_rate': 0.1,
            'avg_response_time': 5.0
        }
        
        self.alert_callbacks: List[Callable] = []
        
        # Начальные значения для расчета
        self.last_network_io = psutil.net_io_counters()
        self.last_timestamp = time.time()
    
    def start_monitoring(self):
        """Запуск мониторинга"""
        if self.is_monitoring:
            logger.warning("Мониторинг уже запущен")
            return
        
        self.is_monitoring = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        
        logger.info("Мониторинг производительности запущен")
    
    def stop_monitoring(self):
        """Остановка мониторинга"""
        if not self.is_monitoring:
            logger.warning("Мониторинг не запущен")
            return
        
        self.is_monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)
        
        logger.info("Мониторинг производительности остановлен")
    
    def _monitor_loop(self):
        """Основной цикл мониторинга"""
        while self.is_monitoring:
            try:
                # Сбор метрик производительности
                self._collect_performance_metrics()
                
                # Сбор метрик приложения
                self._collect_application_metrics()
                
                # Проверка алертов
                self._check_alerts()
                
                # Ожидание следующего цикла
                time.sleep(self.monitoring_interval)
                
            except Exception as e:
                logger.error(f"Ошибка в цикле мониторинга: {e}")
                time.sleep(self.monitoring_interval)
    
    def _collect_performance_metrics(self):
        """Сбор метрик производительности"""
        try:
            # Системные метрики
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            # Сетевые метрики
            network_io = psutil.net_io_counters()
            network_bytes = network_io.bytes_sent + network_io.bytes_recv
            
            # Процессы и потоки
            active_threads = threading.active_count()
            active_processes = len(psutil.pids())
            
            # Нагрузка системы
            try:
                load_avg = psutil.getloadavg()[0]
            except AttributeError:
                load_avg = 0.0
            
            # Создание объекта метрик
            metrics = PerformanceMetrics(
                timestamp=get_utc_now(),
                cpu_percent=cpu_percent,
                memory_usage_mb=memory.used / 1024 / 1024,
                memory_available_mb=memory.available / 1024 / 1024,
                disk_usage_percent=disk.percent,
                network_io_bytes=network_bytes,
                active_threads=active_threads,
                active_processes=active_processes,
                load_average=load_avg
            )
            
            # Обновление текущих метрик
            self.current_performance = metrics
            
            # Добавление в историю
            self.performance_history.append(metrics)
            
            logger.debug(f"Метрики производительности собраны: CPU={cpu_percent:.1f}%, "
                        f"Memory={metrics.memory_usage_mb:.1f}MB")
            
        except Exception as e:
            logger.error(f"Ошибка сбора метрик производительности: {e}")
    
    def _collect_application_metrics(self):
        """Сбор метрик приложения"""
        try:
            # Расчет метрик на основе счетчиков
            total_requests = self.success_count + self.error_count
            error_rate = self.error_count / max(total_requests, 1)
            
            # Расчет времени ответа
            avg_response_time = 0.0
            max_response_time = 0.0
            min_response_time = float('inf')
            
            if self.request_times:
                avg_response_time = sum(self.request_times) / len(self.request_times)
                max_response_time = max(self.request_times)
                min_response_time = min(self.request_times)
            
            # Расчет RPS
            current_time = time.time()
            time_diff = current_time - self.last_timestamp
            requests_per_second = total_requests / max(time_diff, 1)
            
            # Создание объекта метрик
            metrics = ApplicationMetrics(
                timestamp=get_utc_now(),
                total_requests=total_requests,
                successful_requests=self.success_count,
                failed_requests=self.error_count,
                avg_response_time=avg_response_time,
                max_response_time=max_response_time,
                min_response_time=min_response_time,
                requests_per_second=requests_per_second,
                error_rate=error_rate
            )
            
            # Обновление текущих метрик
            self.current_application = metrics
            
            # Добавление в историю
            self.application_history.append(metrics)
            
            logger.debug(f"Метрики приложения собраны: RPS={requests_per_second:.2f}, "
                        f"Error Rate={error_rate:.2%}")
            
        except Exception as e:
            logger.error(f"Ошибка сбора метрик приложения: {e}")
    
    def _check_alerts(self):
        """Проверка алертов"""
        try:
            perf = self.current_performance
            app = self.current_application
            
            # Проверка алертов производительности
            if perf.cpu_percent > self.alert_thresholds['cpu_percent']:
                self._trigger_alert('high_cpu', f"Высокая загрузка CPU: {perf.cpu_percent:.1f}%")
            
            if perf.memory_usage_mb > self.alert_thresholds['memory_usage_mb']:
                self._trigger_alert('high_memory', f"Высокое использование памяти: {perf.memory_usage_mb:.1f}MB")
            
            if perf.disk_usage_percent > self.alert_thresholds['disk_usage_percent']:
                self._trigger_alert('high_disk', f"Высокое использование диска: {perf.disk_usage_percent:.1f}%")
            
            # Проверка алертов приложения
            if app.error_rate > self.alert_thresholds['error_rate']:
                self._trigger_alert('high_error_rate', f"Высокий уровень ошибок: {app.error_rate:.2%}")
            
            if app.avg_response_time > self.alert_thresholds['avg_response_time']:
                self._trigger_alert('slow_response', f"Медленный ответ: {app.avg_response_time:.2f}s")
            
        except Exception as e:
            logger.error(f"Ошибка проверки алертов: {e}")
    
    def _trigger_alert(self, alert_type: str, message: str):
        """Срабатывание алерта"""
        try:
            alert_data = {
                'type': alert_type,
                'message': message,
                'timestamp': get_utc_now().isoformat(),
                'performance': self.current_performance.__dict__,
                'application': self.current_application.__dict__
            }
            
            # Вызов callback'ов
            for callback in self.alert_callbacks:
                try:
                    callback(alert_data)
                except Exception as e:
                    logger.error(f"Ошибка в callback алерта: {e}")
            
            logger.warning(f"Алерт: {message}")
            
        except Exception as e:
            logger.error(f"Ошибка срабатывания алерта: {e}")
    
    def record_request(self, success: bool, response_time: float):
        """Запись запроса"""
        try:
            if success:
                self.success_count += 1
            else:
                self.error_count += 1
            
            self.request_times.append(response_time)
            
            # Ограничение размера списка времени ответа
            if len(self.request_times) > 1000:
                self.request_times = self.request_times[-500:]
            
        except Exception as e:
            logger.error(f"Ошибка записи запроса: {e}")
    
    def add_alert_callback(self, callback: Callable):
        """Добавление callback для алертов"""
        self.alert_callbacks.append(callback)
    
    def set_alert_threshold(self, metric: str, threshold: float):
        """Установка порога алерта"""
        if metric in self.alert_thresholds:
            self.alert_thresholds[metric] = threshold
            logger.info(f"Порог алерта установлен: {metric} = {threshold}")
        else:
            logger.warning(f"Неизвестная метрика для алерта: {metric}")
    
    def get_current_metrics(self) -> Dict[str, Any]:
        """Получение текущих метрик"""
        return {
            'performance': self.current_performance.__dict__,
            'application': self.current_application.__dict__,
            'timestamp': get_utc_now().isoformat()
        }
    
    def get_historical_metrics(self, hours: int = 1) -> Dict[str, List[Dict[str, Any]]]:
        """Получение исторических метрик"""
        try:
            cutoff_time = get_utc_now() - timedelta(hours=hours)
            
            # Фильтрация метрик по времени
            perf_history = [
                m.__dict__ for m in self.performance_history 
                if m.timestamp >= cutoff_time
            ]
            
            app_history = [
                m.__dict__ for m in self.application_history 
                if m.timestamp >= cutoff_time
            ]
            
            return {
                'performance': perf_history,
                'application': app_history
            }
            
        except Exception as e:
            logger.error(f"Ошибка получения исторических метрик: {e}")
            return {'performance': [], 'application': []}
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Получение сводки производительности"""
        try:
            if not self.performance_history:
                return {}
            
            # Расчет статистики
            cpu_values = [m.cpu_percent for m in self.performance_history]
            memory_values = [m.memory_usage_mb for m in self.performance_history]
            
            perf_summary = {
                'cpu': {
                    'current': self.current_performance.cpu_percent,
                    'avg': sum(cpu_values) / len(cpu_values),
                    'max': max(cpu_values),
                    'min': min(cpu_values)
                },
                'memory': {
                    'current': self.current_performance.memory_usage_mb,
                    'avg': sum(memory_values) / len(memory_values),
                    'max': max(memory_values),
                    'min': min(memory_values)
                },
                'uptime': len(self.performance_history) * self.monitoring_interval,
                'data_points': len(self.performance_history)
            }
            
            return perf_summary
            
        except Exception as e:
            logger.error(f"Ошибка получения сводки производительности: {e}")
            return {}
    
    def export_metrics(self, filename: str = None) -> str:
        """Экспорт метрик в JSON"""
        try:
            now = get_utc_now()
            if filename is None:
                filename = f"metrics_{now.strftime('%Y%m%d_%H%M%S')}.json"
            
            # Подготовка данных для экспорта
            export_data = {
                'export_timestamp': now.isoformat(),
                'current_metrics': self.get_current_metrics(),
                'performance_summary': self.get_performance_summary(),
                'historical_performance': [
                    m.__dict__ for m in self.performance_history
                ],
                'historical_application': [
                    m.__dict__ for m in self.application_history
                ]
            }
            
            # Сохранение в файл
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, default=str)
            
            logger.info(f"Метрики экспортированы в {filename}")
            return filename
            
        except Exception as e:
            logger.error(f"Ошибка экспорта метрик: {e}")
            return ""


# Глобальный экземпляр монитора
performance_monitor = PerformanceMonitor()


def start_performance_monitoring():
    """Запуск мониторинга производительности"""
    performance_monitor.start_monitoring()


def stop_performance_monitoring():
    """Остановка мониторинга производительности"""
    performance_monitor.stop_monitoring()


def record_request_metrics(success: bool, response_time: float):
    """Запись метрик запроса"""
    performance_monitor.record_request(success, response_time)


def get_performance_metrics() -> Dict[str, Any]:
    """Получение метрик производительности"""
    return performance_monitor.get_current_metrics()


def monitor_performance(func: Callable):
    """Декоратор для мониторинга производительности функции"""
    def wrapper(*args, **kwargs):
        start_time = time.time()
        success = True
        
        try:
            result = func(*args, **kwargs)
            return result
        except Exception as e:
            success = False
            logger.error(f"Ошибка в функции {func.__name__}: {e}")
            raise
        finally:
            response_time = time.time() - start_time
            record_request_metrics(success, response_time)
    
    return wrapper

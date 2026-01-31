"""
Модуль для сбора и анализа метрик эффективности фильтров
"""

import time
import logging
from datetime import datetime, timedelta
from src.shared.utils.datetime_utils import get_utc_now
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
import pandas as pd
import numpy as np
from enum import Enum

logger = logging.getLogger(__name__)


class FilterType(Enum):
    """Типы фильтров"""
    BB_FILTER = "bb_filter"
    EMA_FILTER = "ema_filter"
    RSI_FILTER = "rsi_filter"
    MACD_FILTER = "macd_filter"  # 🆕 MACD фильтр
    VOLUME_FILTER = "volume_filter"
    AI_FILTER = "ai_filter"
    NEWS_FILTER = "news_filter"
    BTC_TREND_FILTER = "btc_trend_filter"
    WHALE_FILTER = "whale_filter"
    # 🆕 Institutional Indicators filters
    AMT_FILTER = "amt_filter"
    MARKET_PROFILE_FILTER = "market_profile_filter"
    INSTITUTIONAL_PATTERNS_FILTER = "institutional_patterns_filter"


@dataclass
class FilterMetrics:
    """Метрики эффективности фильтра"""
    filter_type: FilterType
    total_signals: int = 0
    passed_signals: int = 0
    rejected_signals: int = 0
    processing_time: float = 0.0
    success_rate: float = 0.0
    rejection_rate: float = 0.0
    avg_processing_time: float = 0.0
    last_updated: datetime = field(default_factory=get_utc_now)
    
    def update_metrics(self, passed: bool, processing_time: float):
        """Обновление метрик"""
        self.total_signals += 1
        if passed:
            self.passed_signals += 1
        else:
            self.rejected_signals += 1
        
        self.processing_time += processing_time
        self.avg_processing_time = self.processing_time / self.total_signals
        self.success_rate = self.passed_signals / self.total_signals if self.total_signals > 0 else 0.0
        self.rejection_rate = self.rejected_signals / self.total_signals if self.total_signals > 0 else 0.0
        self.last_updated = get_utc_now()


@dataclass
class FilterPerformance:
    """Производительность фильтра"""
    filter_type: FilterType
    min_processing_time: float = float('inf')
    max_processing_time: float = 0.0
    avg_processing_time: float = 0.0
    processing_times: deque = field(default_factory=lambda: deque(maxlen=1000))
    
    def add_processing_time(self, processing_time: float):
        """Добавление времени обработки"""
        self.processing_times.append(processing_time)
        self.min_processing_time = min(self.min_processing_time, processing_time)
        self.max_processing_time = max(self.max_processing_time, processing_time)
        self.avg_processing_time = np.mean(list(self.processing_times))


class FilterMetricsCollector:
    """Сборщик метрик фильтров"""
    
    def __init__(self):
        self.metrics: Dict[FilterType, FilterMetrics] = {}
        self.performance: Dict[FilterType, FilterPerformance] = {}
        self.rejection_reasons: Dict[FilterType, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.time_series: Dict[FilterType, List[Tuple[datetime, Dict[str, Any]]]] = defaultdict(list)
        
        # Инициализация метрик для всех типов фильтров
        for filter_type in FilterType:
            self.metrics[filter_type] = FilterMetrics(filter_type=filter_type)
            self.performance[filter_type] = FilterPerformance(filter_type=filter_type)
    
    def record_filter_result(self, 
                           filter_type: FilterType, 
                           passed: bool, 
                           processing_time: float,
                           rejection_reason: Optional[str] = None):
        """Запись результата фильтра"""
        try:
            # Обновление основных метрик
            self.metrics[filter_type].update_metrics(passed, processing_time)
            
            # Обновление метрик производительности
            self.performance[filter_type].add_processing_time(processing_time)
            
            # Запись причины отклонения
            if not passed and rejection_reason:
                self.rejection_reasons[filter_type][rejection_reason] += 1
            
            # Запись временного ряда
            self.time_series[filter_type].append((
                get_utc_now(),
                {
                    'passed': passed,
                    'processing_time': processing_time,
                    'rejection_reason': rejection_reason
                }
            ))
            
            # Ограничение размера временного ряда
            if len(self.time_series[filter_type]) > 10000:
                self.time_series[filter_type] = self.time_series[filter_type][-5000:]
            
            logger.debug(f"Метрики фильтра {filter_type.value} обновлены: "
                        f"passed={passed}, time={processing_time:.4f}s")
            
        except Exception as e:
            logger.error(f"Ошибка при записи метрик фильтра {filter_type.value}: {e}")
    
    def get_filter_metrics(self, filter_type: FilterType) -> FilterMetrics:
        """Получение метрик фильтра"""
        return self.metrics.get(filter_type, FilterMetrics(filter_type=filter_type))
    
    def get_filter_performance(self, filter_type: FilterType) -> FilterPerformance:
        """Получение метрик производительности фильтра"""
        return self.performance.get(filter_type, FilterPerformance(filter_type=filter_type))
    
    def get_rejection_reasons(self, filter_type: FilterType) -> Dict[str, int]:
        """Получение причин отклонения фильтра"""
        return dict(self.rejection_reasons[filter_type])
    
    def get_top_rejection_reasons(self, filter_type: FilterType, limit: int = 5) -> List[Tuple[str, int]]:
        """Получение топ причин отклонения"""
        reasons = self.get_rejection_reasons(filter_type)
        return sorted(reasons.items(), key=lambda x: x[1], reverse=True)[:limit]
    
    def get_time_series_data(self, 
                           filter_type: FilterType, 
                           start_time: Optional[datetime] = None,
                           end_time: Optional[datetime] = None) -> List[Tuple[datetime, Dict[str, Any]]]:
        """Получение данных временного ряда"""
        data = self.time_series[filter_type]
        
        if start_time:
            data = [(dt, metrics) for dt, metrics in data if dt >= start_time]
        
        if end_time:
            data = [(dt, metrics) for dt, metrics in data if dt <= end_time]
        
        return data
    
    def get_aggregated_metrics(self, 
                             start_time: Optional[datetime] = None,
                             end_time: Optional[datetime] = None) -> Dict[str, Any]:
        """Получение агрегированных метрик"""
        try:
            total_signals = 0
            total_passed = 0
            total_rejected = 0
            total_processing_time = 0.0
            
            filter_breakdown = {}
            
            for filter_type in FilterType:
                metrics = self.get_filter_metrics(filter_type)
                
                # Фильтрация по времени
                if start_time and metrics.last_updated < start_time:
                    continue
                if end_time and metrics.last_updated > end_time:
                    continue
                
                total_signals += metrics.total_signals
                total_passed += metrics.passed_signals
                total_rejected += metrics.rejected_signals
                total_processing_time += metrics.processing_time
                
                filter_breakdown[filter_type.value] = {
                    'total_signals': metrics.total_signals,
                    'passed_signals': metrics.passed_signals,
                    'rejected_signals': metrics.rejected_signals,
                    'success_rate': metrics.success_rate,
                    'rejection_rate': metrics.rejection_rate,
                    'avg_processing_time': metrics.avg_processing_time
                }
            
            overall_success_rate = total_passed / total_signals if total_signals > 0 else 0.0
            overall_rejection_rate = total_rejected / total_signals if total_signals > 0 else 0.0
            overall_avg_processing_time = total_processing_time / total_signals if total_signals > 0 else 0.0
            
            return {
                'total_signals': total_signals,
                'total_passed': total_passed,
                'total_rejected': total_rejected,
                'overall_success_rate': overall_success_rate,
                'overall_rejection_rate': overall_rejection_rate,
                'overall_avg_processing_time': overall_avg_processing_time,
                'filter_breakdown': filter_breakdown,
                'timestamp': get_utc_now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Ошибка при получении агрегированных метрик: {e}")
            return {}
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Получение сводки производительности"""
        try:
            performance_summary = {}
            
            for filter_type in FilterType:
                perf = self.get_filter_performance(filter_type)
                
                if perf.processing_times:
                    performance_summary[filter_type.value] = {
                        'min_processing_time': perf.min_processing_time,
                        'max_processing_time': perf.max_processing_time,
                        'avg_processing_time': perf.avg_processing_time,
                        'samples_count': len(perf.processing_times),
                        'std_processing_time': np.std(list(perf.processing_times)) if len(perf.processing_times) > 1 else 0.0
                    }
                else:
                    performance_summary[filter_type.value] = {
                        'min_processing_time': 0.0,
                        'max_processing_time': 0.0,
                        'avg_processing_time': 0.0,
                        'samples_count': 0,
                        'std_processing_time': 0.0
                    }
            
            return performance_summary
            
        except Exception as e:
            logger.error(f"Ошибка при получении сводки производительности: {e}")
            return {}
    
    def get_efficiency_report(self) -> Dict[str, Any]:
        """Получение отчета об эффективности"""
        try:
            report = {
                'timestamp': get_utc_now().isoformat(),
                'filters': {},
                'overall': {},
                'recommendations': []
            }
            
            # Анализ каждого фильтра
            for filter_type in FilterType:
                metrics = self.get_filter_metrics(filter_type)
                performance = self.get_filter_performance(filter_type)
                rejection_reasons = self.get_top_rejection_reasons(filter_type, 3)
                
                report['filters'][filter_type.value] = {
                    'metrics': {
                        'total_signals': metrics.total_signals,
                        'passed_signals': metrics.passed_signals,
                        'rejected_signals': metrics.rejected_signals,
                        'success_rate': metrics.success_rate,
                        'rejection_rate': metrics.rejection_rate
                    },
                    'performance': {
                        'avg_processing_time': performance.avg_processing_time,
                        'min_processing_time': performance.min_processing_time,
                        'max_processing_time': performance.max_processing_time
                    },
                    'top_rejection_reasons': rejection_reasons
                }
            
            # Общие метрики
            aggregated = self.get_aggregated_metrics()
            report['overall'] = aggregated
            
            # Рекомендации
            recommendations = self._generate_recommendations()
            report['recommendations'] = recommendations
            
            return report
            
        except Exception as e:
            logger.error(f"Ошибка при создании отчета об эффективности: {e}")
            return {'error': str(e)}
    
    def _generate_recommendations(self) -> List[str]:
        """Генерация рекомендаций по оптимизации"""
        recommendations = []
        
        try:
            # Анализ производительности
            performance_summary = self.get_performance_summary()
            
            for filter_type, perf in performance_summary.items():
                if perf['samples_count'] > 0:
                    # Рекомендации по производительности
                    if perf['avg_processing_time'] > 0.1:  # Более 100мс
                        recommendations.append(
                            f"Фильтр {filter_type} работает медленно "
                            f"({perf['avg_processing_time']:.3f}s). "
                            "Рекомендуется оптимизация."
                        )
                    
                    # Рекомендации по стабильности
                    if perf['std_processing_time'] > perf['avg_processing_time'] * 0.5:
                        recommendations.append(
                            f"Фильтр {filter_type} имеет нестабильную производительность "
                            f"(std: {perf['std_processing_time']:.3f}s). "
                            "Рекомендуется анализ алгоритма."
                        )
            
            # Анализ эффективности
            aggregated = self.get_aggregated_metrics()
            
            if aggregated:
                # Рекомендации по успешности
                if aggregated['overall_success_rate'] < 0.1:  # Менее 10%
                    recommendations.append(
                        "Общая успешность фильтров очень низкая "
                        f"({aggregated['overall_success_rate']:.1%}). "
                        "Рекомендуется пересмотр параметров фильтров."
                    )
                
                # Рекомендации по отклонениям
                if aggregated['overall_rejection_rate'] > 0.9:  # Более 90%
                    recommendations.append(
                        "Слишком много отклонений "
                        f"({aggregated['overall_rejection_rate']:.1%}). "
                        "Рекомендуется ослабление критериев фильтрации."
                    )
            
        except Exception as e:
            logger.error(f"Ошибка при генерации рекомендаций: {e}")
            recommendations.append(f"Ошибка при анализе: {e}")
        
        return recommendations
    
    def export_metrics_to_csv(self, filepath: str):
        """Экспорт метрик в CSV"""
        try:
            data = []
            
            for filter_type in FilterType:
                metrics = self.get_filter_metrics(filter_type)
                performance = self.get_filter_performance(filter_type)
                
                data.append({
                    'filter_type': filter_type.value,
                    'total_signals': metrics.total_signals,
                    'passed_signals': metrics.passed_signals,
                    'rejected_signals': metrics.rejected_signals,
                    'success_rate': metrics.success_rate,
                    'rejection_rate': metrics.rejection_rate,
                    'avg_processing_time': metrics.avg_processing_time,
                    'min_processing_time': performance.min_processing_time,
                    'max_processing_time': performance.max_processing_time,
                    'last_updated': metrics.last_updated.isoformat()
                })
            
            df = pd.DataFrame(data)
            df.to_csv(filepath, index=False)
            
            logger.info(f"Метрики экспортированы в {filepath}")
            
        except Exception as e:
            logger.error(f"Ошибка при экспорте метрик в CSV: {e}")
    
    def reset_metrics(self, filter_type: Optional[FilterType] = None):
        """Сброс метрик"""
        try:
            if filter_type:
                # Сброс метрик конкретного фильтра
                self.metrics[filter_type] = FilterMetrics(filter_type=filter_type)
                self.performance[filter_type] = FilterPerformance(filter_type=filter_type)
                self.rejection_reasons[filter_type] = defaultdict(int)
                self.time_series[filter_type] = []
            else:
                # Сброс всех метрик
                for ft in FilterType:
                    self.metrics[ft] = FilterMetrics(filter_type=ft)
                    self.performance[ft] = FilterPerformance(filter_type=ft)
                    self.rejection_reasons[ft] = defaultdict(int)
                    self.time_series[ft] = []
            
            logger.info(f"Метрики сброшены для {filter_type.value if filter_type else 'всех фильтров'}")
            
        except Exception as e:
            logger.error(f"Ошибка при сбросе метрик: {e}")


# Глобальный экземпляр сборщика метрик
filter_metrics_collector = FilterMetricsCollector()


def record_filter_metrics(filter_type: FilterType, 
                         passed: bool, 
                         processing_time: float,
                         rejection_reason: Optional[str] = None):
    """Удобная функция для записи метрик фильтра"""
    filter_metrics_collector.record_filter_result(
        filter_type, passed, processing_time, rejection_reason
    )


def get_filter_metrics(filter_type: FilterType) -> FilterMetrics:
    """Удобная функция для получения метрик фильтра"""
    return filter_metrics_collector.get_filter_metrics(filter_type)


def get_efficiency_report() -> Dict[str, Any]:
    """Удобная функция для получения отчета об эффективности"""
    return filter_metrics_collector.get_efficiency_report()

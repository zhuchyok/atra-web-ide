"""
Профилирование и анализ медленных SQL запросов.

Логирует все запросы, которые выполняются дольше заданного порога,
и анализирует планы выполнения для выявления узких мест.
"""

import logging
import time
import sqlite3
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from src.shared.utils.datetime_utils import get_utc_now

logger = logging.getLogger(__name__)


@dataclass
class QueryProfile:
    """Профиль выполнения запроса"""
    query: str
    params: Any
    execution_time: float
    timestamp: datetime
    plan: Optional[str] = None
    rows_affected: Optional[int] = None
    error: Optional[str] = None


class QueryProfiler:
    """Профилировщик SQL запросов"""
    
    def __init__(self, slow_query_threshold: float = 1.0, enable_profiling: bool = True):
        """
        Args:
            slow_query_threshold: Порог для медленных запросов (секунды)
            enable_profiling: Включить профилирование
        """
        self.slow_query_threshold = slow_query_threshold
        self.enable_profiling = enable_profiling
        self.slow_queries: List[QueryProfile] = []
        self.query_stats: Dict[str, Dict[str, Any]] = {}
        self.total_queries = 0
        self.total_slow_queries = 0
    
    @contextmanager
    def profile_query(self, query: str, params: Any = None, conn: Optional[sqlite3.Connection] = None):
        """
        Контекстный менеджер для профилирования запроса
        
        Usage:
            with profiler.profile_query("SELECT * FROM table", (param,), conn) as result:
                # выполнение запроса
        """
        if not self.enable_profiling:
            yield None
            return
        
        start_time = time.time()
        error = None
        plan = None
        rows_affected = None
        
        try:
            # Получаем план выполнения, если есть соединение
            if conn is not None:
                try:
                    cursor = conn.cursor()
                    explain_query = f"EXPLAIN QUERY PLAN {query}"
                    if params:
                        cursor.execute(explain_query, params)
                    else:
                        cursor.execute(explain_query)
                    plan_rows = cursor.fetchall()
                    plan = "\n".join([str(row) for row in plan_rows])
                except Exception as e:
                    logger.debug(f"Не удалось получить план выполнения: {e}")
            
            yield None
            
            # Получаем количество затронутых строк
            if conn is not None:
                try:
                    rows_affected = conn.total_changes
                except Exception:
                    pass
        
        except Exception as e:
            error = str(e)
            raise
        finally:
            execution_time = time.time() - start_time
            self.total_queries += 1
            
            # Логируем медленные запросы
            if execution_time >= self.slow_query_threshold:
                self.total_slow_queries += 1
                profile = QueryProfile(
                    query=query,
                    params=params,
                    execution_time=execution_time,
                    timestamp=get_utc_now(),
                    plan=plan,
                    rows_affected=rows_affected,
                    error=error,
                )
                self.slow_queries.append(profile)
                
                # Логируем медленный запрос
                logger.warning(
                    f"⚠️ [QueryProfiler] Медленный запрос ({execution_time:.3f}s):\n"
                    f"Query: {query[:200]}...\n"
                    f"Params: {params}\n"
                    f"Plan: {plan}\n"
                    f"Rows: {rows_affected}"
                )
            
            # Обновляем статистику
            query_key = self._get_query_key(query)
            if query_key not in self.query_stats:
                self.query_stats[query_key] = {
                    'count': 0,
                    'total_time': 0.0,
                    'max_time': 0.0,
                    'min_time': float('inf'),
                    'avg_time': 0.0,
                }
            
            stats = self.query_stats[query_key]
            stats['count'] += 1
            stats['total_time'] += execution_time
            stats['max_time'] = max(stats['max_time'], execution_time)
            stats['min_time'] = min(stats['min_time'], execution_time)
            stats['avg_time'] = stats['total_time'] / stats['count']
    
    def _get_query_key(self, query: str) -> str:
        """Получить ключ для группировки похожих запросов"""
        # Убираем параметры и нормализуем запрос
        normalized = query.strip().upper()
        # Берем первые 100 символов как ключ
        return normalized[:100]
    
    def get_slow_queries(self, limit: int = 100) -> List[QueryProfile]:
        """Получить список медленных запросов"""
        return sorted(
            self.slow_queries,
            key=lambda x: x.execution_time,
            reverse=True
        )[:limit]
    
    def get_query_statistics(self) -> Dict[str, Dict[str, Any]]:
        """Получить статистику по запросам"""
        return self.query_stats
    
    def get_summary(self) -> Dict[str, Any]:
        """Получить сводку по профилированию"""
        return {
            'total_queries': self.total_queries,
            'slow_queries': self.total_slow_queries,
            'slow_query_percentage': (
                (self.total_slow_queries / self.total_queries * 100)
                if self.total_queries > 0
                else 0.0
            ),
            'unique_queries': len(self.query_stats),
            'top_slow_queries': [
                {
                    'query': q.query[:200],
                    'time': q.execution_time,
                    'timestamp': q.timestamp.isoformat(),
                }
                for q in self.get_slow_queries(limit=10)
            ],
        }
    
    def reset(self):
        """Сбросить статистику"""
        self.slow_queries.clear()
        self.query_stats.clear()
        self.total_queries = 0
        self.total_slow_queries = 0


# Глобальный экземпляр профилировщика
_profiler_instance: Optional[QueryProfiler] = None


def get_query_profiler() -> QueryProfiler:
    """Получить глобальный экземпляр профилировщика"""
    global _profiler_instance
    if _profiler_instance is None:
        _profiler_instance = QueryProfiler(
            slow_query_threshold=1.0,
            enable_profiling=True,
        )
    return _profiler_instance


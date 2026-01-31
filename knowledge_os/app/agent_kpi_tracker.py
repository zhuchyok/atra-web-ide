"""
Agent KPI Tracker
Система KPI и метрик производительности для каждого агента
AGENT IMPROVEMENTS: KPI и метрики производительности
"""

import asyncio
import logging
import os
import json
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
from collections import defaultdict

logger = logging.getLogger(__name__)

# Database connection
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

@dataclass
class AgentKPI:
    """KPI агента"""
    agent_id: str
    kpi_type: str  # 'signal_accuracy', 'execution_speed', 'error_rate', etc.
    value: float
    target_value: float  # Целевое значение
    unit: str  # '%', 'seconds', 'count', etc.
    period: str  # 'daily', 'weekly', 'monthly'
    calculated_at: datetime

@dataclass
class AgentMetrics:
    """Метрики производительности агента"""
    agent_id: str
    total_tasks: int
    completed_tasks: int
    failed_tasks: int
    avg_execution_time: float
    success_rate: float
    quality_score: float
    kpis: List[AgentKPI]
    last_updated: datetime

class AgentKPITracker:
    """
    Система KPI и метрик производительности.
    
    Функционал:
    - Персональные KPI для каждого агента
    - Dashboard с метриками производительности
    - Автоматические алерты при падении метрик
    - Система геймификации (бейджи, достижения)
    """
    
    def __init__(self, db_url: str = DB_URL):
        """
        Args:
            db_url: URL базы данных
        """
        self.db_url = db_url
        self._metrics_cache: Dict[str, AgentMetrics] = {}
        self._kpi_definitions: Dict[str, Dict[str, Any]] = {
            # KPI для разных агентов
            'signal_live': {
                'signal_accuracy': {'target': 0.75, 'unit': '%', 'weight': 0.4},
                'win_rate': {'target': 0.70, 'unit': '%', 'weight': 0.3},
                'profit_factor': {'target': 1.5, 'unit': 'x', 'weight': 0.3}
            },
            'auto_execution': {
                'execution_speed': {'target': 2.0, 'unit': 'seconds', 'weight': 0.3},
                'success_rate': {'target': 0.95, 'unit': '%', 'weight': 0.4},
                'error_rate': {'target': 0.05, 'unit': '%', 'weight': 0.3}
            },
            'risk_manager': {
                'risk_prevented': {'target': 10, 'unit': 'count', 'weight': 0.4},
                'response_time': {'target': 0.5, 'unit': 'seconds', 'weight': 0.3},
                'portfolio_health': {'target': 0.8, 'unit': '%', 'weight': 0.3}
            }
        }
        
    async def _get_conn(self):
        """Получить подключение к БД"""
        if not ASYNCPG_AVAILABLE:
            logger.error("asyncpg is not installed. Database connection unavailable.")
            return None
        try:
            conn = await asyncpg.connect(self.db_url)
            return conn
        except Exception as e:
            logger.error(f"❌ [KPI TRACKER] Ошибка подключения к БД: {e}")
            return None
    
    async def calculate_agent_kpis(self, agent_id: str, period: str = 'daily') -> List[AgentKPI]:
        """
        Рассчитывает KPI для агента.
        
        Args:
            agent_id: ID агента
            period: Период ('daily', 'weekly', 'monthly')
        
        Returns:
            Список AgentKPI
        """
        try:
            conn = await self._get_conn()
            if not conn:
                return []
            
            try:
                kpi_definitions = self._kpi_definitions.get(agent_id, {})
                kpis = []
                
                # Для signal_live агента
                if agent_id == 'signal_live':
                    # Signal accuracy
                    accuracy_data = await conn.fetchrow("""
                        SELECT 
                            COUNT(*) FILTER (WHERE result = 'WIN') * 100.0 / COUNT(*) as win_rate,
                            AVG(CASE WHEN result = 'WIN' THEN 1.0 ELSE 0.0 END) as accuracy
                        FROM signals_log
                        WHERE created_at > NOW() - INTERVAL '1 day'
                    """)
                    if accuracy_data:
                        accuracy = float(accuracy_data['accuracy'] or 0)
                        kpis.append(AgentKPI(
                            agent_id=agent_id,
                            kpi_type='signal_accuracy',
                            value=accuracy,
                            target_value=kpi_definitions.get('signal_accuracy', {}).get('target', 0.75),
                            unit='%',
                            period=period,
                            calculated_at=datetime.now(timezone.utc)
                        ))
                
                # Для auto_execution агента
                elif agent_id == 'auto_execution':
                    # Success rate
                    execution_data = await conn.fetchrow("""
                        SELECT 
                            COUNT(*) FILTER (WHERE status = 'completed') * 100.0 / COUNT(*) as success_rate,
                            AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_time
                        FROM execution_log
                        WHERE created_at > NOW() - INTERVAL '1 day'
                    """)
                    if execution_data:
                        success_rate = float(execution_data['success_rate'] or 0)
                        kpis.append(AgentKPI(
                            agent_id=agent_id,
                            kpi_type='success_rate',
                            value=success_rate / 100.0,
                            target_value=kpi_definitions.get('success_rate', {}).get('target', 0.95),
                            unit='%',
                            period=period,
                            calculated_at=datetime.now(timezone.utc)
                        ))
                
                # Общие метрики для всех агентов
                task_data = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE status = 'completed') as completed,
                        COUNT(*) FILTER (WHERE status = 'failed') as failed,
                        AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_time
                    FROM agent_tasks
                    WHERE agent_id = $1
                    AND created_at > NOW() - INTERVAL '1 day'
                """, agent_id)
                
                if task_data:
                    total = task_data['total'] or 0
                    completed = task_data['completed'] or 0
                    success_rate = completed / total if total > 0 else 0.0
                    
                    kpis.append(AgentKPI(
                        agent_id=agent_id,
                        kpi_type='task_success_rate',
                        value=success_rate,
                        target_value=0.90,
                        unit='%',
                        period=period,
                        calculated_at=datetime.now(timezone.utc)
                    ))
                
                return kpis
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [KPI TRACKER] Ошибка расчета KPI для {agent_id}: {e}")
            return []
    
    async def get_agent_metrics(self, agent_id: str) -> Optional[AgentMetrics]:
        """
        Получает метрики производительности агента.
        
        Args:
            agent_id: ID агента
        
        Returns:
            AgentMetrics или None
        """
        # Проверяем кэш
        if agent_id in self._metrics_cache:
            metrics = self._metrics_cache[agent_id]
            if (datetime.now(timezone.utc) - metrics.last_updated).total_seconds() < 300:  # 5 минут
                return metrics
        
        try:
            conn = await self._get_conn()
            if not conn:
                return None
            
            try:
                # Получаем общие метрики
                task_stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE status = 'completed') as completed,
                        COUNT(*) FILTER (WHERE status = 'failed') as failed,
                        AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_time,
                        AVG(quality_score) as avg_quality
                    FROM agent_tasks
                    WHERE agent_id = $1
                    AND created_at > NOW() - INTERVAL '30 days'
                """, agent_id)
                
                if not task_stats:
                    return None
                
                total = task_stats['total'] or 0
                completed = task_stats['completed'] or 0
                failed = task_stats['failed'] or 0
                avg_time = float(task_stats['avg_time'] or 0)
                quality_score = float(task_stats['avg_quality'] or 3.0)
                success_rate = completed / total if total > 0 else 0.0
                
                # Рассчитываем KPI
                kpis = await self.calculate_agent_kpis(agent_id)
                
                metrics = AgentMetrics(
                    agent_id=agent_id,
                    total_tasks=total,
                    completed_tasks=completed,
                    failed_tasks=failed,
                    avg_execution_time=avg_time,
                    success_rate=success_rate,
                    quality_score=quality_score,
                    kpis=kpis,
                    last_updated=datetime.now(timezone.utc)
                )
                
                # Обновляем кэш
                self._metrics_cache[agent_id] = metrics
                
                return metrics
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [KPI TRACKER] Ошибка получения метрик для {agent_id}: {e}")
            return None
    
    async def check_kpi_alerts(self, agent_id: str) -> List[str]:
        """
        Проверяет KPI и возвращает алерты при падении метрик.
        
        Args:
            agent_id: ID агента
        
        Returns:
            Список сообщений об алертах
        """
        alerts = []
        
        metrics = await self.get_agent_metrics(agent_id)
        if not metrics:
            return alerts
        
        # Проверяем каждый KPI
        for kpi in metrics.kpis:
            # Если значение ниже целевого на 20%
            threshold = kpi.target_value * 0.8
            if kpi.value < threshold:
                alert_msg = (
                    f"⚠️ [KPI ALERT] {agent_id}: {kpi.kpi_type} = {kpi.value:.2f}{kpi.unit} "
                    f"(цель: {kpi.target_value:.2f}{kpi.unit}, падение: {(1 - kpi.value/kpi.target_value)*100:.1f}%)"
                )
                alerts.append(alert_msg)
                logger.warning(alert_msg)
        
        return alerts
    
    async def get_dashboard_data(self) -> Dict[str, Any]:
        """
        Получает данные для dashboard с метриками производительности.
        
        Returns:
            Словарь с данными для dashboard
        """
        try:
            # Список всех агентов
            agent_ids = ['signal_live', 'auto_execution', 'risk_manager', 'price_monitor']
            
            dashboard_data = {
                'agents': [],
                'overall_metrics': {
                    'total_agents': len(agent_ids),
                    'agents_on_target': 0,
                    'agents_below_target': 0
                }
            }
            
            for agent_id in agent_ids:
                metrics = await self.get_agent_metrics(agent_id)
                if metrics:
                    # Проверяем, достиг ли агент целевых значений
                    on_target = all(
                        kpi.value >= kpi.target_value * 0.9  # 90% от цели = на уровне
                        for kpi in metrics.kpis
                    )
                    
                    if on_target:
                        dashboard_data['overall_metrics']['agents_on_target'] += 1
                    else:
                        dashboard_data['overall_metrics']['agents_below_target'] += 1
                    
                    dashboard_data['agents'].append({
                        'agent_id': agent_id,
                        'metrics': {
                            'total_tasks': metrics.total_tasks,
                            'completed_tasks': metrics.completed_tasks,
                            'success_rate': metrics.success_rate,
                            'quality_score': metrics.quality_score,
                            'avg_execution_time': metrics.avg_execution_time
                        },
                        'kpis': [
                            {
                                'type': kpi.kpi_type,
                                'value': kpi.value,
                                'target': kpi.target_value,
                                'unit': kpi.unit,
                                'status': 'on_target' if kpi.value >= kpi.target_value * 0.9 else 'below_target'
                            }
                            for kpi in metrics.kpis
                        ],
                        'alerts': await self.check_kpi_alerts(agent_id)
                    })
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"❌ [KPI TRACKER] Ошибка получения dashboard данных: {e}")
            return {}

# Singleton instance
_kpi_tracker_instance: Optional[AgentKPITracker] = None

def get_agent_kpi_tracker(db_url: str = DB_URL) -> AgentKPITracker:
    """Получить singleton экземпляр AgentKPITracker"""
    global _kpi_tracker_instance
    if _kpi_tracker_instance is None:
        _kpi_tracker_instance = AgentKPITracker(db_url=db_url)
    return _kpi_tracker_instance


"""
Agent Self Assessment
Система самооценки и рефлексии агентов
AGENT IMPROVEMENTS: Система самооценки и рефлексии
"""

import asyncio
import logging
import os
import json
from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict

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
class SelfAssessment:
    """Самооценка агента"""
    assessment_id: str
    agent_id: str
    task_id: str
    performance_score: float  # 0.0-1.0
    strengths: List[str]  # Что получилось хорошо
    weaknesses: List[str]  # Что можно улучшить
    improvements: List[str]  # Конкретные улучшения
    confidence: float  # Уверенность в оценке (0.0-1.0)
    created_at: datetime

@dataclass
class ImprovementPlan:
    """План улучшений"""
    plan_id: str
    agent_id: str
    improvements: List[str]
    priority: str  # 'high', 'medium', 'low'
    target_date: Optional[datetime] = None
    progress: float = 0.0  # 0.0-1.0
    created_at: datetime = None

class AgentSelfAssessment:
    """
    Система самооценки и рефлексии.
    
    Функционал:
    - Автоматическая самооценка после задач
    - Рефлексия о том, что можно улучшить
    - Автоматическое планирование улучшений
    - Отслеживание прогресса
    """
    
    def __init__(self, db_url: str = DB_URL):
        """
        Args:
            db_url: URL базы данных
        """
        self.db_url = db_url
        
    async def _get_conn(self):
        """Получить подключение к БД"""
        if not ASYNCPG_AVAILABLE:
            logger.error("asyncpg is not installed. Database connection unavailable.")
            return None
        try:
            conn = await asyncpg.connect(self.db_url)
            return conn
        except Exception as e:
            logger.error(f"❌ [SELF ASSESSMENT] Ошибка подключения к БД: {e}")
            return None
    
    async def assess_task_performance(
        self,
        agent_id: str,
        task_id: str,
        task_result: Dict[str, Any]
    ) -> Optional[SelfAssessment]:
        """
        Оценивает производительность агента после выполнения задачи.
        
        Args:
            agent_id: ID агента
            task_id: ID задачи
            task_result: Результат выполнения задачи
        
        Returns:
            SelfAssessment или None
        """
        try:
            # Извлекаем метрики из результата
            success = task_result.get('success', False)
            execution_time = task_result.get('execution_time', 0)
            quality_score = task_result.get('quality_score', 0.5)
            error = task_result.get('error')
            
            # Рассчитываем performance_score
            performance_score = 0.0
            if success:
                performance_score += 0.5
            performance_score += quality_score * 0.3
            # Бонус за быстрый ответ (< 5 сек)
            if execution_time < 5.0:
                performance_score += 0.2
            else:
                performance_score += max(0, 0.2 * (10 - execution_time) / 10)
            
            performance_score = min(1.0, performance_score)
            
            # Определяем strengths и weaknesses
            strengths = []
            weaknesses = []
            improvements = []
            
            if success:
                strengths.append("Задача успешно выполнена")
            if quality_score > 0.8:
                strengths.append("Высокое качество результата")
            if execution_time < 5.0:
                strengths.append("Быстрое выполнение")
            
            if not success:
                weaknesses.append("Задача не выполнена")
                if error:
                    weaknesses.append(f"Ошибка: {error}")
            if quality_score < 0.6:
                weaknesses.append("Низкое качество результата")
                improvements.append("Улучшить качество проверки результата")
            if execution_time > 10.0:
                weaknesses.append("Медленное выполнение")
                improvements.append("Оптимизировать алгоритм выполнения")
            
            if not strengths:
                strengths.append("Задача выполнена в срок")
            
            # Генерируем assessment_id
            import hashlib
            assessment_key = f"{agent_id}:{task_id}:{datetime.now(timezone.utc).isoformat()}"
            assessment_id = hashlib.md5(assessment_key.encode()).hexdigest()[:16]
            
            assessment = SelfAssessment(
                assessment_id=assessment_id,
                agent_id=agent_id,
                task_id=task_id,
                performance_score=performance_score,
                strengths=strengths,
                weaknesses=weaknesses,
                improvements=improvements,
                confidence=0.8,  # Уверенность на основе метрик
                created_at=datetime.now(timezone.utc)
            )
            
            # Сохраняем в БД
            conn = await self._get_conn()
            if conn:
                try:
                    table_exists = await conn.fetchval("""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_name = 'agent_self_assessments'
                        )
                    """)
                    
                    if table_exists:
                        await conn.execute("""
                            INSERT INTO agent_self_assessments (assessment_id, agent_id, task_id, performance_score, strengths, weaknesses, improvements, confidence, created_at)
                            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                        """, assessment_id, agent_id, task_id, performance_score, json.dumps(strengths), json.dumps(weaknesses), json.dumps(improvements), 0.8, assessment.created_at)
                    
                    logger.info(f"✅ [SELF ASSESSMENT] Оценка {assessment_id} для агента {agent_id}: score={performance_score:.2f}")
                    return assessment
                    
                finally:
                    await conn.close()
            
            return assessment
            
        except Exception as e:
            logger.error(f"❌ [SELF ASSESSMENT] Ошибка оценки производительности: {e}")
            return None
    
    async def create_improvement_plan(
        self,
        agent_id: str,
        improvements: List[str],
        priority: str = 'medium'
    ) -> Optional[ImprovementPlan]:
        """
        Создает план улучшений на основе самооценки.
        
        Args:
            agent_id: ID агента
            improvements: Список улучшений
            priority: Приоритет ('high', 'medium', 'low')
        
        Returns:
            ImprovementPlan или None
        """
        try:
            # Генерируем plan_id
            import hashlib
            plan_key = f"{agent_id}:{':'.join(improvements)}:{datetime.now(timezone.utc).isoformat()}"
            plan_id = hashlib.md5(plan_key.encode()).hexdigest()[:16]
            
            plan = ImprovementPlan(
                plan_id=plan_id,
                agent_id=agent_id,
                improvements=improvements,
                priority=priority,
                target_date=datetime.now(timezone.utc) + timedelta(days=7),  # 7 дней на улучшения
                progress=0.0,
                created_at=datetime.now(timezone.utc)
            )
            
            # Сохраняем в БД
            conn = await self._get_conn()
            if conn:
                try:
                    table_exists = await conn.fetchval("""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_name = 'agent_improvement_plans'
                        )
                    """)
                    
                    if table_exists:
                        await conn.execute("""
                            INSERT INTO agent_improvement_plans (plan_id, agent_id, improvements, priority, target_date, progress, created_at)
                            VALUES ($1, $2, $3, $4, $5, $6, $7)
                        """, plan_id, agent_id, json.dumps(improvements), priority, plan.target_date, 0.0, plan.created_at)
                    
                    logger.info(f"✅ [SELF ASSESSMENT] Создан план улучшений {plan_id} для агента {agent_id}")
                    return plan
                    
                finally:
                    await conn.close()
            
            return plan
            
        except Exception as e:
            logger.error(f"❌ [SELF ASSESSMENT] Ошибка создания плана улучшений: {e}")
            return None
    
    async def get_agent_improvement_progress(self, agent_id: str) -> Dict[str, Any]:
        """
        Получает прогресс улучшений агента.
        
        Args:
            agent_id: ID агента
        
        Returns:
            Словарь с информацией о прогрессе
        """
        try:
            conn = await self._get_conn()
            if not conn:
                return {}
            
            try:
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'agent_improvement_plans'
                    )
                """)
                
                if not table_exists:
                    return {'total_plans': 0, 'completed_plans': 0, 'active_plans': []}
                
                # Получаем планы агента
                rows = await conn.fetch("""
                    SELECT plan_id, improvements, priority, progress, target_date, created_at
                    FROM agent_improvement_plans
                    WHERE agent_id = $1
                    ORDER BY created_at DESC
                """, agent_id)
                
                total_plans = len(rows)
                completed_plans = sum(1 for row in rows if row['progress'] >= 1.0)
                active_plans = [
                    {
                        'plan_id': row['plan_id'],
                        'improvements': json.loads(row['improvements']) if isinstance(row['improvements'], str) else row['improvements'],
                        'priority': row['priority'],
                        'progress': float(row['progress']),
                        'target_date': row['target_date'].isoformat() if row['target_date'] else None
                    }
                    for row in rows if row['progress'] < 1.0
                ]
                
                return {
                    'total_plans': total_plans,
                    'completed_plans': completed_plans,
                    'active_plans': active_plans,
                    'completion_rate': completed_plans / total_plans if total_plans > 0 else 0.0
                }
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [SELF ASSESSMENT] Ошибка получения прогресса: {e}")
            return {}

# Singleton instance
_self_assessment_instance: Optional[AgentSelfAssessment] = None

def get_agent_self_assessment(db_url: str = DB_URL) -> AgentSelfAssessment:
    """Получить singleton экземпляр AgentSelfAssessment"""
    global _self_assessment_instance
    if _self_assessment_instance is None:
        _self_assessment_instance = AgentSelfAssessment(db_url=db_url)
    return _self_assessment_instance


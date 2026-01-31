"""
Mentor System
Система менторства между агентами для передачи опыта
AGENT IMPROVEMENTS: Система менторства
"""

import asyncio
import logging
import os

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False
import json
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, asdict
from collections import defaultdict

logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

@dataclass
class AgentRating:
    """Рейтинг агента"""
    agent_id: str
    success_rate: float  # Процент успешных решений
    avg_quality_score: float  # Средний качественный балл
    total_tasks: int  # Общее количество задач
    solved_tasks: int  # Решенных задач
    failed_tasks: int  # Проваленных задач
    mentorship_score: float  # Балл менторства (на основе опыта)
    last_updated: datetime

@dataclass
class MentorAssignment:
    """Назначение ментора"""
    mentor_id: str  # ID ментора (senior)
    mentee_id: str  # ID подопечного (junior)
    assigned_at: datetime
    status: str  # 'active', 'completed', 'paused'
    guidance_count: int  # Количество переданных рекомендаций

class MentorSystem:
    """
    Система менторства между агентами.
    
    Функционал:
    - Система рейтинга агентов (на основе успешности решений)
    - Алгоритм назначения менторов (senior → junior)
    - Механизм передачи опыта через guidance
    - Автоматические рекомендации от менторов
    - Мониторинг эффективности менторства
    """
    
    def __init__(self, db_url: str = DB_URL):
        """
        Args:
            db_url: URL базы данных
        """
        self.db_url = db_url
        self._ratings_cache: Dict[str, AgentRating] = {}
        self._cache_ttl = 300  # 5 минут
        self._assignments_cache: Dict[str, MentorAssignment] = {}
        
    async def _get_conn(self):
        """Получить подключение к БД"""
        if not asyncpg:
            logger.error("asyncpg is not installed. Database connection unavailable.")
            return None
        try:
            conn = await asyncpg.connect(self.db_url)
            return conn
        except Exception as e:
            logger.error(f"❌ [MENTOR SYSTEM] Ошибка подключения к БД: {e}")
            return None
    
    async def calculate_agent_rating(self, agent_id: str) -> Optional[AgentRating]:
        """
        Рассчитывает рейтинг агента на основе успешности решений.
        
        Args:
            agent_id: ID агента
        
        Returns:
            AgentRating или None
        """
        # Проверяем кэш
        if agent_id in self._ratings_cache:
            rating = self._ratings_cache[agent_id]
            if (datetime.now(timezone.utc) - rating.last_updated).total_seconds() < self._cache_ttl:
                return rating
        
        conn = await self._get_conn()
        if not conn:
            return None
        
        try:
            # Проверяем наличие таблицы agent_ratings
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'agent_ratings'
                )
            """)
            
            if not table_exists:
                # Если таблицы нет, создаем дефолтный рейтинг
                return AgentRating(
                    agent_id=agent_id,
                    success_rate=0.5,
                    avg_quality_score=3.0,
                    total_tasks=0,
                    solved_tasks=0,
                    failed_tasks=0,
                    mentorship_score=0.0,
                    last_updated=datetime.now(timezone.utc)
                )
            
            # Получаем статистику агента из БД
            stats = await conn.fetchrow("""
                SELECT 
                    COUNT(*) FILTER (WHERE status = 'solved') as solved,
                    COUNT(*) FILTER (WHERE status = 'failed') as failed,
                    COUNT(*) as total,
                    AVG(quality_score) as avg_quality,
                    AVG(CASE WHEN status = 'solved' THEN 1.0 ELSE 0.0 END) as success_rate
                FROM agent_tasks
                WHERE agent_id = $1
                AND created_at > NOW() - INTERVAL '30 days'
            """, agent_id)
            
            if stats:
                solved = stats['solved'] or 0
                failed = stats['failed'] or 0
                total = stats['total'] or 0
                avg_quality = float(stats['avg_quality'] or 3.0)
                success_rate = float(stats['success_rate'] or 0.5)
            else:
                solved, failed, total = 0, 0, 0
                avg_quality = 3.0
                success_rate = 0.5
            
            # Рассчитываем mentorship_score на основе опыта
            # Больше опыта и лучше результаты = выше mentorship_score
            experience_score = min(total / 100.0, 1.0)  # Опыт (0-1)
            quality_score = avg_quality / 5.0  # Качество (0-1)
            mentorship_score = (experience_score * 0.4 + quality_score * 0.4 + success_rate * 0.2)
            
            rating = AgentRating(
                agent_id=agent_id,
                success_rate=success_rate,
                avg_quality_score=avg_quality,
                total_tasks=total,
                solved_tasks=solved,
                failed_tasks=failed,
                mentorship_score=mentorship_score,
                last_updated=datetime.now(timezone.utc)
            )
            
            # Обновляем кэш
            self._ratings_cache[agent_id] = rating
            
            return rating
            
        except Exception as e:
            logger.error(f"❌ [MENTOR SYSTEM] Ошибка расчета рейтинга для {agent_id}: {e}")
            return None
        finally:
            await conn.close()
    
    async def find_mentor_for_agent(self, mentee_id: str) -> Optional[str]:
        """
        Находит ментора для агента (senior → junior).
        
        Args:
            mentee_id: ID подопечного
        
        Returns:
            ID ментора или None
        """
        try:
            mentee_rating = await self.calculate_agent_rating(mentee_id)
            if not mentee_rating:
                return None
            
            # Ищем агентов с более высоким mentorship_score
            # Ментор должен иметь:
            # 1. mentorship_score > подопечного на 0.2+
            # 2. total_tasks > подопечного в 2+ раза
            # 3. success_rate > 0.6
            
            conn = await self._get_conn()
            if not conn:
                return None
            
            try:
                # Получаем список потенциальных менторов
                mentors = await conn.fetch("""
                    SELECT agent_id, mentorship_score, total_tasks, success_rate
                    FROM agent_ratings
                    WHERE mentorship_score > $1 + 0.2
                    AND total_tasks > $2 * 2
                    AND success_rate > 0.6
                    AND agent_id != $3
                    ORDER BY mentorship_score DESC
                    LIMIT 10
                """, mentee_rating.mentorship_score, mentee_rating.total_tasks, mentee_id)
                
                if not mentors:
                    logger.debug(f"⚠️ [MENTOR SYSTEM] Ментор не найден для {mentee_id}")
                    return None
                
                # Выбираем лучшего ментора (с наивысшим mentorship_score)
                best_mentor = mentors[0]['agent_id']
                logger.info(f"✅ [MENTOR SYSTEM] Найден ментор {best_mentor} для {mentee_id}")
                return best_mentor
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [MENTOR SYSTEM] Ошибка поиска ментора для {mentee_id}: {e}")
            return None
    
    async def assign_mentor(self, mentee_id: str, mentor_id: Optional[str] = None) -> bool:
        """
        Назначает ментора для агента.
        
        Args:
            mentee_id: ID подопечного
            mentor_id: ID ментора (если None - автоматический поиск)
        
        Returns:
            True если назначение успешно
        """
        try:
            # Если ментор не указан, ищем автоматически
            if not mentor_id:
                mentor_id = await self.find_mentor_for_agent(mentee_id)
                if not mentor_id:
                    logger.warning(f"⚠️ [MENTOR SYSTEM] Не удалось найти ментора для {mentee_id}")
                    return False
            
            # Проверяем, нет ли уже активного ментора
            existing = await self.get_active_mentor(mentee_id)
            if existing:
                logger.info(f"ℹ️ [MENTOR SYSTEM] У {mentee_id} уже есть ментор {existing.mentor_id}")
                return True
            
            # Создаем назначение
            assignment = MentorAssignment(
                mentor_id=mentor_id,
                mentee_id=mentee_id,
                assigned_at=datetime.now(timezone.utc),
                status='active',
                guidance_count=0
            )
            
            # Сохраняем в БД
            conn = await self._get_conn()
            if not conn:
                return False
            
            try:
                # Проверяем наличие таблицы mentor_assignments
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'mentor_assignments'
                    )
                """)
                
                if table_exists:
                    await conn.execute("""
                        INSERT INTO mentor_assignments (mentor_id, mentee_id, assigned_at, status, guidance_count)
                        VALUES ($1, $2, $3, $4, $5)
                        ON CONFLICT (mentor_id, mentee_id) DO UPDATE
                        SET status = EXCLUDED.status, assigned_at = EXCLUDED.assigned_at
                    """, mentor_id, mentee_id, assignment.assigned_at, assignment.status, assignment.guidance_count)
                
                # Обновляем кэш
                self._assignments_cache[f"{mentor_id}:{mentee_id}"] = assignment
                
                logger.info(f"✅ [MENTOR SYSTEM] Ментор {mentor_id} назначен для {mentee_id}")
                return True
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [MENTOR SYSTEM] Ошибка назначения ментора: {e}")
            return False
    
    async def get_active_mentor(self, mentee_id: str) -> Optional[MentorAssignment]:
        """
        Получает активного ментора для агента.
        
        Args:
            mentee_id: ID подопечного
        
        Returns:
            MentorAssignment или None
        """
        # Проверяем кэш
        for key, assignment in self._assignments_cache.items():
            if assignment.mentee_id == mentee_id and assignment.status == 'active':
                return assignment
        
        conn = await self._get_conn()
        if not conn:
            return None
        
        try:
            # Проверяем наличие таблицы
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'mentor_assignments'
                )
            """)
            
            if not table_exists:
                return None
            
            row = await conn.fetchrow("""
                SELECT mentor_id, mentee_id, assigned_at, status, guidance_count
                FROM mentor_assignments
                WHERE mentee_id = $1 AND status = 'active'
                ORDER BY assigned_at DESC
                LIMIT 1
            """, mentee_id)
            
            if row:
                assignment = MentorAssignment(
                    mentor_id=row['mentor_id'],
                    mentee_id=row['mentee_id'],
                    assigned_at=row['assigned_at'],
                    status=row['status'],
                    guidance_count=row['guidance_count']
                )
                self._assignments_cache[f"{assignment.mentor_id}:{assignment.mentee_id}"] = assignment
                return assignment
            
            return None
            
        except Exception as e:
            logger.debug(f"⚠️ [MENTOR SYSTEM] Ошибка получения ментора для {mentee_id}: {e}")
            return None
        finally:
            await conn.close()
    
    async def provide_guidance(self, mentor_id: str, mentee_id: str, guidance: str) -> bool:
        """
        Предоставляет рекомендацию от ментора подопечному.
        
        Args:
            mentor_id: ID ментора
            mentee_id: ID подопечного
            guidance: Текст рекомендации
        
        Returns:
            True если рекомендация успешно передана
        """
        try:
            # Проверяем, есть ли активное назначение
            assignment = await self.get_active_mentor(mentee_id)
            if not assignment or assignment.mentor_id != mentor_id:
                logger.warning(f"⚠️ [MENTOR SYSTEM] Нет активного назначения {mentor_id} → {mentee_id}")
                return False
            
            # Сохраняем рекомендацию в guidance system (если есть)
            # Интеграция с observability.guidance
            
            # Увеличиваем счетчик рекомендаций
            assignment.guidance_count += 1
            
            # Обновляем в БД
            conn = await self._get_conn()
            if not conn:
                return False
            
            try:
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'mentor_assignments'
                    )
                """)
                
                if table_exists:
                    await conn.execute("""
                        UPDATE mentor_assignments
                        SET guidance_count = guidance_count + 1
                        WHERE mentor_id = $1 AND mentee_id = $2
                    """, mentor_id, mentee_id)
                
                logger.info(f"✅ [MENTOR SYSTEM] Рекомендация передана от {mentor_id} к {mentee_id} (#{assignment.guidance_count})")
                return True
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [MENTOR SYSTEM] Ошибка передачи рекомендации: {e}")
            return False
    
    async def get_mentorship_statistics(self) -> Dict[str, Any]:
        """
        Получает статистику по менторству.
        
        Returns:
            Словарь со статистикой
        """
        try:
            conn = await self._get_conn()
            if not conn:
                return {}
            
            try:
                # Проверяем наличие таблиц
                assignments_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'mentor_assignments'
                    )
                """)
                
                if not assignments_exists:
                    return {
                        'total_assignments': 0,
                        'active_assignments': 0,
                        'total_guidance': 0,
                        'top_mentors': []
                    }
                
                # Получаем статистику
                stats = await conn.fetchrow("""
                    SELECT 
                        COUNT(*) as total,
                        COUNT(*) FILTER (WHERE status = 'active') as active,
                        SUM(guidance_count) as total_guidance
                    FROM mentor_assignments
                """)
                
                # Топ менторов
                top_mentors = await conn.fetch("""
                    SELECT mentor_id, COUNT(*) as mentees_count, SUM(guidance_count) as total_guidance
                    FROM mentor_assignments
                    WHERE status = 'active'
                    GROUP BY mentor_id
                    ORDER BY mentees_count DESC, total_guidance DESC
                    LIMIT 10
                """)
                
                return {
                    'total_assignments': stats['total'] or 0,
                    'active_assignments': stats['active'] or 0,
                    'total_guidance': stats['total_guidance'] or 0,
                    'top_mentors': [
                        {
                            'mentor_id': row['mentor_id'],
                            'mentees_count': row['mentees_count'],
                            'total_guidance': row['total_guidance']
                        }
                        for row in top_mentors
                    ]
                }
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [MENTOR SYSTEM] Ошибка получения статистики: {e}")
            return {}

# Singleton instance
_mentor_system_instance: Optional[MentorSystem] = None

def get_mentor_system(db_url: str = DB_URL) -> MentorSystem:
    """Получить singleton экземпляр MentorSystem"""
    global _mentor_system_instance
    if _mentor_system_instance is None:
        _mentor_system_instance = MentorSystem(db_url=db_url)
    return _mentor_system_instance


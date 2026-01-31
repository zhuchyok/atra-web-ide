"""
Team Formation System
Система командной работы для решения сложных задач
AGENT IMPROVEMENTS: Система командной работы
"""

import asyncio
import logging
import os
import json
import hashlib
from typing import Optional, Dict, List, Any, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
from enum import Enum
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

class TeamRole(Enum):
    """Роль в команде"""
    LEADER = "leader"        # Лидер команды (координация)
    EXECUTOR = "executor"    # Исполнитель (выполнение задач)
    REVIEWER = "reviewer"    # Ревьюер (проверка качества)
    SPECIALIST = "specialist" # Специалист (узкая экспертиза)

@dataclass
class TeamMember:
    """Участник команды"""
    agent_id: str
    role: TeamRole
    expertise: List[str]  # Области экспертизы
    assigned_at: datetime

@dataclass
class Team:
    """Команда агентов"""
    team_id: str
    task_id: str  # ID задачи, для которой создана команда
    members: List[TeamMember]
    leader_id: str
    status: str  # 'forming', 'active', 'completed', 'disbanded'
    created_at: datetime
    completed_at: Optional[datetime] = None

class TeamFormationSystem:
    """
    Система командной работы.
    
    Функционал:
    - Автоматическое формирование команд для сложных задач
    - Распределение ролей в команде (leader, executor, reviewer)
    - Координация работы команды через shared memory
    - Оценка эффективности команды
    - Оптимизация состава команд на основе истории
    """
    
    def __init__(self, db_url: str = DB_URL):
        """
        Args:
            db_url: URL базы данных
        """
        self.db_url = db_url
        self._active_teams: Dict[str, Team] = {}
        self._agent_expertise: Dict[str, List[str]] = {}  # agent_id -> [expertise areas]
        
    async def _get_conn(self):
        """Получить подключение к БД"""
        if not ASYNCPG_AVAILABLE:
            logger.error("asyncpg is not installed. Database connection unavailable.")
            return None
        try:
            conn = await asyncpg.connect(self.db_url)
            return conn
        except Exception as e:
            logger.error(f"❌ [TEAM FORMATION] Ошибка подключения к БД: {e}")
            return None
    
    async def get_agent_expertise(self, agent_id: str) -> List[str]:
        """
        Получает области экспертизы агента.
        
        Args:
            agent_id: ID агента
        
        Returns:
            Список областей экспертизы
        """
        # Проверяем кэш
        if agent_id in self._agent_expertise:
            return self._agent_expertise[agent_id]
        
        # Загружаем из БД (если есть таблица agent_expertise)
        conn = await self._get_conn()
        if not conn:
            return []
        
        try:
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'agent_expertise'
                )
            """)
            
            if table_exists:
                rows = await conn.fetch("""
                    SELECT expertise_area
                    FROM agent_expertise
                    WHERE agent_id = $1
                """, agent_id)
                expertise = [row['expertise_area'] for row in rows]
            else:
                # Дефолтные области на основе agent_id
                expertise = self._infer_expertise_from_agent_id(agent_id)
            
            self._agent_expertise[agent_id] = expertise
            return expertise
            
        finally:
            await conn.close()
    
    def _infer_expertise_from_agent_id(self, agent_id: str) -> List[str]:
        """Выводит экспертизу из ID агента (fallback)"""
        agent_lower = agent_id.lower()
        expertise = []
        
        if 'ml' in agent_lower or 'model' in agent_lower:
            expertise.append('machine_learning')
        if 'risk' in agent_lower:
            expertise.append('risk_management')
        if 'execution' in agent_lower or 'trade' in agent_lower:
            expertise.append('trade_execution')
        if 'signal' in agent_lower:
            expertise.append('signal_generation')
        if 'monitor' in agent_lower:
            expertise.append('monitoring')
        
        if not expertise:
            expertise = ['general']  # Общая экспертиза
        
        return expertise
    
    async def form_team(
        self,
        task_id: str,
        task_type: str,
        required_expertise: List[str],
        team_size: int = 3
    ) -> Optional[Team]:
        """
        Формирует команду для задачи.
        
        Args:
            task_id: ID задачи
            task_type: Тип задачи
            required_expertise: Требуемые области экспертизы
            team_size: Размер команды
        
        Returns:
            Team или None
        """
        try:
            # Генерируем team_id
            team_key = f"{task_id}:{task_type}:{datetime.now(timezone.utc).isoformat()}"
            team_id = hashlib.md5(team_key.encode()).hexdigest()[:16]
            
            # Находим агентов с подходящей экспертизой
            conn = await self._get_conn()
            if not conn:
                return None
            
            try:
                # Получаем список всех агентов (из agent_expertise или дефолтный список)
                # Для упрощения используем известные агенты
                available_agents = [
                    'auto_execution', 'risk_manager', 'signal_live',
                    'price_monitor', 'ml_predictor', 'correlation_manager'
                ]
                
                # Оцениваем соответствие агентов требуемой экспертизе
                agent_scores = []
                for agent_id in available_agents:
                    expertise = await self.get_agent_expertise(agent_id)
                    # Считаем пересечение требуемой и имеющейся экспертизы
                    match_count = len(set(required_expertise) & set(expertise))
                    score = match_count / len(required_expertise) if required_expertise else 0.5
                    agent_scores.append((agent_id, score, expertise))
                
                # Сортируем по score и выбираем лучших
                agent_scores.sort(key=lambda x: x[1], reverse=True)
                selected_agents = agent_scores[:team_size]
                
                if len(selected_agents) < 2:  # Минимум 2 агента для команды
                    logger.warning(f"⚠️ [TEAM FORMATION] Недостаточно агентов для команды (требуется {team_size}, найдено {len(selected_agents)})")
                    return None
                
                # Формируем команду с ролями
                members = []
                leader_id = selected_agents[0][0]  # Лучший агент = лидер
                
                for i, (agent_id, score, expertise) in enumerate(selected_agents):
                    if i == 0:
                        role = TeamRole.LEADER
                    elif i == len(selected_agents) - 1:
                        role = TeamRole.REVIEWER
                    else:
                        role = TeamRole.EXECUTOR
                    
                    member = TeamMember(
                        agent_id=agent_id,
                        role=role,
                        expertise=expertise,
                        assigned_at=datetime.now(timezone.utc)
                    )
                    members.append(member)
                
                team = Team(
                    team_id=team_id,
                    task_id=task_id,
                    members=members,
                    leader_id=leader_id,
                    status='active',
                    created_at=datetime.now(timezone.utc)
                )
                
                # Сохраняем в БД
                table_exists = await conn.fetchval("""
                    SELECT EXISTS (
                        SELECT 1 FROM information_schema.tables 
                        WHERE table_name = 'agent_teams'
                    )
                """)
                
                if table_exists:
                    await conn.execute("""
                        INSERT INTO agent_teams (team_id, task_id, leader_id, status, created_at, members)
                        VALUES ($1, $2, $3, $4, $5, $6)
                        ON CONFLICT (team_id) DO UPDATE
                        SET status = EXCLUDED.status
                    """, team_id, task_id, leader_id, team.status, team.created_at, json.dumps([asdict(m) for m in members]))
                
                # Обновляем кэш
                self._active_teams[team_id] = team
                
                logger.info(f"✅ [TEAM FORMATION] Сформирована команда {team_id} для задачи {task_id} ({len(members)} участников)")
                return team
                
            finally:
                await conn.close()
                
        except Exception as e:
            logger.error(f"❌ [TEAM FORMATION] Ошибка формирования команды: {e}")
            return None
    
    async def get_team_for_task(self, task_id: str) -> Optional[Team]:
        """
        Получает команду для задачи.
        
        Args:
            task_id: ID задачи
        
        Returns:
            Team или None
        """
        # Проверяем кэш
        for team in self._active_teams.values():
            if team.task_id == task_id and team.status == 'active':
                return team
        
        # Загружаем из БД
        conn = await self._get_conn()
        if not conn:
            return None
        
        try:
            table_exists = await conn.fetchval("""
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables 
                    WHERE table_name = 'agent_teams'
                )
            """)
            
            if not table_exists:
                return None
            
            row = await conn.fetchrow("""
                SELECT team_id, task_id, leader_id, status, created_at, members
                FROM agent_teams
                WHERE task_id = $1 AND status = 'active'
                ORDER BY created_at DESC
                LIMIT 1
            """, task_id)
            
            if row:
                members_data = json.loads(row['members']) if isinstance(row['members'], str) else row['members']
                members = [
                    TeamMember(
                        agent_id=m['agent_id'],
                        role=TeamRole(m['role']),
                        expertise=m['expertise'],
                        assigned_at=datetime.fromisoformat(m['assigned_at']) if isinstance(m['assigned_at'], str) else m['assigned_at']
                    )
                    for m in members_data
                ]
                
                team = Team(
                    team_id=row['team_id'],
                    task_id=row['task_id'],
                    members=members,
                    leader_id=row['leader_id'],
                    status=row['status'],
                    created_at=row['created_at']
                )
                
                self._active_teams[team.team_id] = team
                return team
            
            return None
            
        finally:
            await conn.close()
    
    async def disband_team(self, team_id: str) -> bool:
        """
        Распускает команду.
        
        Args:
            team_id: ID команды
        
        Returns:
            True если успешно
        """
        try:
            team = self._active_teams.get(team_id)
            if not team:
                return False
            
            team.status = 'disbanded'
            team.completed_at = datetime.now(timezone.utc)
            
            # Обновляем в БД
            conn = await self._get_conn()
            if conn:
                try:
                    table_exists = await conn.fetchval("""
                        SELECT EXISTS (
                            SELECT 1 FROM information_schema.tables 
                            WHERE table_name = 'agent_teams'
                        )
                    """)
                    
                    if table_exists:
                        await conn.execute("""
                            UPDATE agent_teams
                            SET status = $1, completed_at = $2
                            WHERE team_id = $3
                        """, team.status, team.completed_at, team_id)
                    
                    logger.info(f"✅ [TEAM FORMATION] Команда {team_id} распущена")
                    return True
                    
                finally:
                    await conn.close()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ [TEAM FORMATION] Ошибка роспуска команды: {e}")
            return False
    
    async def evaluate_team_performance(self, team_id: str) -> Dict[str, Any]:
        """
        Оценивает эффективность команды.
        
        Args:
            team_id: ID команды
        
        Returns:
            Словарь с метриками эффективности
        """
        try:
            team = self._active_teams.get(team_id)
            if not team:
                return {}
            
            # Здесь можно добавить реальные метрики:
            # - Время выполнения задачи
            # - Качество результата
            # - Количество итераций
            # - Удовлетворенность результатом
            
            return {
                'team_id': team_id,
                'task_id': team.task_id,
                'team_size': len(team.members),
                'roles': [m.role.value for m in team.members],
                'status': team.status,
                'duration_hours': (team.completed_at - team.created_at).total_seconds() / 3600 if team.completed_at else None
            }
            
        except Exception as e:
            logger.error(f"❌ [TEAM FORMATION] Ошибка оценки эффективности: {e}")
            return {}

# Singleton instance
_team_formation_instance: Optional[TeamFormationSystem] = None

def get_team_formation_system(db_url: str = DB_URL) -> TeamFormationSystem:
    """Получить singleton экземпляр TeamFormationSystem"""
    global _team_formation_instance
    if _team_formation_instance is None:
        _team_formation_instance = TeamFormationSystem(db_url=db_url)
    return _team_formation_instance


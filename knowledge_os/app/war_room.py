"""
Collaborative Debugging War Room (Tactical emergency response)
Реализация тактического уровня управления из Phase 5.

Функционал:
1. Автоматический созыв экспертов при обнаружении критических сбоев.
2. Координация действий в реальном времени.
3. Синтез тактического плана исправления.
"""
import asyncio
import logging
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

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
class WarRoomSession:
    session_id: str
    incident_title: str
    severity: str
    status: str = "active"
    experts: List[str] = field(default_factory=list)
    log: List[Dict] = field(default_factory=list)
    final_fix_plan: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

class WarRoomManager:
    """
    Менеджер тактических сессий (War Room).
    """
    
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url
        self.active_sessions: Dict[str, WarRoomSession] = {}

    async def open_war_room(self, incident_title: str, severity: str, description: str) -> str:
        """Открыть новую тактическую сессию"""
        session_id = f"war_{int(datetime.now().timestamp())}"
        
        # 1. Выбираем экспертов на основе инцидента
        experts = await self._select_experts_for_incident(incident_title, description)
        
        session = WarRoomSession(
            session_id=session_id,
            incident_title=incident_title,
            severity=severity,
            experts=[e['name'] for e in experts]
        )
        
        self.active_sessions[session_id] = session
        logger.warning(f"🚨 [WAR ROOM] Открыта сессия {session_id}: {incident_title} (Эксперты: {', '.join(session.experts)})")
        
        # 2. Запускаем "брейншторм" экспертов
        asyncio.create_task(self._conduct_emergency_brainstorm(session, description))
        
        # 3. Сохраняем в БД
        await self._save_session_to_db(session)
        
        return session_id

    async def _select_experts_for_incident(self, title: str, description: str) -> List[Dict]:
        """Выбор экспертов для тушения пожара"""
        from expert_council_discussion import ExpertCouncil
        council = ExpertCouncil(self.db_url)
        # Ищем SRE, Backend, Security в зависимости от слов в описании
        topic = f"{title} {description}"
        return await council.get_relevant_experts(topic, count=3)

    async def _conduct_emergency_brainstorm(self, session: WarRoomSession, description: str):
        """Процесс экстренного обсуждения проблемы"""
        from ai_core import run_smart_agent_async
        
        session.log.append({"role": "system", "content": f"Инцидент: {description}", "time": datetime.now().isoformat()})
        
        # Каждый эксперт дает свою оценку
        for expert_name in session.experts:
            prompt = f"""СРОЧНО: В системе авария! 
ИНЦИДЕНТ: {session.incident_title}
ОПИСАНИЕ: {description}

ТЫ: {expert_name}. Дай краткую оценку ситуации и предложи ПЕРВЫЙ ШАГ для исправления.
Ответь максимально технично и кратко."""
            
            response = await run_smart_agent_async(prompt, expert_name=expert_name, category="reasoning")
            if response:
                entry = {"role": expert_name, "content": response, "time": datetime.now().isoformat()}
                session.log.append(entry)
                await self._update_session_log_in_db(session.session_id, entry)

        # Виктория синтезирует финальный план
        synthesis_prompt = f"""Ты Виктория, Team Lead. Синтезируй предложения экспертов в единый ТАКТИЧЕСКИЙ ПЛАН ИСПРАВЛЕНИЯ.
Инцидент: {session.incident_title}
Обсуждение: {json.dumps(session.log, ensure_ascii=False)}

Выдай план по пунктам."""
        
        final_plan = await run_smart_agent_async(synthesis_prompt, expert_name="Виктория", category="reasoning")
        session.final_fix_plan = final_plan
        session.status = "resolved"
        
        await self._finalize_session_in_db(session)
        logger.info(f"✅ [WAR ROOM] Сессия {session.session_id} завершена. План готов.")

    async def _save_session_to_db(self, session: WarRoomSession):
        if not ASYNCPG_AVAILABLE: return
        conn = await asyncpg.connect(self.db_url)
        try:
            # Используем таблицу expert_discussions как базу для War Room
            await conn.execute("""
                INSERT INTO expert_discussions (topic, status, metadata)
                VALUES ($1, $2, $3::jsonb)
            """, session.incident_title, 'open', json.dumps({
                "session_id": session.session_id,
                "type": "war_room",
                "severity": session.severity,
                "experts": session.experts,
                "created_at": session.created_at.isoformat()
            }))
        finally:
            await conn.close()

    async def _update_session_log_in_db(self, session_id: str, log_entry: Dict):
        if not ASYNCPG_AVAILABLE: return
        conn = await asyncpg.connect(self.db_url)
        try:
            await conn.execute("""
                UPDATE expert_discussions 
                SET metadata = metadata || jsonb_build_object('log', COALESCE(metadata->'log', '[]'::jsonb) || $1::jsonb)
                WHERE metadata->>'session_id' = $2
            """, json.dumps(log_entry), session_id)
        finally:
            await conn.close()

    async def _finalize_session_in_db(self, session: WarRoomSession):
        if not ASYNCPG_AVAILABLE: return
        conn = await asyncpg.connect(self.db_url)
        try:
            await conn.execute("""
                UPDATE expert_discussions 
                SET status = 'closed', consensus_summary = $1,
                    metadata = metadata || jsonb_build_object('resolved_at', NOW()::text)
                WHERE metadata->>'session_id' = $2
            """, session.final_fix_plan, session.session_id)
            
            # Сохраняем как критическое знание
            await conn.execute("""
                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                VALUES ((SELECT id FROM domains WHERE name = 'System' LIMIT 1), $1, 1.0, $2, true)
            """, f"FIXED INCIDENT: {session.incident_title}\nPLAN: {session.final_fix_plan}", 
                 json.dumps({"type": "incident_fix", "session_id": session.session_id}))
        finally:
            await conn.close()

async def trigger_war_room_if_needed(error_msg: str, severity: str = "high"):
    """Глобальный триггер для открытия War Room из любой части системы"""
    manager = WarRoomManager()
    await manager.open_war_room(f"Emergency: {error_msg[:50]}", severity, error_msg)

if __name__ == "__main__":
    # Тестовый запуск
    logging.basicConfig(level=logging.INFO)
    asyncio.run(trigger_war_room_if_needed("Критическая ошибка пула соединений PostgreSQL", "high"))

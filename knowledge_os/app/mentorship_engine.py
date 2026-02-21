"""
[SINGULARITY 20.0] Mentorship Engine.
Victoria audits completed tasks and provides feedback to experts to improve collective intelligence.
"""

import asyncio
import os
import json
import logging
import asyncpg
from datetime import datetime
from typing import List, Dict, Any, Optional

import sys
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv('DATABASE_URL', 'postgresql://admin:secret@localhost:5432/knowledge_os')

class MentorshipEngine:
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

    async def run_audit_cycle(self, limit: int = 5):
        """
        Selects recently completed tasks and performs an audit.
        """
        logger.info(f"🎓 [MENTORSHIP] Starting audit cycle for {limit} tasks...")
        
        conn = await asyncpg.connect(self.db_url)
        try:
            # 1. Get recently completed tasks that haven't been audited yet
            # We look for tasks in the 'tasks' table or interaction_logs
            tasks = await conn.fetch("""
                SELECT id, title, description, metadata, updated_at
                FROM tasks
                WHERE status = 'completed' 
                  AND (metadata->>'audited_by_victoria' IS NULL OR metadata->>'audited_by_victoria' = 'false')
                ORDER BY updated_at DESC
                LIMIT $1
            """, limit)

            if not tasks:
                logger.info("No new completed tasks for audit.")
                return

            for task in tasks:
                await self.audit_task(conn, task)

        finally:
            await conn.close()

    async def audit_task(self, conn, task: asyncpg.Record):
        """
        Audits a single task using Victoria's high-level reasoning.
        """
        task_id = task['id']
        title = task['title']
        description = task['description']
        metadata = json.loads(task['metadata']) if task['metadata'] else {}
        
        # Identify the expert who performed the task
        expert_name = metadata.get('assignee_hint', 'Unknown Expert')
        
        logger.info(f"🔍 [AUDIT] Reviewing task: {title} (Expert: {expert_name})")

        # 2. Prepare the audit prompt
        audit_prompt = f"""
        ТЫ - ВИКТОРИЯ, ВЕРХОВНЫЙ МЕНТОР КОРПОРАЦИИ (LEVEL 20 WISDOM).
        ТВОЯ ЗАДАЧА: Провести аудит выполненной задачи и дать конструктивный фидбек эксперту.

        ЭКСПЕРТ: {expert_name}
        ЗАДАЧА: {title}
        ОПИСАНИЕ: {description}
        РЕЗУЛЬТАТ (МЕТАДАННЫЕ): {json.dumps(metadata, indent=2, ensure_ascii=False)}

        ПЛАН АУДИТА:
        1. Оцени качество выполнения (0-10).
        2. Выяви, что можно было сделать лучше (архитектура, безопасность, производительность).
        3. Сформулируй ОДИН конкретный совет (Mentorship Note) для этого эксперта на будущее.

        ФОРМАТ ОТВЕТА (JSON):
        {{
            "score": 8,
            "critique": "...",
            "mentorship_note": "В следующий раз при работе с БД всегда проверяй наличие индексов в миграции."
        }}
        ВЕРНИ ТОЛЬКО ЧИСТЫЙ JSON.
        """

        # 3. Call Victoria (using local model or cloud fallback)
        from ai_core import run_smart_agent_async
        
        audit_json_str = await run_smart_agent_async(audit_prompt, expert_name="Виктория", category="reasoning")

        if not audit_json_str:
            logger.error(f"Failed to get audit response for task {task_id}")
            return

        try:
            # Clean JSON string if needed
            if "```json" in audit_json_str:
                audit_json_str = audit_json_str.split("```json")[1].split("```")[0].strip()
            elif "```" in audit_json_str:
                audit_json_str = audit_json_str.split("```")[1].split("```")[0].strip()
            
            audit_data = json.loads(audit_json_str)
            
            # 4. Save mentorship note to knowledge base
            note = audit_data.get('mentorship_note')
            score = audit_data.get('score', 0)
            
            if note:
                # Store as a knowledge node with type 'mentorship_note'
                domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = 'Mentorship' LIMIT 1")
                if not domain_id:
                    domain_id = await conn.fetchval("INSERT INTO domains (name) VALUES ('Mentorship') RETURNING id")
                
                content_kn = f"🎓 MENTORSHIP NOTE for {expert_name}: {note}"
                meta_kn = json.dumps({
                    "type": "mentorship_note",
                    "target_expert": expert_name,
                    "task_id": str(task_id),
                    "score": score,
                    "critique": audit_data.get('critique')
                })
                
                await conn.execute("""
                    INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                    VALUES ($1, $2, $3, $4, true)
                """, domain_id, content_kn, score / 10.0, meta_kn)
                
                # 5. Mark task as audited
                metadata['audited_by_victoria'] = 'true'
                metadata['audit_score'] = score
                await conn.execute("""
                    UPDATE tasks SET metadata = $1 WHERE id = $2
                """, json.dumps(metadata), task_id)
                
                logger.info(f"✅ [AUDIT COMPLETE] Task {task_id} scored {score}/10. Mentorship note stored.")

        except Exception as e:
            logger.error(f"Error parsing audit JSON for task {task_id}: {e}")

async def run_mentorship_cycle(limit: int = 5):
    engine = MentorshipEngine()
    await engine.run_audit_cycle(limit=limit)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Mentorship Engine Audit Cycle')
    parser.add_argument('--limit', type=int, default=5, help='Number of tasks to audit')
    args = parser.parse_args()
    
    asyncio.run(run_mentorship_cycle(limit=args.limit))

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone

# Добавляем пути для импорта
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "knowledge_os/app")))

try:
    import asyncpg
    from ai_core import run_smart_agent_async
except ImportError:
    asyncpg = None
    run_smart_agent_async = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("RedTeamAuditor")

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")

class RedTeamAuditor:
    """
    [SINGULARITY 26.3] Autonomous Red-Team Auditor.
    Constantly audits knowledge nodes and recent tasks for logic breaches.
    """
    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

    async def run_audit_cycle(self):
        """Один цикл аудита"""
        logger.info("🛡️ [RED TEAM] Starting logic audit cycle...")
        if not asyncpg: return

        conn = await asyncpg.connect(self.db_url)
        try:
            # 1. Берем случайные узлы знаний для проверки
            nodes = await conn.fetch("""
                SELECT id, content, metadata 
                FROM knowledge_nodes 
                WHERE is_verified = TRUE 
                ORDER BY RANDOM() LIMIT 3
            """)

            for node in nodes:
                await self._audit_node(conn, node)

            # 2. Проверяем последние выполненные задачи
            tasks = await conn.fetch("""
                SELECT id, title, result 
                FROM tasks 
                WHERE status = 'completed' 
                ORDER BY completed_at DESC LIMIT 2
            """)

            for task in tasks:
                await self._audit_task(conn, task)

        finally:
            await conn.close()
        logger.info("✅ [RED TEAM] Audit cycle completed.")

    async def _audit_node(self, conn, node):
        """Аудит конкретного узла знаний"""
        logger.info(f"🔍 Auditing node {node['id']}...")
        prompt = f"""ТЫ - Red Team Auditor. Найди логическую ошибку, противоречие или галлюцинацию в этом знании.
ЗНАНИЕ: {node['content']}

Примени метод '5 Почему'. Если все верно, верни 'OK'. 
Если нашел проблему, верни JSON: {{"problem": "описание", "severity": "high/medium"}}"""
        
        res = await run_smart_agent_async(prompt, expert_name="Red Team Critic", category="reasoning")
        if res and isinstance(res, str) and "problem" in res.lower():
            await self._report_breach(conn, f"Knowledge Node {node['id']}", res)

    async def _audit_task(self, conn, task):
        """Аудит результата задачи"""
        logger.info(f"🔍 Auditing task {task['id']} ({task['title']})...")
        prompt = f"""ТЫ - Red Team Auditor. Проверь результат задачи на логическую целостность.
ЗАДАЧА: {task['title']}
РЕЗУЛЬТАТ: {task['result']}

Найди скрытые риски или неверные выводы. Если все верно, верни 'OK'.
Если нашел проблему, верни JSON: {{"problem": "описание", "severity": "high/medium"}}"""

        res = await run_smart_agent_async(prompt, expert_name="Red Team Critic", category="reasoning")
        if res and isinstance(res, str) and "problem" in res.lower():
            await self._report_breach(conn, f"Task {task['id']}", res)

    async def _report_breach(self, conn, source, report):
        """Зарегистрировать нарушение логики"""
        logger.warning(f"🚨 [LOGIC BREACH] Found in {source}: {report[:200]}...")
        
        # Создаем задачу на исправление
        await conn.execute("""
            INSERT INTO tasks (title, description, status, priority, metadata)
            VALUES ($1, $2, 'pending', 'high', $3)
        """, f"🚨 LOGIC BREACH: {source}", f"Red Team Auditor found a problem: {report}", 
        json.dumps({"source": "red_team_auditor", "origin": source}))

if __name__ == "__main__":
    auditor = RedTeamAuditor()
    asyncio.run(auditor.run_audit_cycle())

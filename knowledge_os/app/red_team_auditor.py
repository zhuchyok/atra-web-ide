import asyncio
import json
import logging
import os
import re
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

# ---------------------------------------------------------------------------
# Rule-based детекторы — работают БЕЗ LLM (быстро, надёжно)
# ---------------------------------------------------------------------------
_PLACEHOLDER_PATTERNS = re.compile(
    r"(TODO|FIXME|PLACEHOLDER|заглушка|здесь будет|insert here|coming soon|not implemented)",
    re.IGNORECASE,
)
_EMPTY_RESULT_MIN_LEN = 30  # Результат короче 30 символов считается пустым
_DUPLICATE_WINDOW = 5  # Проверяем последние N задач на дубликаты


def _rule_based_audit_text(text: str, source: str) -> list[dict]:
    """
    Детерминированные проверки текста. Возвращает список найденных проблем.
    НЕ требует LLM.
    """
    problems = []

    if not text or len(text.strip()) < _EMPTY_RESULT_MIN_LEN:
        problems.append({
            "source": source,
            "problem": f"Пустой или слишком короткий результат ({len(text or '')} символов)",
            "severity": "high",
            "rule": "empty_result",
        })

    if text and _PLACEHOLDER_PATTERNS.search(text):
        match = _PLACEHOLDER_PATTERNS.search(text)
        problems.append({
            "source": source,
            "problem": f"Результат содержит заглушку/плейсхолдер: '{match.group()}'",
            "severity": "medium",
            "rule": "placeholder_detected",
        })

    return problems


class RedTeamAuditor:
    """
    [SINGULARITY 26.3] Autonomous Red-Team Auditor.
    Constantly audits knowledge nodes and recent tasks for logic breaches.

    [SINGULARITY 26.4] Двухуровневая архитектура:
    - Уровень 1: Rule-based (детерминированный, работает без LLM)
    - Уровень 2: LLM-based (глубокий анализ, при наличии Ollama)
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
                ORDER BY completed_at DESC LIMIT 5
            """)

            for task in tasks:
                await self._audit_task(conn, task)

            # 3. [SINGULARITY 26.4] Rule-based проверка дубликатов в очереди
            await self._check_queue_duplicates(conn)

        finally:
            await conn.close()
        logger.info("✅ [RED TEAM] Audit cycle completed.")

    async def _audit_node(self, conn, node):
        """Аудит конкретного узла знаний — сначала rule-based, потом LLM"""
        logger.info(f"🔍 Auditing node {node['id']}...")

        # Уровень 1: Rule-based
        problems = _rule_based_audit_text(
            node.get("content", ""), f"Knowledge Node {node['id']}"
        )
        for p in problems:
            await self._report_breach(conn, p["source"], json.dumps(p))
            return  # Уже нашли проблему — LLM не нужен

        # Уровень 2: LLM (если доступен)
        if run_smart_agent_async is None:
            return
        try:
            prompt = f"""ТЫ - Red Team Auditor. Найди логическую ошибку, противоречие или галлюцинацию в этом знании.
ЗНАНИЕ: {node['content']}

Примени метод '5 Почему'. Если все верно, верни 'OK'. 
Если нашел проблему, верни JSON: {{"problem": "описание", "severity": "high/medium"}}"""
            
            res = await run_smart_agent_async(prompt, expert_name="Red Team Critic", category="reasoning")
            if res and isinstance(res, str) and "problem" in res.lower():
                await self._report_breach(conn, f"Knowledge Node {node['id']}", res)
        except Exception as e:
            logger.debug(f"[RED TEAM] LLM audit skipped (non-critical): {e}")

    async def _audit_task(self, conn, task):
        """Аудит результата задачи — сначала rule-based, потом LLM"""
        logger.info(f"🔍 Auditing task {task['id']} ({task['title']})...")

        # Уровень 1: Rule-based
        problems = _rule_based_audit_text(
            task.get("result", ""), f"Task {task['id']}"
        )
        for p in problems:
            await self._report_breach(conn, p["source"], json.dumps(p))
            return

        # Уровень 2: LLM (если доступен)
        if run_smart_agent_async is None:
            return
        try:
            prompt = f"""ТЫ - Red Team Auditor. Проверь результат задачи на логическую целостность.
ЗАДАЧА: {task['title']}
РЕЗУЛЬТАТ: {task['result']}

Найди скрытые риски или неверные выводы. Если все верно, верни 'OK'.
Если нашел проблему, верни JSON: {{"problem": "описание", "severity": "high/medium"}}"""

            res = await run_smart_agent_async(prompt, expert_name="Red Team Critic", category="reasoning")
            if res and isinstance(res, str) and "problem" in res.lower():
                await self._report_breach(conn, f"Task {task['id']}", res)
        except Exception as e:
            logger.debug(f"[RED TEAM] LLM audit skipped (non-critical): {e}")

    async def _check_queue_duplicates(self, conn):
        """
        [SINGULARITY 26.4] Rule-based: проверить дубликаты в очереди задач.
        Дубликат = задачи с одинаковым title в статусе pending/in_progress.
        """
        dupes = await conn.fetch("""
            SELECT title, COUNT(*) as cnt
            FROM tasks
            WHERE status IN ('pending', 'in_progress')
            GROUP BY title
            HAVING COUNT(*) > 1
        """)
        for row in dupes:
            msg = f"Дубликат в очереди: '{row['title']}' встречается {row['cnt']} раз"
            logger.warning(f"🔁 [RED TEAM RULE] {msg}")
            await self._report_breach(conn, "Queue", json.dumps({
                "problem": msg,
                "severity": "medium",
                "rule": "duplicate_task",
            }))

    async def _report_breach(self, conn, source, report):
        """Зарегистрировать нарушение логики"""
        logger.warning(f"🚨 [LOGIC BREACH] Found in {source}: {report[:200]}...")
        
        # Создаем задачу на исправление (idempotent — ON CONFLICT DO NOTHING)
        await conn.execute("""
            INSERT INTO tasks (title, description, status, priority, metadata)
            VALUES ($1, $2, 'pending', 'high', $3)
            ON CONFLICT DO NOTHING
        """, f"🚨 LOGIC BREACH: {source[:80]}", f"Red Team Auditor found a problem: {report}",
        json.dumps({"source": "red_team_auditor", "origin": source}))

if __name__ == "__main__":
    auditor = RedTeamAuditor()
    asyncio.run(auditor.run_audit_cycle())

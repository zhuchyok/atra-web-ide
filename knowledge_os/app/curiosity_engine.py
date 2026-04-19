import asyncio
import getpass
import json
import logging
import os
import re
from datetime import datetime

import asyncpg
from ai_core import run_smart_agent_async

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

USER = getpass.getuser()
DB_URL = os.getenv("DATABASE_URL", f"postgresql://{USER}@localhost:6432/knowledge_os")
WORKSPACE_ROOT = "/Users/zhuchyok/Documents/GITHUB/atra"


class CuriosityEngine:
    """
    Phase B of Singularity v4.0.
    Scans the workspace for technical gaps and triggers research.
    """

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

    async def scan_for_gaps(self):
        """Analyze project files to find technologies/concepts not yet in knowledge base."""
        logger.info("🔍 Curiosity Engine: Scanning workspace for knowledge gaps...")

        found_keywords = set()

        # 1. Simple heuristic: look for imports and decorators in Python files
        for root, dirs, files in os.walk(WORKSPACE_ROOT):
            if "node_modules" in root or "venv" in root or "__pycache__" in root:
                continue
            for file in files:
                if file.endswith(".py"):
                    try:
                        with open(os.path.join(root, file), encoding="utf-8") as f:
                            content = f.read()
                            # 1. Extract imports
                            imports = re.findall(
                                r"^(?:from|import)\s+([\w\.]+)", content, re.MULTILINE
                            )
                            for imp in imports:
                                imp = imp.strip()
                                if imp and not imp.startswith("atra"):  # Ignore internal
                                    found_keywords.add(imp.split(".")[0])

                            # 2. Extract TODOs
                            todos = re.findall(r"#\s*TODO:\s*(.*)", content, re.IGNORECASE)
                            for todo in todos:
                                if len(todo) > 10:
                                    found_keywords.add(f"TASK:{todo[:30]}")
                    except Exception:
                        continue

        if not found_keywords:
            return "No gaps identified."

        conn = await asyncpg.connect(self.db_url)
        try:
            # 2. Cross-reference with knowledge_nodes
            gaps = []
            for kw in list(found_keywords)[:20]:  # Limit to avoid overload
                exists = await conn.fetchval(
                    """
                    SELECT EXISTS (
                        SELECT 1 FROM knowledge_nodes
                        WHERE content ILIKE $1 OR metadata->>'tags' LIKE $1
                    )
                """,
                    f"%{kw}%",
                )

                if not exists:
                    gaps.append(kw)

            if not gaps:
                logger.info("✅ All identified technologies are already in the Knowledge Graph.")
                return "Knowledge Graph is up to date."

            # 3. Create research tasks for the "Strategy" or "Technology" domain
            victoria_id = await conn.fetchval("SELECT id FROM experts WHERE name = 'Виктория'")
            tech_domain_id = await conn.fetchval(
                "SELECT id FROM domains WHERE name IN ('Technology', 'ML/Технологии') LIMIT 1"
            )

            for gap in gaps[:3]:  # Create max 3 tasks per run
                task_title = f"🔍 ИССЛЕДОВАНИЕ ТЕХНОЛОГИИ: {gap}"
                task_desc = f"Мы используем '{gap}' в проекте, но у нас нет глубоких знаний об этом в базе. Проведи исследование лучших практик, безопасности и оптимизации для {gap} в 2026 году."

                # Check if task already exists
                task_exists = await conn.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM tasks WHERE title = $1 AND status != 'completed')",
                    task_title,
                )
                if not task_exists:
                    await conn.execute(
                        """
                        INSERT INTO tasks (title, description, status, priority, creator_expert_id, domain_id, metadata)
                        VALUES ($1, $2, 'pending', 'medium', $3, $4, $5)
                        ON CONFLICT (title, COALESCE(project_context, 'default'))
                        WHERE status IN ('pending', 'in_progress') 
                        DO UPDATE SET updated_at = NOW()
                    """,
                        task_title,
                        task_desc,
                        victoria_id,
                        tech_domain_id,
                        json.dumps(
                            {"source": "curiosity_engine", "gap": gap, "is_autonomous": True}
                        ),
                    )
                    logger.info(f"🚀 Created research task for gap: {gap}")

            return f"Curiosity Engine identified {len(gaps)} gaps. Created research tasks."
        finally:
            await conn.close()


if __name__ == "__main__":
    engine = CuriosityEngine()
    asyncio.run(engine.scan_for_gaps())

import asyncio
import json
import logging
import os
from typing import Any, Dict, Optional

import asyncpg
from ai_core import run_smart_agent_async

logger = logging.getLogger("expert_synthesizer")

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")


class ExpertSynthesizer:
    """
    [SINGULARITY 24.0] Autonomous HR: Dynamic Expert Synthesis.
    Generates and registers new expert profiles based on task requirements.
    """

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

    async def find_or_synthesize_expert(self, task_description: str) -> Dict[str, Any]:
        """
        [FIX] Checks DB first for existing expert, then synthesizes only if needed.
        """
        try:
            conn = await asyncpg.connect(self.db_url)

            # 1. Ask Victoria to identify the required role/focus
            analysis_prompt = f"""### ЗАДАЧА: АНАЛИЗ ПОТРЕБНОСТИ В ЭКСПЕРТЕ
Ты — Виктория, Team Lead. Проанализируй задачу и определи, какой узкопрофильный эксперт нужен для её решения.

ЗАДАЧА:
{task_description}

ЗАДАНИЕ:
1. Определи нужную роль/фокус для решения.
2. Если нужен специфичный эксперт, предложи РОЛЬ и КЛЮЧЕВЫЕ СЛОВА для поиска.
3. Верни ответ в формате JSON:
{{
    "needs_new_expert": true/false,
    "suggested_name": "Имя (если новый)",
    "suggested_role": "Роль",
    "focus_area": "Ключевые слова для поиска"
}}
"""
            analysis = await run_smart_agent_async(
                analysis_prompt, expert_name="Виктория", category="reasoning"
            )

            # Parse JSON
            import re

            match = re.search(r"\{.*\}", analysis, re.DOTALL)
            if not match:
                logger.warning("⚠️ Failed to parse expert analysis JSON.")
                return {}

            data = json.loads(match.group())

            # [FIX] Check DB for existing expert BEFORE synthesizing
            focus_area = data.get("focus_area", "")
            if focus_area:
                existing = await conn.fetchrow(
                    """
                    SELECT id, name, role, department
                    FROM experts
                    WHERE role ILIKE $1 OR department ILIKE $1 OR name ILIKE $1
                    LIMIT 1
                """,
                    f"%{focus_area}%",
                )
                if existing:
                    logger.info(
                        f"✅ Found existing expert: {existing['name']} ({existing['role']})"
                    )
                    return {
                        "needs_new_expert": False,
                        "suggested_name": existing["name"],
                        "suggested_role": existing["role"],
                        "focus_area": focus_area,
                        "existing_expert_id": str(existing["id"]),
                        "existing": True,
                    }

            if not data.get("needs_new_expert"):
                logger.info("✅ Existing expert team is sufficient.")
                return data

            # 2. Synthesize new expert if needed
            new_expert = await self.synthesize_expert(
                data["suggested_name"], data["suggested_role"], data["focus_area"]
            )

            if new_expert:
                # 3. Register in DB
                await self.register_expert(new_expert)
                return new_expert

            return {}

        except Exception as e:
            logger.error(f"❌ Expert synthesis failed: {e}")
            return {}
        finally:
            if "conn" in locals():
                await conn.close()

    async def synthesize_expert(self, name: str, role: str, focus: str) -> Dict[str, Any]:
        """Generates a full system prompt for a new expert."""
        logger.info(f"🧬 Synthesizing new expert: {name} ({role})...")

        prompt = f"""### ЗАДАЧА: СОЗДАНИЕ ЦИФРОВОГО СЛЕПКА ЭКСПЕРТА
Ты — Виктория, Team Lead. Создай идеальный системный промпт для нового эксперта корпорации.

ИМЯ: {name}
РОЛЬ: {role}
ФОКУС: {focus}

ЗАДАНИЕ:
Напиши профессиональный, глубокий системный промпт, который сделает этого эксперта лучшим в своей области.
Используй стандарты Singularity 24.0.

ВЕРНИ ТОЛЬКО JSON:
{{
    "name": "{name}",
    "role": "{role}",
    "system_prompt": "Текст промпта...",
    "department": "Название отдела (например, Engineering, Research, Operations)",
    "metadata": {{"focus": "{focus}", "synthesized_at": "{datetime.now().isoformat()}"}}
}}
"""
        response = await run_smart_agent_async(prompt, expert_name="Виктория", category="reasoning")

        import re

        match = re.search(r"\{.*\}", response, re.DOTALL)
        if match:
            return json.loads(match.group())
        return {}

    async def register_expert(self, expert_data: Dict[str, Any]):
        """Inserts the new expert into the database."""
        try:
            conn = await asyncpg.connect(self.db_url)
            await conn.execute(
                """
                INSERT INTO experts (name, role, system_prompt, department, metadata, is_active)
                VALUES ($1, $2, $3, $4, $5::jsonb, true)
                ON CONFLICT (name) DO UPDATE
                SET system_prompt = EXCLUDED.system_prompt,
                    metadata = experts.metadata || EXCLUDED.metadata
            """,
                expert_data["name"],
                expert_data["role"],
                expert_data["system_prompt"],
                expert_data.get("department", "General"),
                json.dumps(expert_data.get("metadata", {})),
            )
            logger.info(f"✅ Expert {expert_data['name']} registered in DB.")
        except Exception as e:
            logger.error(f"❌ Failed to register expert: {e}")
        finally:
            await conn.close()


if __name__ == "__main__":

    async def test():
        synthesizer = ExpertSynthesizer()
        await synthesizer.find_or_synthesize_expert(
            "Нам нужно оптимизировать код на Rust для работы с Metal на Mac Studio M4 Max."
        )

    asyncio.run(test())

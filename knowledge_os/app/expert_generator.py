"""
[KNOWLEDGE OS] Expert Generator Engine.
Autonomous Recruitment: Designing and hiring AI experts for specific domains.
Part of the ATRA Singularity framework.
"""

import asyncio
import getpass
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone

# Third-party imports with fallback
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

# Local project imports with fallback
try:
    from ai_core import run_smart_agent_sync
except ImportError:
    def run_smart_agent_sync(prompt, **kwargs):  # pylint: disable=unused-argument
        """Fallback for run_smart_agent_sync."""
        return None

logger = logging.getLogger(__name__)

USER_NAME = getpass.getuser()
DEFAULT_DB_URL = os.getenv('DATABASE_URL') or 'postgresql://admin:secret@localhost:5432/knowledge_os'

DB_URL = os.getenv('DATABASE_URL', DEFAULT_DB_URL)


def run_cursor_agent(prompt: str):
    """Run cursor-agent CLI through smart core."""
    return run_smart_agent_sync(prompt, expert_name="HR-Director", category="recruitment")


async def recruit_expert(domain_name: str):
    """
    Autonomous Recruitment: Designing expert for domain.
    1. Analyzes best practices.
    2. Generates name, role, and system prompt.
    3. Persists expert to database.
    """
    if not ASYNCPG_AVAILABLE:
        logger.error("❌ asyncpg is not installed. Recruitment is disabled.")
        return

    logger.info("🕵️ Autonomous Recruitment: Designing expert for domain '%s'...", domain_name)
    conn = await asyncpg.connect(DB_URL)

    # 1. Анализируем лучшие мировые практики для этой роли
    recruitment_prompt = f"""
    Ты - Главный HR-Директор ИИ-Корпорации. 
    Нам нужен эксперт мирового уровня в области: {domain_name}.
    
    ЗАДАЧА:
    1. Придумай имя для эксперта (в стиле компании, например, Марк, София и т.д.).
    2. Определи его точную роль (например, Senior Legal Counsel).
    3. Разработай ГЛУБОКИЙ системный промпт, который сделает его гуру в этой области. 
       Промпт должен включать методологию работы, стиль общения и глубокие технические инструкции.
    
    ВЕРНИ ТОЛЬКО JSON:
    {{
        "name": "Имя",
        "role": "Роль",
        "system_prompt": "Текст промпта",
        "department": "{domain_name}"
    }}
    """

    output = run_cursor_agent(recruitment_prompt)

    if output:
        try:
            # More robust JSON extraction
            json_match = re.search(r'(\{[\s\S]*\})', output)
            if json_match:
                clean_json = json_match.group(1)
            else:
                clean_json = output.strip()
                if "```json" in clean_json:
                    clean_json = clean_json.split("```json")[1].split("```")[0]
                elif "```" in clean_json:
                    clean_json = clean_json.split("```")[1].split("```")[0]

            # Handle potential unescaped newlines in the system_prompt or other strings
            try:
                data = json.loads(clean_json)
            except json.JSONDecodeError:
                # Try to escape newlines manually in values
                fixed_json = re.sub(
                    r'(?<=: ")([\s\S]*?)(?=",)',
                    lambda m: m.group(1).replace('\n', '\\n'),
                    clean_json
                )
                data = json.loads(fixed_json)

            # 2. Нанимаем эксперта (вставляем в базу)
            expert_id = await conn.fetchval("""
                INSERT INTO experts (name, role, system_prompt, department, metadata)
                VALUES ($1, $2, $3, $4, $5)
                ON CONFLICT (name) DO NOTHING
                RETURNING id
            """, data['name'], data['role'], data['system_prompt'], data['department'],
            json.dumps({"hired_at": datetime.now(timezone.utc).isoformat(), "is_autonomous": True}))

            if expert_id:
                logger.info("✅ Hired new expert: %s as %s in %s",
                            data['name'], data['role'], data['department'])

                # Создаем приветственное знание
                domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = $1", domain_name)
                if not domain_id:
                    domain_id = await conn.fetchval(
                        "INSERT INTO domains (name) VALUES ($1) RETURNING id",
                        domain_name
                    )

                welcome_msg = (
                    f"👋 ПРИВЕТСТВИЕ: Я {data['name']}, ваш новый эксперт в области {domain_name}. "
                    "Моя цель - довести наши компетенции в этой сфере до абсолютного максимума."
                )
                await conn.execute("""
                    INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                    VALUES ($1, $2, 1.0, $3, TRUE)
                """, domain_id, welcome_msg,
                json.dumps({"type": "recruitment_event", "expert_name": data['name']}))
            else:
                logger.warning("⚠️ Expert %s already exists.", data['name'])

        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("❌ Error parsing recruitment output: %s", exc)

    await conn.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(recruit_expert(sys.argv[1]))
    else:
        print("Usage: python expert_generator.py <domain_name>")

"""
[KNOWLEDGE OS] Meta-Architect Engine.
Autonomous Meta-Architect Agent (Singularity v3.0).
Responsible for self-authoring, patching, and code-level optimization across the workspace.
"""

import asyncio
import getpass
import json
import logging
import os
import subprocess

# Third-party imports with fallback
try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False

# Local project imports with fallback
try:
    from ai_core import run_smart_agent_async
except ImportError:
    async def run_smart_agent_async(prompt, **kwargs):  # pylint: disable=unused-argument
        """Fallback for run_smart_agent_async."""
        return None

logger = logging.getLogger(__name__)

USER_NAME = getpass.getuser()
# Priority: 1. env var, 2. local user (Mac), 3. fallback to admin (Server)
if USER_NAME == 'zhuchyok':
    DEFAULT_DB_URL = f'postgresql://{USER_NAME}@localhost:5432/knowledge_os'
else:
    DEFAULT_DB_URL = 'postgresql://admin:secret@localhost:5432/knowledge_os'

DB_URL = os.getenv('DATABASE_URL', DEFAULT_DB_URL)
# GLOBAL VISION: Meta-Architect now scans the entire workspace
base_dir_path = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
WORKSPACE_ROOT = os.getenv('WORKSPACE_ROOT', base_dir_path)


class MetaArchitect:
    """
    Autonomous Meta-Architect Agent (Singularity v3.0).
    Responsible for self-authoring, patching, and code-level optimization across the workspace.
    """

    def __init__(self, db_url: str = DB_URL):
        self.db_url = db_url

    async def self_repair_cycle(self):
        """Analyze repair tasks and attempt to fix the code."""
        if not ASYNCPG_AVAILABLE:
            logger.error("❌ asyncpg is not installed. Repair cycle aborted.")
            return "Error: asyncpg missing"

        try:
            conn = await asyncpg.connect(self.db_url)
            # Find urgent repair tasks created by Phase 8
            tasks = await conn.fetch("""
                SELECT id, title, description, metadata
                FROM tasks
                WHERE status = 'pending' AND title LIKE '🚨 АВТО-РЕМОНТ%'
                ORDER BY created_at ASC
                LIMIT 1
            """)

            if not tasks:
                await conn.close()
                return "No repair tasks found."

            for task in tasks:
                logger.info("🏗️ Meta-Architect (Global) addressing task: %s", task['title'])

                # 1. Identify relevant files
                analysis_prompt = (
                    "ВЫ - ГЛОБАЛЬНЫЙ МЕТА-АРХИТЕКТОР. "
                    "ЗАДАЧА: Проанализируйте описание ошибки и определите ПОЛНЫЙ путь к файлу "
                    f"в директории {WORKSPACE_ROOT}.\n\n"
                    f"ОШИБКА: {task['description']}\n"
                    f"МЕТАДАННЫЕ: {task['metadata']}\n\n"
                    "ВЕРНИТЕ ТОЛЬКО АБСОЛЮТНЫЙ ПУТЬ К ФАЙЛУ."
                )
                file_path_rel = await run_smart_agent_async(
                    analysis_prompt,
                    expert_name="Виктория",
                    category="meta_architect_analysis"
                )
                full_path = file_path_rel.strip().strip('`').strip()

                if not os.path.exists(full_path):
                    logger.error("File not found: %s", full_path)
                    continue

                # 2. Read file content
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # 3. Generate patch
                patch_prompt = (
                    "ВЫ - ГЛОБАЛЬНЫЙ МЕТА-АРХИТЕКТОР. "
                    "ЦЕЛЬ: Исправьте ошибку в коде.\n\n"
                    f"ФАЙЛ: {full_path}\n"
                    "ТЕКУЩИЙ КОД:\n"
                    "```python\n"
                    f"{content}\n"
                    "```\n\n"
                    f"ОПИСАНИЕ ОШИБКИ: {task['description']}\n\n"
                    "ЗАДАЧА: Верните ПОЛНЫЙ исправленный код файла. "
                    "Не используйте комментарии '... more code ...'. Только валидный Python код."
                )
                new_code = await run_smart_agent_async(
                    patch_prompt,
                    expert_name="Виктория",
                    category="meta_architect_patching"
                )

                if "```python" in new_code:
                    new_code = new_code.split("```python")[1].split("```")[0].strip()
                elif "```" in new_code:
                    new_code = new_code.split("```")[1].split("```")[0].strip()

                if len(new_code) < 100:
                    logger.error("Generated code is too short, aborting.")
                    continue

                # 4. Verify (Simple syntax check)
                temp_file = full_path + ".tmp"
                with open(temp_file, 'w', encoding='utf-8') as f:
                    f.write(new_code)

                try:
                    subprocess.check_call(['python3', '-m', 'py_compile', temp_file])
                    # 5. Apply
                    os.replace(temp_file, full_path)
                    await conn.execute("""
                        UPDATE tasks SET status = 'completed', result = $2, updated_at = NOW()
                        WHERE id = $1
                    """, task['id'], f"Code patched in {full_path}")

                    # 6. Log knowledge
                    node_content = f"🔧 GLOBAL SELF-PATCH: Meta-Architect исправил баг в {full_path}"
                    node_meta = json.dumps({
                        "type": "self_patch",
                        "file": full_path,
                        "task_id": str(task['id'])
                    })
                    await conn.execute("""
                        INSERT INTO knowledge_nodes (domain_id, content, is_verified, confidence_score, metadata)
                        VALUES ((SELECT id FROM domains WHERE name = 'Strategy' LIMIT 1), $1, true, 1.0, $2)
                    """, node_content, node_meta)

                    logger.info("✅ Successfully patched %s", full_path)
                except Exception as exc:  # pylint: disable=broad-exception-caught
                    logger.error("Syntax check failed for %s: %s", file_path_rel, exc)
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                    await conn.execute("""
                        UPDATE tasks SET status = 'failed', result = $2, updated_at = NOW()
                        WHERE id = $1
                    """, task['id'], f"Syntax error in generated patch: {exc}")

            await conn.close()
            return "Repair cycle finished."
        except Exception as exc:  # pylint: disable=broad-exception-caught
            logger.error("Meta-Architect error: %s", exc)
            return f"Error: {exc}"


if __name__ == "__main__":
    architect_instance = MetaArchitect()
    asyncio.run(architect_instance.self_repair_cycle())

import asyncio
import json
import logging
import os

import asyncpg

# Setup logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("backfill_project_slugs")

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")


async def backfill():
    logger.info("🚀 Starting backfill of project_slugs...")
    pool = await asyncpg.create_pool(DATABASE_URL)

    async with pool.acquire() as conn:
        # 1. Get all projects and their workspace paths
        projects = await conn.fetch("SELECT slug, workspace_path FROM projects")

        for project in projects:
            slug = project["slug"]
            path = project["workspace_path"]
            logger.info(f"📁 Processing project: {slug} (Path: {path})")

            # Update nodes where file_path matches project workspace_path
            # We use metadata->>'file_path' for matching
            result = await conn.execute(
                """
                UPDATE knowledge_nodes
                SET metadata = metadata || jsonb_build_object('project_slug', $1::text)
                WHERE (metadata->>'project_slug' IS NULL OR metadata->>'project_slug' = '')
                AND metadata->>'file_path' LIKE $2 || '%'
                """,
                slug,
                path,
            )
            logger.info(f"  ✅ Updated nodes for {slug}: {result}")

        # 2. Special case for AI Research domains
        ai_research_patterns = [
            "openai-cookbook%",
            "langchain%",
            "autogen%",
            "DeepSeek%",
            "system_prompts_leaks%",
        ]
        for pattern in ai_research_patterns:
            result = await conn.execute(
                """
                UPDATE knowledge_nodes
                SET metadata = metadata || '{"project_slug": "ai-research"}'
                WHERE (metadata->>'project_slug' IS NULL OR metadata->>'project_slug' = '')
                AND metadata->>'file_path' LIKE $1
                """,
                pattern,
            )
            logger.info(f"  ✅ Updated AI Research nodes ({pattern}): {result}")

        # 3. Special case for knowledge_os and core files -> atra-web-ide
        result = await conn.execute(
            """
            UPDATE knowledge_nodes
            SET metadata = metadata || '{"project_slug": "atra-web-ide"}'
            WHERE (metadata->>'project_slug' IS NULL OR metadata->>'project_slug' = '')
            AND (
                metadata->>'file_path' LIKE 'knowledge_os/%'
                OR metadata->>'file_path' LIKE 'src/%'
                OR metadata->>'file_path' LIKE 'docs/%'
                OR metadata->>'file_path' LIKE 'backend/%'
                OR metadata->>'file_path' LIKE 'frontend/%'
                OR metadata->>'file_path' LIKE 'scripts/%'
            )
            """
        )
        logger.info(f"  ✅ Updated atra-web-ide nodes: {result}")

    await pool.close()
    logger.info("🏁 Backfill complete.")


if __name__ == "__main__":
    asyncio.run(backfill())

"""
Knowledge Applicator — применение изученных знаний к корпорации (Singularity 10.0)

Применяет:
1. Lessons learned → guidance (.cursorrules или правила)
2. Ретроспективы → knowledge_nodes (из interaction_logs с feedback)
3. Новые знания → эволюция промптов (топ-инсайты из knowledge_nodes)

Мировые практики: BCG 10/20/70, ExpeL Closed-Loop, Microsoft Multi-Agent Architecture
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

try:
    import asyncpg
    ASYNCPG_AVAILABLE = True
except ImportError:
    asyncpg = None
    ASYNCPG_AVAILABLE = False


DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CURSORRULES_PATHS = [
    _PROJECT_ROOT / ".cursorrules",
    _PROJECT_ROOT.parent / ".cursorrules",
]


async def _apply_lessons_to_guidance(conn: asyncpg.Connection) -> bool:
    """
    Lessons learned из adaptive_learning_logs → обновление guidance (.cursorrules).
    Топ-5 по impact_score добавляются в блок "Lessons Learned".
    """
    try:
        rows = await conn.fetch("""
            SELECT learned_insight, impact_score, learning_type
            FROM adaptive_learning_logs
            WHERE impact_score > 0.5
            ORDER BY impact_score DESC
            LIMIT 5
        """)
        if not rows:
            logger.debug("No high-impact lessons to apply")
            return False

        insights = [r["learned_insight"] for r in rows]
        block = "\n## Lessons Learned (auto-applied)\n\n" + "\n".join(f"- {i}" for i in insights)

        for path in _CURSORRULES_PATHS:
            if path.exists():
                content = path.read_text(encoding="utf-8", errors="replace")
                marker = "## Lessons Learned (auto-applied)"
                if marker in content:
                    start = content.find(marker)
                    end = content.find("\n## ", start + 5)
                    end = end if end > 0 else len(content)
                    new_content = content[:start] + block.rstrip() + "\n" + (content[end:] if end < len(content) else "")
                else:
                    new_content = content.rstrip() + "\n\n" + block + "\n"
                path.write_text(new_content, encoding="utf-8")
                logger.info("Updated guidance at %s with %d lessons", path, len(insights))
                return True
        return False
    except Exception as e:
        logger.warning("apply_lessons_to_guidance: %s", e)
        return False


async def _apply_retrospectives_to_knowledge(conn: asyncpg.Connection) -> bool:
    """
    Ретроспективы из interaction_logs (feedback_text при feedback_score) → knowledge_nodes.
    Получаем domain_id для "Feedback" или создаём, вставляем инсайты.
    """
    try:
        rows = await conn.fetch("""
            SELECT il.feedback_text, il.feedback_score, il.user_query, il.assistant_response
            FROM interaction_logs il
            WHERE il.feedback_text IS NOT NULL
              AND LENGTH(TRIM(il.feedback_text)) > 10
              AND il.created_at > NOW() - INTERVAL '7 days'
            ORDER BY il.created_at DESC
            LIMIT 10
        """)
        if not rows:
            return False

        domain_id = await conn.fetchval(
            "SELECT id FROM domains WHERE name ILIKE $1", "Feedback"
        )
        if not domain_id:
            await conn.execute(
                "INSERT INTO domains (name, description) VALUES ($1, $2) ON CONFLICT (name) DO NOTHING",
                "Feedback",
                "Lessons from user feedback",
            )
            domain_id = await conn.fetchval(
                "SELECT id FROM domains WHERE name ILIKE $1", "Feedback"
            )

        inserted = 0
        for r in rows:
            content = f"Feedback (score={r['feedback_score']}): {r['feedback_text']}"
            metadata = json.dumps({"source": "interaction_logs", "feedback_score": r["feedback_score"]})
            await conn.execute("""
                INSERT INTO knowledge_nodes (domain_id, content, metadata, confidence_score, source_ref)
                VALUES ($1, $2, $3::jsonb, 0.7, 'retrospective')
            """, domain_id, content[:5000], metadata)
            inserted += 1

        if inserted > 0:
            logger.info("Inserted %d retrospectives into knowledge_nodes", inserted)
            return True
        return False
    except Exception as e:
        logger.warning("apply_retrospectives_to_knowledge: %s", e)
        return False


async def _evolve_prompts_from_insights(conn: asyncpg.Connection) -> bool:
    """
    Топ-инсайты из knowledge_nodes → предложения по эволюции промптов.
    Создаёт задачи (tasks) для Prompt Engineer или пишет в staging.
    Реальное обновление промптов — через enhanced_expert_evolver или human review.
    """
    try:
        rows = await conn.fetch("""
            SELECT k.content, k.confidence_score, d.name as domain_name
            FROM knowledge_nodes k
            LEFT JOIN domains d ON k.domain_id = d.id
            WHERE k.is_verified = true
               OR k.confidence_score > 0.8
            ORDER BY k.confidence_score DESC, k.created_at DESC
            LIMIT 5
        """)
        if not rows:
            return False

        # Создаём задачу для Prompt Engineer на основе топ-инсайтов
        insight_summary = "\n".join(f"- [{r['domain_name']}] {r['content'][:200]}..." for r in rows)
        title = "Prompt evolution from top insights"
        description = f"Apply these verified insights to expert prompts:\n\n{insight_summary[:2000]}"

        metadata = json.dumps({"source": "knowledge_applicator", "insights_count": len(rows)})
        await conn.execute("""
            INSERT INTO tasks (title, description, status, priority, metadata)
            VALUES ($1, $2, 'pending', 'medium', $3::jsonb)
        """, title, description, metadata)

        logger.info("Created prompt evolution task with %d insights", len(rows))
        return True
    except Exception as e:
        logger.warning("evolve_prompts_from_insights: %s", e)
        return False


async def _apply_all_knowledge_async() -> Dict[str, bool]:
    if not ASYNCPG_AVAILABLE:
        logger.warning("asyncpg not available, skipping knowledge application")
        return {"guidance_updated": False, "knowledge_base_updated": False, "prompts_evolved": False}

    conn = await asyncpg.connect(DB_URL)
    try:
        guidance_updated = await _apply_lessons_to_guidance(conn)
        knowledge_base_updated = await _apply_retrospectives_to_knowledge(conn)
        prompts_evolved = await _evolve_prompts_from_insights(conn)
        return {
            "guidance_updated": guidance_updated,
            "knowledge_base_updated": knowledge_base_updated,
            "prompts_evolved": prompts_evolved,
        }
    finally:
        await conn.close()


def apply_all_knowledge() -> Dict[str, bool]:
    """
    Синхронная обёртка для применения всех знаний.
    Вызывается из scripts/apply_knowledge.py.
    """
    try:
        return asyncio.run(_apply_all_knowledge_async())
    except Exception as e:
        logger.error("apply_all_knowledge failed: %s", e, exc_info=True)
        return {"guidance_updated": False, "knowledge_base_updated": False, "prompts_evolved": False}


async def apply_all_knowledge_async() -> Dict[str, bool]:
    """
    Асинхронная версия для вызова из Nightly Learner.
    """
    try:
        return await _apply_all_knowledge_async()
    except Exception as e:
        logger.error("apply_all_knowledge_async failed: %s", e, exc_info=True)
        return {"guidance_updated": False, "knowledge_base_updated": False, "prompts_evolved": False}

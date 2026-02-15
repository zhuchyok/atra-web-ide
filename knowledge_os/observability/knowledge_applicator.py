"""
Knowledge Applicator — применение изученных знаний к корпорации (Singularity 10.0)

Применяет:
1. Lessons learned → guidance (.cursorrules или правила)
2. Ретроспективы → knowledge_nodes (из interaction_logs с feedback)
3. Новые знания → эволюция промптов (топ-инсайты из knowledge_nodes)
4. Lessons/инсайты с код-релевантностью → задачи «Внедрить в код» (ExpeL-style: insight → actionable task)

Мировые практики:
- ExpeL (AAAI 2024): Experience → Knowledge Extraction → Task Inference; у нас: lessons → code_improvement tasks → worker.
- BCG 10/20/70: 10% обучение, 20% обмен, 70% практика — знания в .cursorrules + задачи на внедрение в код.
- Closed-loop: ретроспективы в БД, уроки в правила, код-инсайты в задачи для воркера/агента.
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
        get_embedding_fn = None
        try:
            from semantic_cache import get_embedding as _ge
            get_embedding_fn = _ge
        except Exception:
            try:
                from app.semantic_cache import get_embedding as _ge
                get_embedding_fn = _ge
            except Exception:
                pass
        for r in rows:
            content = f"Feedback (score={r['feedback_score']}): {r['feedback_text']}"
            content_trim = content[:5000]
            metadata = json.dumps({"source": "interaction_logs", "feedback_score": r["feedback_score"]})
            embedding = None
            if get_embedding_fn:
                try:
                    embedding = await get_embedding_fn(content_trim[:8000])
                except Exception:
                    pass
            if embedding is not None:
                await conn.execute("""
                    INSERT INTO knowledge_nodes (domain_id, content, metadata, confidence_score, source_ref, embedding)
                    VALUES ($1, $2, $3::jsonb, 0.7, 'retrospective', $4::vector)
                """, domain_id, content_trim, metadata, str(embedding))
            else:
                await conn.execute("""
                    INSERT INTO knowledge_nodes (domain_id, content, metadata, confidence_score, source_ref)
                    VALUES ($1, $2, $3::jsonb, 0.7, 'retrospective')
                """, domain_id, content_trim, metadata)
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

        metadata = json.dumps({
            "source": "knowledge_applicator",
            "insights_count": len(rows),
            "assignee_hint": "Prompt Engineer",
        })
        await conn.execute("""
            INSERT INTO tasks (title, description, status, priority, metadata)
            VALUES ($1, $2, 'pending', 'medium', $3::jsonb)
        """, title, description, metadata)

        logger.info("Created prompt evolution task with %d insights", len(rows))
        return True
    except Exception as e:
        logger.warning("evolve_prompts_from_insights: %s", e)
        return False


# Ключевые слова для определения «код-релевантных» уроков (ExpeL: извлекаемые инсайты → actionable code tasks)
_CODE_RELEVANT_KEYWORDS = (
    "код", "code", "тест", "test", "api", "валидац", "validation", "ошибк", "error",
    "файл", "file", "модуль", "module", "функци", "function", "класс", "class",
    "база", "database", "запрос", "query", "безопасност", "security", "производительност",
    "async", "таймаут", "timeout", "retry", "повтор", "логирован", "log",
)


def _is_code_relevant(text: str) -> bool:
    """Проверка, относится ли урок/инсайт к коду или практике разработки."""
    if not text or len(text) < 15:
        return False
    lower = text.lower()
    return any(kw in lower for kw in _CODE_RELEVANT_KEYWORDS)


async def _create_code_improvement_tasks(conn: asyncpg.Connection) -> bool:
    """
    Создание задач «Внедрить в код» из уроков и верифицированных инсайтов (ExpeL-style closed loop).
    Высоко-импактные lessons и код-релевантные knowledge_nodes → tasks с assignee_hint Backend/QA/DevOps.
    """
    try:
        created = 0
        # 1) Lessons из adaptive_learning_logs (код-релевантные, высокий impact)
        rows = await conn.fetch("""
            SELECT learned_insight, impact_score, learning_type
            FROM adaptive_learning_logs
            WHERE impact_score > 0.5
            ORDER BY impact_score DESC
            LIMIT 10
        """)
        for r in rows:
            insight = (r["learned_insight"] or "").strip()
            if not _is_code_relevant(insight):
                continue
            # Не создаём дубликат по тому же уроку
            exists = await conn.fetchval("""
                SELECT 1 FROM tasks
                WHERE metadata->>'source' = 'knowledge_applicator_code_improvement'
                  AND description LIKE $1
                  AND status NOT IN ('completed', 'cancelled')
                  AND created_at > NOW() - INTERVAL '14 days'
                LIMIT 1
            """, insight[:80] + "%")
            if exists:
                continue
            domain_id = await conn.fetchval(
                "SELECT id FROM domains WHERE name IN ('Engineering', 'Backend', 'QA', 'DevOps') LIMIT 1"
            )
            if not domain_id:
                domain_id = await conn.fetchval("SELECT id FROM domains LIMIT 1")
            victoria_id = await conn.fetchval("SELECT id FROM experts WHERE name = 'Виктория' LIMIT 1")
            meta = json.dumps({
                "source": "knowledge_applicator_code_improvement",
                "assignee_hint": "Backend Developer",
                "lesson_impact": r["impact_score"],
                "learning_type": r.get("learning_type"),
            })
            await conn.execute("""
                INSERT INTO tasks (title, description, status, priority, domain_id, creator_expert_id, metadata)
                VALUES ($1, $2, 'pending', 'medium', $3, $4, $5::jsonb)
            """, "🔧 Внедрить в код: урок из обучения", insight[:3000], domain_id, victoria_id, meta)
            created += 1
            if created >= 3:
                break

        # 2) Верифицированные инсайты из knowledge_nodes (код-релевантные)
        if created < 3:
            kn_rows = await conn.fetch("""
                SELECT k.id, k.content, k.confidence_score, d.name as domain_name
                FROM knowledge_nodes k
                LEFT JOIN domains d ON k.domain_id = d.id
                WHERE (k.is_verified = true OR k.confidence_score > 0.85)
                  AND k.created_at > NOW() - INTERVAL '30 days'
                ORDER BY k.confidence_score DESC, k.created_at DESC
                LIMIT 15
            """)
            for r in kn_rows:
                content = (r["content"] or "").strip()
                if not _is_code_relevant(content) or len(content) < 20:
                    continue
                exists = await conn.fetchval("""
                    SELECT 1 FROM tasks
                    WHERE metadata->>'source' = 'knowledge_applicator_code_improvement'
                      AND description LIKE $1
                      AND status NOT IN ('completed', 'cancelled')
                      AND created_at > NOW() - INTERVAL '7 days'
                    LIMIT 1
                """, content[:100] + "%")
                if exists:
                    continue
                domain_id = await conn.fetchval(
                    "SELECT id FROM domains WHERE name = $1", r["domain_name"] or "Engineering"
                )
                if not domain_id:
                    domain_id = await conn.fetchval("SELECT id FROM domains LIMIT 1")
                victoria_id = await conn.fetchval("SELECT id FROM experts WHERE name = 'Виктория' LIMIT 1")
                meta = json.dumps({
                    "source": "knowledge_applicator_code_improvement",
                    "assignee_hint": "Backend Developer",
                    "knowledge_node_id": r["id"],
                })
                await conn.execute("""
                    INSERT INTO tasks (title, description, status, priority, domain_id, creator_expert_id, metadata)
                    VALUES ($1, $2, 'pending', 'medium', $3, $4, $5::jsonb)
                """, "🔧 Внедрить в код: инсайт из базы знаний", content[:3000], domain_id, victoria_id, meta)
                created += 1
                if created >= 5:
                    break

        if created > 0:
            logger.info("Created %d code improvement task(s) from lessons/insights", created)
            return True
        return False
    except Exception as e:
        logger.warning("create_code_improvement_tasks: %s", e)
        return False


async def _apply_all_knowledge_async() -> Dict[str, bool]:
    if not ASYNCPG_AVAILABLE:
        logger.warning("asyncpg not available, skipping knowledge application")
        return {"guidance_updated": False, "knowledge_base_updated": False, "prompts_evolved": False, "code_tasks_created": False}

    conn = await asyncpg.connect(DB_URL)
    try:
        guidance_updated = await _apply_lessons_to_guidance(conn)
        knowledge_base_updated = await _apply_retrospectives_to_knowledge(conn)
        prompts_evolved = await _evolve_prompts_from_insights(conn)
        code_tasks_created = await _create_code_improvement_tasks(conn)
        return {
            "guidance_updated": guidance_updated,
            "knowledge_base_updated": knowledge_base_updated,
            "prompts_evolved": prompts_evolved,
            "code_tasks_created": code_tasks_created,
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
        return {"guidance_updated": False, "knowledge_base_updated": False, "prompts_evolved": False, "code_tasks_created": False}


async def apply_all_knowledge_async() -> Dict[str, bool]:
    """
    Асинхронная версия для вызова из Nightly Learner.
    """
    try:
        return await _apply_all_knowledge_async()
    except Exception as e:
        logger.error("apply_all_knowledge_async failed: %s", e, exc_info=True)
        return {"guidance_updated": False, "knowledge_base_updated": False, "prompts_evolved": False, "code_tasks_created": False}

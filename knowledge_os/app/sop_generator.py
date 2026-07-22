"""
[SINGULARITY 20.0] SOP Generator.
Synthesizes Standard Operating Procedures from successful complex tasks.
"""

import asyncio
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
_DEFAULT_SOP_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "docs", "SOP")
)
SOP_DIR = os.getenv("SOP_DIR", _DEFAULT_SOP_DIR)
SOP_TIMEOUT_SEC = float(os.getenv("SOP_GENERATE_TIMEOUT_SEC", "90"))


def _metadata_as_dict(metadata: Any) -> Dict[str, Any]:
    if metadata is None:
        return {}
    if isinstance(metadata, dict):
        return dict(metadata)
    if isinstance(metadata, str):
        try:
            parsed = json.loads(metadata)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _fallback_sop(title: str, description: str, metadata: Dict[str, Any]) -> str:
    expert = (
        metadata.get("assignee_hint")
        or metadata.get("expert_name")
        or metadata.get("target_expert")
        or "исполнитель"
    )
    return f"""# SOP: {title or 'Процесс'}

## Trigger
Применять при задачах, похожих на «{(title or '')[:120]}».

## Step-by-step
1. Уточнить цель и критерии done у заказчика / Team Lead.
2. Проверить health зависимостей (DB, Redis, MLX/Ollama).
3. Выполнить работу ({expert}), фиксируя промежуточные evidence.
4. Записать `tasks.result` и ключевые артефакты в Knowledge Fabric.
5. Закрыть задачу только после smoke-check.

## Pitfalls
- Закрытие без измеримого result.
- Игнор health-check перед эскалацией.
- Отсутствие mentorship/audit после сложных задач.

## Tools
- Victoria `/run`, dashboard Wisdom tab, `knowledge_nodes`, Blackboard.

## Context
{(description or '')[:500]}
"""


class SOPGenerator:
    def __init__(self, db_url: str = DB_URL, sop_dir: str = SOP_DIR):
        self.db_url = db_url
        self.sop_dir = sop_dir
        if not os.path.exists(self.sop_dir):
            os.makedirs(self.sop_dir)

    async def run_sop_cycle(self, limit: int = 3):
        """
        Identifies high-quality successful tasks and generates SOPs.
        """
        logger.info("📜 [SOP] Starting SOP generation cycle...")

        conn = await asyncpg.connect(self.db_url)
        try:
            # 1. Find successful tasks with high complexity or specific metadata
            # We look for tasks that are completed and have a high audit score (if available)
            tasks = await conn.fetch(
                """
                SELECT id, title, description, metadata, updated_at
                FROM tasks
                WHERE status = 'completed'
                  AND (metadata->>'sop_generated' IS NULL OR metadata->>'sop_generated' = 'false')
                  AND (metadata->>'audit_score')::int >= 8
                ORDER BY updated_at DESC
                LIMIT $1
            """,
                limit,
            )

            if not tasks:
                logger.info("No suitable tasks for SOP generation.")
                return

            for task in tasks:
                try:
                    await self.generate_sop(conn, task)
                except Exception as exc:
                    logger.error("SOP failed for %s: %s", task["id"], exc)

        finally:
            await conn.close()

    async def _generate_sop_text(
        self, sop_prompt: str, title: str, description: str, metadata: Dict[str, Any]
    ) -> str:
        try:
            from dialogue_llm import generate_dialogue_text

            text = await asyncio.wait_for(
                generate_dialogue_text(
                    sop_prompt,
                    expert_name="Виктория",
                    model_hint=os.getenv("SOP_MODEL", "phi3.5:3.8b"),
                ),
                timeout=SOP_TIMEOUT_SEC,
            )
            if text and len(text.strip()) > 80:
                return text.strip()
        except Exception as exc:
            logger.warning("dialogue_llm SOP failed: %s", exc)

        try:
            from ai_core import run_smart_agent_async

            text = await asyncio.wait_for(
                run_smart_agent_async(
                    sop_prompt, expert_name="Виктория", category="reasoning"
                ),
                timeout=SOP_TIMEOUT_SEC,
            )
            if text and len(text.strip()) > 80:
                return text.strip()
        except Exception as exc:
            logger.warning("ai_core SOP failed/timeout: %s", exc)

        return _fallback_sop(title or "", description or "", metadata)

    async def generate_sop(self, conn, task: asyncpg.Record):
        """
        Generates a Standard Operating Procedure from a task.
        """
        task_id = task["id"]
        title = task["title"]
        description = task["description"]
        metadata = _metadata_as_dict(task["metadata"])

        logger.info(f"📝 [SOP] Generating SOP for: {title}")

        # 2. Prepare the SOP prompt
        sop_prompt = f"""
        ТЫ - ВИКТОРИЯ, ГЛАВНЫЙ АРХИТЕКТОР ПРОЦЕССОВ (LEVEL 20 WISDOM).
        ЗАДАЧА: Создать Standard Operating Procedure (SOP) на основе успешно выполненной сложной задачи.

        НАЗВАНИЕ ЗАДАЧИ: {title}
        ОПИСАНИЕ: {description}
        ДЕТАЛИ ВЫПОЛНЕНИЯ: {json.dumps(metadata, indent=2, ensure_ascii=False)[:2500]}

        SOP ДОЛЖЕН ВКЛЮЧАТЬ:
        1. Название процесса.
        2. Когда применять этот процесс (Trigger).
        3. Пошаговая инструкция (Step-by-step).
        4. Типичные ошибки и как их избежать (Pitfalls).
        5. Инструменты и команды.

        ФОРМАТ: Markdown.
        ВЕРНИ ТОЛЬКО ТЕКСТ SOP.
        """

        sop_content = await self._generate_sop_text(
            sop_prompt, title or "", description or "", metadata
        )

        if not sop_content:
            logger.error(f"Failed to generate SOP content for task {task_id}")
            return

        try:
            # 4. Save SOP to file
            filename = f"SOP_{datetime.now().strftime('%Y%m%d')}_{task_id}.md"
            filepath = os.path.join(self.sop_dir, filename)

            with open(filepath, "w", encoding="utf-8") as f:
                f.write(sop_content)

            # 5. Register in Knowledge Base
            domain_id = await conn.fetchval("SELECT id FROM domains WHERE name = 'SOP' LIMIT 1")
            if not domain_id:
                domain_id = await conn.fetchval(
                    "INSERT INTO domains (name) VALUES ('SOP') RETURNING id"
                )

            content_kn = (
                f"📜 NEW SOP: {title}\nFile: docs/SOP/{filename}\n\nSummary: {sop_content[:500]}..."
            )
            meta_kn = json.dumps(
                {
                    "type": "sop_document",
                    "task_id": str(task_id),
                    "file_path": f"docs/SOP/{filename}",
                }
            )

            await conn.execute(
                """
                INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, is_verified)
                VALUES ($1, $2, 1.0, $3::jsonb, true)
            """,
                domain_id,
                content_kn,
                meta_kn,
            )

            # 6. Mark task
            metadata["sop_generated"] = "true"
            await conn.execute(
                """
                UPDATE tasks SET metadata = $1::jsonb, updated_at = NOW() WHERE id = $2
            """,
                json.dumps(metadata),
                task_id,
            )

            logger.info(f"✅ [SOP COMPLETE] SOP saved to {filepath} and registered in KB.")

        except Exception as e:
            logger.error(f"Error saving SOP for task {task_id}: {e}")


async def run_sop_cycle(limit: int = 3):
    generator = SOPGenerator()
    await generator.run_sop_cycle(limit=limit)


if __name__ == "__main__":
    asyncio.run(run_sop_cycle())

# /Users/bikos/Documents/atra-web-ide/knowledge_os/app/distillation_engine.py
"""
[SINGULARITY 21.0] Knowledge Distillation Engine.
Compresses raw knowledge nodes into high-density "Wisdom Adapters" (LoRA-ready)
using Victoria-Wisdom-30b as the teacher model.
"""

import asyncio
import json
import logging
import os
from datetime import datetime

import asyncpg
from ai_core import run_smart_agent_async

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:6432/knowledge_os")
DISTILLATION_BATCH_SIZE = 10


class KnowledgeDistiller:
    def __init__(self):
        self.teacher_model = "victoria-wisdom-v3.5"

    async def get_relevant_examples(self, query: str, category: str = "coding") -> str:
        """
        [SINGULARITY 21.5] Получает релевантные примеры (few-shot) из дистиллированных знаний.
        """
        try:
            # [FIX] Используем внутренний импорт, чтобы избежать циклической зависимости
            import asyncpg

            conn = await asyncpg.connect(DB_URL)
            # Ищем дистиллированные знания по категории
            rows = await conn.fetch(
                """
                SELECT metadata->>'wisdom_summary' as summary,
                       metadata->>'instruction' as instruction
                FROM knowledge_nodes
                WHERE metadata->>'distilled' = 'true'
                AND (metadata->>'category' = $1 OR $1 = 'coding')
                ORDER BY confidence_score DESC
                LIMIT 3
            """,
                category,
            )
            await conn.close()

            if not rows:
                return ""

            examples = "### РЕЛЕВАНТНЫЕ ПРИМЕРЫ (FEW-SHOT):\n"
            for row in rows:
                if row["summary"] and row["instruction"]:
                    examples += f"- СУТЬ: {row['summary']}\n  ИНСТРУКЦИЯ: {row['instruction']}\n"
            return examples
        except Exception as e:
            logger.warning(f"⚠️ [DISTILLER] Ошибка получения примеров: {e}")
            return ""

    async def distill_knowledge_batch(self):
        """
        Selects raw knowledge and compresses it into structured wisdom.
        """
        logger.info("⚗️ [DISTILLATION] Starting batch distillation cycle...")

        try:
            conn = await asyncpg.connect(DB_URL)

            # 1. Get raw, verified, but not yet distilled nodes
            nodes = await conn.fetch(
                """
                SELECT id, content, domain_id, metadata
                FROM knowledge_nodes
                WHERE is_verified = TRUE
                AND (metadata->>'distilled' IS NULL OR metadata->>'distilled' = 'false')
                LIMIT $1
            """,
                DISTILLATION_BATCH_SIZE,
            )

            if not nodes:
                logger.info("😴 [DISTILLATION] No nodes to distill. All wisdom is compressed.")
                await conn.close()
                return

            for node in nodes:
                logger.info(f"🧪 [DISTILLATION] Distilling node: {node['id']}")

                # 2. Teacher (Victoria-Wisdom) compresses the knowledge
                prompt = f"""
                ТЫ - ВЕРХОВНЫЙ ДИСТИЛЛЯТОР ЗНАНИЙ.
                ЗАДАЧА: Сожми это знание в максимально плотный и полезный формат для обучения других ИИ.

                ИСХОДНОЕ ЗНАНИЕ:
                {node["content"]}

                ВЕРНИ JSON:
                {{
                    "wisdom_summary": "Суть знания в 1-2 предложениях",
                    "instruction": "Как это знание применить (команда)",
                    "category": "coding/strategy/architecture/security"
                }}
                ВЕРНИ ТОЛЬКО ЧИСТЫЙ JSON.
                """

                distilled_json = await run_smart_agent_async(
                    prompt, expert_name="Виктория", category="reasoning"
                )

                try:
                    # Clean and parse JSON
                    if "```json" in distilled_json:
                        distilled_json = distilled_json.split("```json")[1].split("```")[0].strip()
                    wisdom = json.loads(distilled_json)

                    # 3. Update node with distilled metadata
                    new_metadata = dict(node["metadata"] or {})
                    new_metadata.update(
                        {
                            "distilled": "true",
                            "distilled_at": datetime.now().isoformat(),
                            "wisdom_summary": wisdom.get("wisdom_summary"),
                            "distilled_by": self.teacher_model,
                        }
                    )

                    await conn.execute(
                        """
                        UPDATE knowledge_nodes
                        SET metadata = $1,
                            confidence_score = GREATEST(confidence_score, 0.95)
                        WHERE id = $2
                    """,
                        json.dumps(new_metadata),
                        node["id"],
                    )

                    logger.info(f"✅ [DISTILLATION] Node {node['id']} compressed successfully.")

                except Exception as parse_err:
                    logger.error(
                        f"❌ [DISTILLATION] Failed to parse wisdom for node {node['id']}: {parse_err}"
                    )

            await conn.close()

        except Exception as e:
            logger.error(f"❌ [DISTILLATION] Error in cycle: {e}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    distiller = KnowledgeDistiller()
    asyncio.run(distiller.distill_knowledge_batch())

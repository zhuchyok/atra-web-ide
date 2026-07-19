# knowledge_os/scripts/prepare_wisdom_dataset.py
"""
[SINGULARITY 20.0] Wisdom Dataset Synthesizer.
Converts Knowledge OS nodes into Instruction-Tuning format (JSONL) for Fine-tuning.
"""

import asyncio
import json
import logging
import os
from datetime import datetime

import asyncpg

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL", "postgresql://admin:secret@localhost:5432/knowledge_os")
OUTPUT_FILE = "wisdom_dataset.jsonl"


async def synthesize_dataset():
    logger.info("🚀 [SYNTHESIZER] Starting Wisdom Dataset synthesis...")

    try:
        conn = await asyncpg.connect(DB_URL)

        # 1. Выбираем лучшие узлы знаний
        # Приоритет: Evolution Logs, Board Directives, High Confidence nodes
        # [SINGULARITY 20.0] Специальный акцент на знаниях гигантов
        rows = await conn.fetch("""
            SELECT content, metadata, confidence_score
            FROM knowledge_nodes
            WHERE (
                metadata->>'type' IN ('evolution_log', 'board_directive', 'swarm_resolution', 'mentorship_note')
                OR domain_id IN (SELECT id FROM domains WHERE name IN ('AI Research', 'Strategy', 'Architecture'))
                OR confidence_score >= 0.85
            )
            AND length(content) > 50
            ORDER BY created_at DESC
        """)

        logger.info(f"📊 [SYNTHESIZER] Found {len(rows)} potential knowledge nodes.")

        dataset = []
        for row in rows:
            content = row["content"]
            meta = row["metadata"] or {}
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except:
                    meta = {}

            # Формируем инструкцию на основе типа метаданных
            node_type = meta.get("type", "general_knowledge")

            instruction = ""
            if (
                node_type == "evolution_log"
                or "гигант" in str(content).lower()
                or "google" in str(content).lower()
                or "openai" in str(content).lower()
            ):
                instruction = "Внедрите передовой архитектурный паттерн или фичу, основываясь на практиках AI-гигантов (Google, OpenAI, Meta, Anthropic)."
            elif node_type == "board_directive":
                instruction = "Выполните стратегическую директиву Совета Директоров корпорации."
            elif node_type == "mentorship_note":
                instruction = "Примените наставление по улучшению качества работы и стиля кодинга."
            else:
                instruction = "Используйте накопленные знания корпорации для решения технической или стратегической задачи."

            entry = {
                "text": f"### Инструкция: {instruction}\n\n### Контекст: {node_type}\n\n### Данные: {content[:500]}...\n\n### Ответ: {content}"
            }
            dataset.append(entry)

        # 2. Записываем в JSONL
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            for entry in dataset:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        logger.info(f"✅ [SYNTHESIZER] Dataset created: {OUTPUT_FILE} ({len(dataset)} examples)")
        await conn.close()
        return len(dataset)

    except Exception as e:
        logger.error(f"❌ [SYNTHESIZER] Error: {e}")
        return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(synthesize_dataset())

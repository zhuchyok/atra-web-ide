#!/usr/bin/env python3
"""
Скрипт для создания дебатов для существующих знаний с высоким confidence_score
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from evaluator import get_pool
from nightly_learner import run_expert_council


async def create_debates_for_existing():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Находим знания без council_review
        knowledges = await conn.fetch("""
            SELECT id, content, metadata->>'expert' as expert, confidence_score
            FROM knowledge_nodes
            WHERE confidence_score >= 0.9
            AND (metadata->>'council_review' IS NULL OR metadata->>'council_review' = 'null')
            AND created_at > NOW() - INTERVAL '7 days'
            ORDER BY created_at DESC
            LIMIT 10
        """)

        print(f"📊 Найдено знаний для создания дебатов: {len(knowledges)}")

        created = 0
        for kn in knowledges:
            if kn["expert"]:
                expert = await conn.fetchrow("SELECT id FROM experts WHERE name = $1", kn["expert"])
                if expert:
                    try:
                        await run_expert_council(conn, kn["id"], kn["content"][:300], expert["id"])
                        created += 1
                        print(f"✅ Дебат создан для знания {str(kn['id'])[:8]}...")
                    except Exception as e:
                        print(f"❌ Ошибка для {str(kn['id'])[:8]}...: {e}")

        print(f"\n✅ Создано дебатов: {created}")

        # Проверяем результат
        debates_count = await conn.fetchval("SELECT COUNT(*) FROM expert_discussions")
        print(f"📊 Всего дебатов в БД: {debates_count}")
    await pool.close()


if __name__ == "__main__":
    asyncio.run(create_debates_for_existing())

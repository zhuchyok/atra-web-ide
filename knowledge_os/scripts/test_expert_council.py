#!/usr/bin/env python3
"""Тестовый скрипт для создания дебатов"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from evaluator import get_pool
from nightly_learner import run_expert_council


async def create_debates_for_existing():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Находим знания из nightly_learner без council_review
        knowledges = await conn.fetch("""
            SELECT id, content, metadata->>'expert' as expert, confidence_score
            FROM knowledge_nodes
            WHERE metadata->>'cycle' = 'nightly_council'
            AND confidence_score >= 0.9
            AND (metadata->>'council_review' IS NULL OR metadata->>'council_review' = 'null')
            ORDER BY created_at DESC
            LIMIT 5
        """)

        print(f"📊 Найдено знаний для создания дебатов: {len(knowledges)}")

        created = 0
        for kn in knowledges:
            if kn["expert"]:
                expert = await conn.fetchrow("SELECT id FROM experts WHERE name = $1", kn["expert"])
                if expert:
                    try:
                        print(f"Создаю дебат для {str(kn['id'])[:8]}...")
                        await run_expert_council(conn, kn["id"], kn["content"][:300], expert["id"])
                        created += 1
                        print(f"✅ Дебат {created}/{len(knowledges)} создан")
                    except Exception as e:
                        print(f"❌ Ошибка: {e}")
                        import traceback

                        traceback.print_exc()

        # Проверяем результат
        debates_count = await conn.fetchval("SELECT COUNT(*) FROM expert_discussions")
        print(f"\n📊 Всего дебатов в БД: {debates_count}")

        if debates_count > 0:
            recent = await conn.fetch(
                "SELECT topic, consensus_summary FROM expert_discussions ORDER BY created_at DESC LIMIT 3"
            )
            print("\n💬 Последние дебаты:")
            for d in recent:
                print(f"   Тема: {d['topic'][:60]}")
                print(f"   Консенсус: {d['consensus_summary'][:100]}...")
                print()
    await pool.close()


if __name__ == "__main__":
    asyncio.run(create_debates_for_existing())

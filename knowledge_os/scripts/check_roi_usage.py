#!/usr/bin/env python3
"""
Проверка использования данных ROI
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from evaluator import get_pool


async def check_roi():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Топ по ликвидности
        top = await conn.fetch("""
            SELECT k.id, k.content, k.usage_count, k.confidence_score,
                   (k.usage_count * k.confidence_score) as liquidity_score,
                   k.metadata->>'expert' as expert, d.name as domain
            FROM knowledge_nodes k
            JOIN domains d ON k.domain_id = d.id
            WHERE k.usage_count > 0
            ORDER BY liquidity_score DESC
            LIMIT 5
        """)

        print("📊 Топ-5 узлов знаний по ликвидности:")
        for i, node in enumerate(top, 1):
            print(f"\n{i}. Score: {node['liquidity_score']:.2f}")
            print(f"   Использовано: {node['usage_count']} раз")
            print(f"   Confidence: {node['confidence_score']}")
            print(f"   Эксперт: {node['expert']}")
            print(f"   Домен: {node['domain']}")

        # Проверяем колонку liquidity_score
        has_col = await conn.fetchval("""
            SELECT EXISTS (
                SELECT 1 FROM information_schema.columns
                WHERE table_name = 'knowledge_nodes'
                AND column_name = 'liquidity_score'
            )
        """)
        print(f"\n📋 Колонка liquidity_score в БД: {has_col}")
    await pool.close()


if __name__ == "__main__":
    asyncio.run(check_roi())

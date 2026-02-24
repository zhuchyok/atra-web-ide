import asyncio
import os
import sys
from datetime import datetime, timezone

import asyncpg

# Используем get_pool из evaluator для консистентности
sys.path.insert(0, os.path.dirname(__file__))
from evaluator import get_pool


async def manage_pnl():
    print("💰 Calculating Knowledge P&L and ROI...")
    pool = await get_pool()

    async with pool.acquire() as conn:
        # 1. Рассчитываем ликвидность знаний (usage_count / days_since_creation)
        await conn.execute("""
            UPDATE knowledge_nodes
            SET liquidity_score = usage_count::double precision /
                GREATEST(EXTRACT(DAY FROM (NOW() - created_at)), 1)
        """)

        # 2. Начисляем "дивиденды" экспертам за их вклад
        experts = await conn.fetch("SELECT id, virtual_budget FROM experts")

        for expert in experts:
            # Считаем суммарную ликвидность знаний этого эксперта (из метаданных)
            total_liquidity = await conn.fetchval(
                """
                SELECT COALESCE(SUM(liquidity_score), 0)
                FROM knowledge_nodes
                WHERE metadata->>'expert_id' = $1
            """,
                str(expert["id"]),
            )

            # Обновляем бюджет и score
            new_budget = float(expert["virtual_budget"]) + (
                float(total_liquidity) * 10.0
            )  # 10 "кредитов" за единицу ликвидности
            new_score = 0.5 + (min(new_budget / 2000.0, 1.5))  # Ограничиваем score

            await conn.execute(
                """
                UPDATE experts
                SET virtual_budget = $1, performance_score = $2
                WHERE id = $3
            """,
                new_budget,
                new_score,
                expert["id"],
            )

            print(
                f"📊 Expert ID {expert['id']}: New Budget = {new_budget:.2f}, Score = {new_score:.2f}"
            )

    print("✅ P&L Management cycle completed.")

    # 3. Создание задач на основе высоколиквидных знаний
    try:
        from liquidity_task_generator import LiquidityTaskGenerator

        generator = LiquidityTaskGenerator()
        liquidity_stats = await generator.process_high_liquidity_knowledge()
        if liquidity_stats.get("tasks_created", 0) > 0:
            print(
                f"💡 Created {liquidity_stats['tasks_created']} tasks from high-liquidity knowledge"
            )
    except Exception as e:
        print(f"⚠️ Liquidity task generation error: {e}")

    try:
        await pool.close()
    except:
        pass


if __name__ == "__main__":
    asyncio.run(manage_pnl())

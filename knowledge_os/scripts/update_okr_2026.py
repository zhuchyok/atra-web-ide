#!/usr/bin/env python3
"""
Скрипт для обновления OKR на 2026-Q1
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "app"))

from evaluator import get_pool


async def update_or_create_okr_2026():
    pool = await get_pool()
    async with pool.acquire() as conn:
        # Проверяем, сколько OKR на 2026-Q1
        okrs_2026 = await conn.fetch("SELECT id, objective FROM okrs WHERE period = $1", "2026-Q1")

        if len(okrs_2026) < 2:
            print("📅 Создаю OKR на 2026-Q1...")

            # Создаем OKR 1
            okr1_id = await conn.fetchval(
                """
                INSERT INTO okrs (objective, period, created_at)
                VALUES ($1, $2, NOW())
                RETURNING id
            """,
                "Достичь технологического суверенитета и стабильности Knowledge OS",
                "2026-Q1",
            )

            await conn.execute(
                """
                INSERT INTO key_results (okr_id, description, target_value, unit)
                VALUES
                    ($1, 'Стабильность системы (Uptime)', 99.9, '%'),
                    ($2, 'Время восстановления (MTTR)', 5.0, 'min')
            """,
                okr1_id,
                okr1_id,
            )

            # Создаем OKR 2
            okr2_id = await conn.fetchval(
                """
                INSERT INTO okrs (objective, period, created_at)
                VALUES ($1, $2, NOW())
                RETURNING id
            """,
                "Максимизировать интеллектуальный капитал холдинга",
                "2026-Q1",
            )

            await conn.execute(
                """
                INSERT INTO key_results (okr_id, description, target_value, unit)
                VALUES
                    ($1, 'Объем базы знаний (узлов)', 5000, 'ед'),
                    ($2, 'Вовлеченность штата в обучение', 100, '%'),
                    ($3, 'Использование знаний (ROI)', 1000, 'раз')
            """,
                okr2_id,
                okr2_id,
                okr2_id,
            )

            print(f"✅ OKR 2026-Q1 создан (OKR 1: {okr1_id}, OKR 2: {okr2_id})")
        else:
            print(f"ℹ️ OKR 2026-Q1 уже существуют ({len(okrs_2026)} OKR)")
            for okr in okrs_2026:
                print(f"   - {okr['objective']}")

        # Показываем все OKR
        all_okrs = await conn.fetch(
            "SELECT id, objective, period, created_at FROM okrs ORDER BY created_at DESC"
        )
        print(f"\n📊 Всего OKR в системе: {len(all_okrs)}")
        for okr in all_okrs:
            print(f"   {okr['period']}: {okr['objective']}")
    await pool.close()


if __name__ == "__main__":
    asyncio.run(update_or_create_okr_2026())

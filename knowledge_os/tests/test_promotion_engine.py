import asyncio
import json
import os
import uuid
from datetime import datetime

import pytest

from knowledge_os.app.promotion_engine import check_and_promote_mutations


@pytest.mark.asyncio
async def test_promotion_engine_integration():
    """
    Integration test for PromotionEngine:
    1. Creates a test expert.
    2. Creates a mutation that meets thresholds (win_rate > 65%, tests >= 50).
    3. Creates another mutation that should be archived.
    4. Runs promotion engine.
    5. Verifies:
       - Expert's system_prompt is updated.
       - Expert's version is incremented.
       - Mutation status is 'promoted'.
       - Other mutation status is 'archived'.
       - A knowledge_node of type 'architectural_lesson' is created.
    """
    from knowledge_os.app.evaluator import get_pool

    pool = await get_pool()
    if not pool:
        pytest.skip("Database pool not available")

    async with pool.acquire() as conn:
        # Cleanup potential leftovers
        test_expert_name = "Test Evolution Expert"
        await conn.execute("DELETE FROM experts WHERE name = $1", test_expert_name)

        # 1. Setup: Create a test expert
        expert_id = await conn.fetchval(
            """
            INSERT INTO experts (name, role, system_prompt, version, department)
            VALUES ($1, 'Tester', 'Old Prompt', 1, 'QA')
            RETURNING id
        """,
            test_expert_name,
        )

        # 2. Setup: Create a mutation that meets thresholds (win_rate = 40/50 = 80% > 65%)
        mutation_id = uuid.uuid4()
        mutated_prompt = "New and Improved Prompt v2"
        await conn.execute(
            """
            INSERT INTO expert_mutations (id, expert_id, mutated_prompt, base_version, status, win_count, total_tests)
            VALUES ($1, $2, $3, 1, 'shadow', 40, 50)
        """,
            mutation_id,
            expert_id,
            mutated_prompt,
        )

        # 3. Setup: Create another mutation that should be archived
        other_mutation_id = uuid.uuid4()
        await conn.execute(
            """
            INSERT INTO expert_mutations (id, expert_id, mutated_prompt, base_version, status, win_count, total_tests)
            VALUES ($1, $2, 'Other Prompt', 1, 'shadow', 10, 50)
        """,
            other_mutation_id,
            expert_id,
        )

        # 4. Run promotion engine
        await check_and_promote_mutations(conn)

        # 5. Verify results
        # A. Expert updated
        expert = await conn.fetchrow(
            "SELECT system_prompt, version FROM experts WHERE id = $1", expert_id
        )
        assert expert["system_prompt"] == mutated_prompt
        assert expert["version"] >= 2

        # B. Mutation status promoted
        mutation = await conn.fetchrow(
            "SELECT status FROM expert_mutations WHERE id = $1", mutation_id
        )
        assert mutation["status"] == "promoted"

        # C. Other mutation archived
        other_mutation = await conn.fetchrow(
            "SELECT status FROM expert_mutations WHERE id = $1", other_mutation_id
        )
        assert other_mutation["status"] == "archived"

        # D. Knowledge node created as architectural_lesson
        kn = await conn.fetchrow(
            """
            SELECT content, metadata
            FROM knowledge_nodes
            WHERE metadata->>'mutation_id' = $1
        """,
            str(mutation_id),
        )

        assert kn is not None
        assert "Architectural Lesson" in kn["content"]
        meta = json.loads(kn["metadata"])
        assert meta["type"] == "architectural_lesson"
        assert meta["expert_id"] == str(expert_id)

        # Cleanup
        await conn.execute("DELETE FROM expert_mutations WHERE expert_id = $1", expert_id)
        await conn.execute("DELETE FROM experts WHERE id = $1", expert_id)
        await conn.execute(
            "DELETE FROM knowledge_nodes WHERE metadata->>'mutation_id' = $1", str(mutation_id)
        )

    await pool.close()

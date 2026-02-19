import pytest
import asyncio
import os
import json
import uuid
from knowledge_os.app.promotion_engine import check_and_promote_mutations, get_db_pool

@pytest.mark.asyncio
async def test_promotion_engine_logic():
    """
    Tests the promotion engine:
    1. Creates a mutation that meets thresholds.
    2. Runs promotion engine.
    3. Verifies expert's prompt is updated and mutation status is 'promoted'.
    """
    pool = await get_db_pool()
    if not pool:
        pytest.skip("Database not available")

    async with pool.acquire() as conn:
        # 1. Setup: Create a test expert
        expert_id = uuid.uuid4()
        expert_name = f"Test Expert {expert_id}"
        await conn.execute("""
            INSERT INTO experts (id, name, role, system_prompt, version)
            VALUES ($1, $2, 'Tester', 'Old Prompt', 1)
        """, expert_id, expert_name)

        # 2. Setup: Create a mutation that meets thresholds (win_rate = 40/50 = 80% > 65%)
        mutation_id = uuid.uuid4()
        mutated_prompt = "New and Improved Prompt"
        await conn.execute("""
            INSERT INTO expert_mutations (id, expert_id, mutated_prompt, base_version, status, win_count, total_tests)
            VALUES ($1, $2, $3, 1, 'shadow', 40, 50)
        """, mutation_id, expert_id, mutated_prompt)

        # 3. Setup: Create another mutation that should be archived
        other_mutation_id = uuid.uuid4()
        await conn.execute("""
            INSERT INTO expert_mutations (id, expert_id, mutated_prompt, base_version, status, win_count, total_tests)
            VALUES ($1, $2, 'Other Prompt', 1, 'shadow', 10, 50)
        """, other_mutation_id, expert_id)

        # 4. Run promotion engine
        await check_and_promote_mutations()

        # 5. Verify results
        # A. Expert updated
        expert = await conn.fetchrow("SELECT system_prompt, version FROM experts WHERE id = $1", expert_id)
        assert expert['system_prompt'] == mutated_prompt
        assert expert['version'] == 2

        # B. Mutation status promoted
        mutation = await conn.fetchrow("SELECT status FROM expert_mutations WHERE id = $1", mutation_id)
        assert mutation['status'] == 'promoted'

        # C. Other mutation archived
        other_mutation = await conn.fetchrow("SELECT status FROM expert_mutations WHERE id = $1", other_mutation_id)
        assert other_mutation['status'] == 'archived'

        # D. Knowledge node created
        kn = await conn.fetchrow("SELECT content FROM knowledge_nodes WHERE metadata->>'mutation_id' = $1", str(mutation_id))
        assert kn is not None
        assert "promoted" in kn['content']

        # Cleanup
        await conn.execute("DELETE FROM expert_mutations WHERE expert_id = $1", expert_id)
        await conn.execute("DELETE FROM experts WHERE id = $1", expert_id)
        await conn.execute("DELETE FROM knowledge_nodes WHERE metadata->>'mutation_id' = $1", str(mutation_id))

    await pool.close()

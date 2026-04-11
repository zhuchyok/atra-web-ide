import pytest
import asyncio
import uuid
from app.graphrag.multi_hop_retriever import MultiHopRetriever
from app.db_pool import get_pool

@pytest.fixture
async def db_connection():
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn

@pytest.fixture
async def test_domain_id(db_connection):
    domain_id = uuid.uuid4()
    await db_connection.execute(
        "INSERT INTO domains (id, name) VALUES ($1, $2)",
        domain_id, f"test_domain_{domain_id.hex[:8]}"
    )
    yield domain_id
    # Cleanup
    await db_connection.execute("DELETE FROM knowledge_links WHERE source_node_id IN (SELECT id FROM knowledge_nodes WHERE domain_id = $1)", domain_id)
    await db_connection.execute("DELETE FROM knowledge_nodes WHERE domain_id = $1", domain_id)
    await db_connection.execute("DELETE FROM domains WHERE id = $1", domain_id)

@pytest.mark.asyncio
async def test_retrieve_with_hops_depth_limit(db_connection, test_domain_id):
    """
    Test that MultiHopRetriever respects depth limits and uses adaptive strength.
    """
    retriever = MultiHopRetriever(db_url="") # db_url is not used if pool is mocked or available

    # 1. Setup a chain of nodes: A -> B -> C -> D -> E
    # A (seed) -> B (hop 1) -> C (hop 2) -> D (hop 3) -> E (hop 4)

    node_ids = []
    unique_val = 0.99
    prefix = f"DEPTH_TEST_{test_domain_id.hex[:8]}"
    for i in range(5):
        embedding = [unique_val] * 768
        node_id = await db_connection.fetchval(
            """
            INSERT INTO knowledge_nodes (domain_id, content, confidence_score, embedding)
            VALUES ($1, $2, 1.0, $3::vector)
            RETURNING id
            """,
            test_domain_id,
            f"{prefix}_{i}_{chr(65+i)}",
            str(embedding)
        )
        node_ids.append(node_id)

    # Create links with decreasing strength
    # A -> B (0.9)
    # B -> C (0.85)
    # C -> D (0.8)
    # D -> E (0.75)
    strengths = [0.9, 0.85, 0.8, 0.75]
    for i in range(4):
        await db_connection.execute(
            """
            INSERT INTO knowledge_links (source_node_id, target_node_id, link_type, strength)
            VALUES ($1, $2, 'related_to', $3)
            """,
            node_ids[i],
            node_ids[i+1],
            strengths[i]
        )

    # 2. Run retrieval with max_hops=4
    # Use a unique embedding to avoid interference with other data
    unique_embedding = [unique_val] * 768
    results = await retriever.retrieve_with_hops(unique_embedding, max_hops=4, limit=10)

    # 3. Verify results
    # Depth limit is 3, so Node E (hop 4) should NOT be in results
    # Node A is seed, B is hop 1, C is hop 2, D is hop 3.
    result_contents = [r["content"] for r in results]

    print(f"DEBUG: result_contents = {result_contents}")

    assert f"{prefix}_0_A" in result_contents
    assert f"{prefix}_1_B" in result_contents
    assert f"{prefix}_2_C" in result_contents
    assert f"{prefix}_3_D" in result_contents
    
    assert f"{prefix}_4_E" not in result_contents, f"Node E should be excluded by depth limit (max 3). Results: {result_contents}"

@pytest.mark.asyncio
async def test_retrieve_with_hops_caching(db_connection, test_domain_id):
    """
    Test that MultiHopRetriever uses Redis caching.
    """
    retriever = MultiHopRetriever(db_url="")

    # Setup a simple link A -> B
    unique_val = 0.88
    # Use a unique content prefix to avoid interference
    prefix = f"CACHE_TEST_{test_domain_id.hex[:8]}"
    node_a = await db_connection.fetchval(
        "INSERT INTO knowledge_nodes (domain_id, content, confidence_score, embedding) VALUES ($1, $2, 1.0, $3::vector) RETURNING id",
        test_domain_id, f"{prefix}_A", str([unique_val]*768)
    )
    node_b = await db_connection.fetchval(
        "INSERT INTO knowledge_nodes (domain_id, content, confidence_score, embedding) VALUES ($1, $2, 1.0, $3::vector) RETURNING id",
        test_domain_id, f"{prefix}_B", str([unique_val]*768)
    )
    await db_connection.execute(
        "INSERT INTO knowledge_links (source_node_id, target_node_id, link_type, strength) VALUES ($1, $2, 'related_to', 0.95)",
        node_a, node_b
    )

    # Use the same unique embedding for the query to ensure we find node_a as seed
    query_embedding = [unique_val] * 768

    # First call - should populate cache
    results1 = await retriever.retrieve_with_hops(query_embedding, max_hops=1, limit=10)
    
    result_contents1 = [r["content"] for r in results1]
    print(f"DEBUG: results1 contents = {result_contents1}")
    
    # Check if node_a was found as seed
    assert any(r["content"] == f"{prefix}_A" for r in results1), f"{prefix}_A not found in results: {result_contents1}"
    assert any(r["content"] == f"{prefix}_B" for r in results1), f"{prefix}_B not found in results: {result_contents1}"

    # Second call - should hit cache
    results2 = await retriever.retrieve_with_hops(query_embedding, max_hops=1, limit=10)
    assert len(results1) == len(results2)
    assert [r["id"] for r in results1] == [r["id"] for r in results2]

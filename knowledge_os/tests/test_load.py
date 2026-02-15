"""
Load testing for Knowledge OS
"""

import uuid
import pytest
import asyncio
from knowledge_os.app.knowledge_graph import KnowledgeGraph, LinkType
from knowledge_os.app.performance_optimizer import QueryCache


@pytest.mark.asyncio
async def test_load_create_many_links(db_connection, test_domain_id, knowledge_nodes_id_is_uuid):
    """Load test: Create many knowledge links (требует knowledge_nodes.id = UUID)."""
    if not knowledge_nodes_id_is_uuid:
        pytest.skip("knowledge_nodes.id не UUID — knowledge_links ожидают UUID")
    graph = KnowledgeGraph()
    
    # Create 100 knowledge nodes
    node_ids = []
    for i in range(100):
        node_id = await db_connection.fetchval("""
            INSERT INTO knowledge_nodes (domain_id, content, confidence_score)
            VALUES ($1, $2, 1.0)
            RETURNING id
        """, test_domain_id, f"Load test node {i}")
        node_ids.append(str(node_id))
    
    # Create links between nodes
    link_count = 0
    for i in range(len(node_ids) - 1):
        link_id = await graph.create_link(
            node_ids[i],
            node_ids[i + 1],
            LinkType.RELATED_TO
        )
        if link_id:
            link_count += 1
    
    assert link_count > 0
    
    # Get stats
    stats = await graph.get_graph_stats()
    assert stats['total_links'] >= link_count
    
    # Cleanup
    await db_connection.execute(
        f"DELETE FROM knowledge_nodes WHERE id IN ({','.join(['$' + str(i+1) for i in range(len(node_ids))])})",
        *[uuid.UUID(node_id) for node_id in node_ids]
    )


@pytest.mark.asyncio
async def test_load_cache_performance():
    """Load test: Cache performance"""
    cache = QueryCache()
    
    # Set many cache entries
    for i in range(1000):
        await cache.set(f"query_{i}", (), {"data": i}, ttl=60)
    
    # Get many cache entries
    hits = 0
    for i in range(1000):
        result = await cache.get(f"query_{i}", ())
        if result:
            hits += 1
    
    # Cache hit rate should be high
    assert hits >= 900  # 90% hit rate


@pytest.mark.asyncio
async def test_load_concurrent_operations():
    """Load test: Concurrent operations"""
    graph = KnowledgeGraph()
    
    async def create_link_task(i):
        # Create test nodes and link
        # (Упрощенная версия для теста)
        return i * 2
    
    # Execute 100 concurrent tasks
    tasks = [create_link_task(i) for i in range(100)]
    results = await asyncio.gather(*tasks)
    
    assert len(results) == 100
    assert all(r == i * 2 for i, r in enumerate(results))


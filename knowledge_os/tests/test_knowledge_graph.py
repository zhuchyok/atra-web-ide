"""
Unit tests for Knowledge Graph
"""

import pytest
import asyncio
from knowledge_os.app.knowledge_graph import KnowledgeGraph, LinkType


@pytest.mark.asyncio
async def test_create_link(db_connection, test_domain_id):
    """Test creating a knowledge link"""
    graph = KnowledgeGraph()
    
    # Create two test knowledge nodes
    node1_id = await db_connection.fetchval("""
        INSERT INTO knowledge_nodes (domain_id, content, confidence_score)
        VALUES ($1, 'Test knowledge 1', 1.0)
        RETURNING id
    """, test_domain_id)
    
    node2_id = await db_connection.fetchval("""
        INSERT INTO knowledge_nodes (domain_id, content, confidence_score)
        VALUES ($1, 'Test knowledge 2', 1.0)
        RETURNING id
    """, test_domain_id)
    
    # Create link
    link_id = await graph.create_link(
        str(node1_id),
        str(node2_id),
        LinkType.DEPENDS_ON,
        strength=0.9
    )
    
    assert link_id is not None
    
    # Verify link exists
    links = await graph.get_links(str(node1_id))
    assert len(links) > 0
    assert links[0]['target_node_id'] == str(node2_id)
    
    # Cleanup
    await db_connection.execute("DELETE FROM knowledge_nodes WHERE id IN ($1, $2)", node1_id, node2_id)


@pytest.mark.asyncio
async def test_get_related_nodes(db_connection, test_domain_id):
    """Test getting related nodes"""
    graph = KnowledgeGraph()
    
    # Create knowledge nodes with links
    node1_id = await db_connection.fetchval("""
        INSERT INTO knowledge_nodes (domain_id, content, confidence_score)
        VALUES ($1, 'Node 1', 1.0)
        RETURNING id
    """, test_domain_id)
    
    node2_id = await db_connection.fetchval("""
        INSERT INTO knowledge_nodes (domain_id, content, confidence_score)
        VALUES ($1, 'Node 2', 1.0)
        RETURNING id
    """, test_domain_id)
    
    # Create link
    await graph.create_link(
        str(node1_id),
        str(node2_id),
        LinkType.RELATED_TO
    )
    
    # Get related nodes
    related = await graph.get_related_nodes(str(node1_id), max_depth=1)
    
    assert len(related) > 0
    
    # Cleanup
    await db_connection.execute("DELETE FROM knowledge_nodes WHERE id IN ($1, $2)", node1_id, node2_id)


@pytest.mark.asyncio
async def test_get_graph_stats():
    """Test getting graph statistics"""
    graph = KnowledgeGraph()
    stats = await graph.get_graph_stats()
    
    assert 'total_links' in stats
    assert 'links_by_type' in stats
    assert 'nodes_with_links' in stats
    assert 'avg_strength' in stats


"""
E2E tests for critical scenarios
"""

import pytest
import asyncio
from knowledge_os.app.knowledge_graph import KnowledgeGraph, LinkType
from knowledge_os.app.security import SecurityManager, Role
from knowledge_os.app.contextual_learner import ContextualMemory, AdaptiveLearner


@pytest.mark.asyncio
async def test_e2e_knowledge_creation_and_linking(db_connection, test_domain_id, knowledge_nodes_id_is_uuid):
    """E2E test: Create knowledge and link it (требует knowledge_nodes.id = UUID)."""
    if not knowledge_nodes_id_is_uuid:
        pytest.skip("knowledge_nodes.id не UUID — knowledge_links ожидают UUID")
    graph = KnowledgeGraph()
    
    # 1. Create knowledge nodes
    node1_id = await db_connection.fetchval("""
        INSERT INTO knowledge_nodes (domain_id, content, confidence_score)
        VALUES ($1, 'E2E Test Knowledge 1', 1.0)
        RETURNING id
    """, test_domain_id)
    
    node2_id = await db_connection.fetchval("""
        INSERT INTO knowledge_nodes (domain_id, content, confidence_score)
        VALUES ($1, 'E2E Test Knowledge 2', 1.0)
        RETURNING id
    """, test_domain_id)
    
    # 2. Create link
    link_id = await graph.create_link(
        str(node1_id),
        str(node2_id),
        LinkType.ENHANCES
    )
    assert link_id is not None
    
    # 3. Get related nodes
    related = await graph.get_related_nodes(str(node1_id))
    assert len(related) > 0
    
    # 4. Get graph stats
    stats = await graph.get_graph_stats()
    assert stats['total_links'] > 0
    
    # Cleanup
    await db_connection.execute("DELETE FROM knowledge_nodes WHERE id IN ($1, $2)", node1_id, node2_id)


@pytest.mark.asyncio
async def test_e2e_user_authentication_flow(db_connection):
    """E2E test: User registration and authentication"""
    security = SecurityManager()
    
    # 1. Create user
    user_id = await security.create_user(
        username="e2e_test_user",
        password="testpassword123",
        role=Role.USER,
        email="e2e@test.com"
    )
    assert user_id is not None
    
    # 2. Authenticate user
    user = await security.authenticate_user("e2e_test_user", "testpassword123")
    assert user is not None
    assert user['username'] == "e2e_test_user"
    assert user['role'] == Role.USER
    
    # 3. Generate token
    token = security.generate_jwt_token(
        user['user_id'],
        user['username'],
        user['role']
    )
    assert token is not None
    
    # 4. Verify token
    payload = security.verify_jwt_token(token)
    assert payload is not None
    assert payload['user_id'] == user['user_id']
    
    # Cleanup
    await db_connection.execute("DELETE FROM users WHERE id = $1", user_id)


@pytest.mark.asyncio
async def test_e2e_contextual_learning_flow(db_connection, test_expert_id):
    """E2E test: Contextual learning workflow"""
    learner = AdaptiveLearner()
    memory = ContextualMemory()
    
    # 1. Create interaction log
    interaction_id = await db_connection.fetchval("""
        INSERT INTO interaction_logs (expert_id, user_query, assistant_response, feedback_score)
        VALUES ($1, 'Test query', 'Test response', 1)
        RETURNING id
    """, test_expert_id)
    
    # 2. Learn from feedback
    learning_id = await learner.learn_from_feedback(
        str(interaction_id),
        str(test_expert_id),
        1,  # Positive feedback
        "Great response!"
    )
    assert learning_id is not None
    
    # 3. Save pattern
    pattern_id = await memory.save_pattern(
        "query_pattern",
        "Test query",
        "Test response",
        0.9,
        domain="test"
    )
    assert pattern_id is not None
    
    # 4. Find similar patterns
    patterns = await memory.find_similar_patterns("Test query")
    assert isinstance(patterns, list)
    
    # Cleanup
    await db_connection.execute("DELETE FROM interaction_logs WHERE id = $1", interaction_id)


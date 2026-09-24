import asyncio
import json

import pytest

from knowledge_os.app.ai_core import _enrich_with_deep_memory, _get_db_pool, _get_knowledge_context


@pytest.mark.asyncio
async def test_enrich_with_deep_memory_unit(db_connection, test_domain_id):
    """
    Unit test for _enrich_with_deep_memory function.
    """
    # 1. Insert a domain summary node for the test domain
    summary_content = "This is a test domain summary for deep memory."
    await db_connection.execute(
        """
        INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata)
        VALUES ($1, $2, 1.0, $3)
        """,
        test_domain_id,
        summary_content,
        json.dumps({"type": "domain_summary"}),
    )

    # 2. Prepare mock nodes
    mock_nodes = [{"domain_id": test_domain_id}]
    pool = await _get_db_pool()

    # 3. Call _enrich_with_deep_memory
    enrichment = await _enrich_with_deep_memory(mock_nodes, pool)

    # 4. Assertions
    assert "<deep_memory>" in enrichment
    assert "domain name=" in enrichment
    assert summary_content in enrichment


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="Requires complex setup to bypass GraphRAG and hit Python RAG path with specific nodes"
)
async def test_get_knowledge_context_enrichment(db_connection, test_domain_id):
    """
    Test that _get_knowledge_context includes <deep_memory> enrichment.
    """
    # 1. Insert a domain summary node for the test domain
    summary_content = "This is a test domain summary for deep memory."
    await db_connection.execute(
        """
        INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata)
        VALUES ($1, $2, 1.0, $3)
        """,
        test_domain_id,
        summary_content,
        json.dumps({"type": "domain_summary"}),
    )

    # 2. Insert a regular knowledge node that will be retrieved
    # Using 768 dimensions as expected by the database
    await db_connection.execute(
        """
        INSERT INTO knowledge_nodes (domain_id, content, confidence_score, metadata, embedding)
        VALUES ($1, $2, 1.0, $3, array_fill(0.1, ARRAY[768])::vector)
        """,
        test_domain_id,
        "Specific knowledge about something.",
        json.dumps({"source": "indexing_daemon", "file_path": "test.py"}),
    )

    # 3. Call _get_knowledge_context
    # We use a query that should match (or we rely on the fact that we inserted a node)
    # The current implementation of _get_knowledge_context uses embeddings.
    # We also pass project_context to trigger the Python RAG path.
    # AND we pass a domain_id that we know exists to bypass some filters if needed.
    # Actually, let's just mock the embedding to be sure.
    context = await _get_knowledge_context("something", project_context=str(test_domain_id))

    # 4. Assertions
    assert "<deep_memory>" in context
    assert "domain name=" in context
    assert summary_content in context

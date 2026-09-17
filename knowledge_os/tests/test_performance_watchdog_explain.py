"""Watchdog must not EXPLAIN ANALYZE pg_stat_statements queries with $n."""

from app.performance_watchdog import _should_explain_analyze


def test_skip_parameterized_rag_query():
    q = (
        "SELECT id, ($3 - (embedding <=> $1::vector)) * "
        "CASE WHEN metadata->>$4 = $5 THEN $6 ELSE $7 END AS score "
        "FROM knowledge_nodes WHERE kind = $2"
    )
    assert _should_explain_analyze(q) is False


def test_allow_literal_select():
    assert _should_explain_analyze("SELECT id FROM knowledge_nodes WHERE id = 1") is True


def test_skip_non_select_and_explain():
    assert _should_explain_analyze("UPDATE tasks SET status = 'done'") is False
    assert _should_explain_analyze("EXPLAIN SELECT 1") is False
    assert _should_explain_analyze("") is False

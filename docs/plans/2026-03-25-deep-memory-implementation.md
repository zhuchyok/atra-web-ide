# Deep Memory Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement Hierarchical Context Injection (Deep Memory) to enrich RAG with domain-level summaries.

**Architecture:** Extend `_get_knowledge_context` in `ai_core.py` to recursively fetch domain summaries based on `domain_id` of retrieved nodes. Use a new SQL query to fetch these summaries efficiently.

**Tech Stack:** Python, asyncpg, PostgreSQL (pgvector).

---

### Task 1: Database Preparation (Domain Passports)

**Files:**
- Create: `knowledge_os/db/migrations/20260325_add_domain_passports.sql`
- Test: `docker exec knowledge_postgres psql -U admin -d knowledge_os -c "SELECT count(*) FROM knowledge_nodes WHERE metadata->>'type' = 'domain_summary';"`

**Step 1: Create migration file**
```sql
-- Insert initial domain summaries for core domains
INSERT INTO knowledge_nodes (domain_id, content, confidence_score, is_verified, metadata)
SELECT 
    id as domain_id,
    'Архитектурный паспорт домена ' || name || '. Стандарты: 12-Factor, SOLID, KISS. Текущий статус: 10/10.' as content,
    1.0 as confidence_score,
    true as is_verified,
    jsonb_build_object('type', 'domain_summary', 'source', 'system_init') as metadata
FROM domains
ON CONFLICT DO NOTHING;
```

**Step 2: Apply migration**
Run: `docker exec -i knowledge_postgres psql -U admin -d knowledge_os < knowledge_os/db/migrations/20260325_add_domain_passports.sql`
Expected: "INSERT 0 N"

**Step 3: Verify data**
Run: `docker exec knowledge_postgres psql -U admin -d knowledge_os -c "SELECT count(*) FROM knowledge_nodes WHERE metadata->>'type' = 'domain_summary';"`
Expected: > 0

**Step 4: Commit**
```bash
git add knowledge_os/db/migrations/20260325_add_domain_passports.sql
git commit -m "db: add initial domain passports for Deep Memory"
```

---

### Task 2: Core Logic (Hierarchical Enrichment)

**Files:**
- Modify: `knowledge_os/app/ai_core.py`
- Test: `knowledge_os/tests/test_deep_memory.py`

**Step 1: Write failing test for enrichment**
```python
import pytest
from app.ai_core import _get_knowledge_context

@pytest.mark.asyncio
async def test_deep_memory_enrichment():
    context = await _get_knowledge_context("database optimization")
    assert "<deep_memory>" in context
    assert "domain_summary" in context
```

**Step 2: Run test to verify it fails**
Run: `pytest knowledge_os/tests/test_deep_memory.py`
Expected: FAIL (AssertionError or context not containing tags)

**Step 3: Implement `_enrich_with_deep_memory` in `ai_core.py`**
```python
async def _enrich_with_deep_memory(nodes: list, pool) -> str:
    if not nodes: return ""
    domain_ids = list(set(n.get('domain_id') for n in nodes if n.get('domain_id')))
    if not domain_ids: return ""
    
    async with pool.acquire() as conn:
        summaries = await conn.fetch(
            "SELECT content, metadata->>'domain_name' as name FROM knowledge_nodes "
            "WHERE domain_id = ANY($1) AND metadata->>'type' = 'domain_summary'",
            domain_ids
        )
    
    enrichment = "<deep_memory>\n"
    for s in summaries:
        enrichment += f'  <domain name="{s["name"]}">{s["content"]}</domain>\n'
    enrichment += "</deep_memory>\n"
    return enrichment
```
*Note: Integrate this into `_get_knowledge_context` before returning the final string.*

**Step 4: Run test to verify it passes**
Run: `pytest knowledge_os/tests/test_deep_memory.py`
Expected: PASS

**Step 5: Commit**
```bash
git add knowledge_os/app/ai_core.py
git commit -m "feat: implement Hierarchical Context Injection in ai_core"
```

---

### Task 3: Evolution Integration (Auto-update)

**Files:**
- Modify: `knowledge_os/app/perpetual_evolution.py`

**Step 1: Update evolution prompt to include domain passports**
Modify the logic in `PerpetualEvolution` to periodically generate/update `domain_summary` nodes based on recent `knowledge_nodes` in that domain.

**Step 2: Verify evolution task creation**
Run: `docker logs knowledge_evolution`
Expected: Logs showing "Updating domain summary for..."

**Step 3: Commit**
```bash
git add knowledge_os/app/perpetual_evolution.py
git commit -m "feat: integrate domain passport updates into evolution loop"
```

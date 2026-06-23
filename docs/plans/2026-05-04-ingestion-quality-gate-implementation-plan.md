# Ingestion Quality Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce fail-closed quality validation at knowledge-node creation time so noisy candidates are rejected before entering `knowledge_nodes`.

**Architecture:** Add a hybrid ingestion gate (deterministic rules + LLM judge for borderline) as a reusable service, integrate it into both node-creation paths, and store rejected candidates in an audit table. Roll out with shadow mode first, then phased enforcement with rollback thresholds.

**Tech Stack:** Python (`asyncpg`, existing embedding stack), PostgreSQL (`jsonb` + new reject log table), existing `knowledge_os` services and tests.

---

## File Structure and Responsibilities

- Create: `knowledge_os/app/ingestion/quality_gate.py`  
  Core deterministic filter, borderline routing, decision model.
- Create: `knowledge_os/app/ingestion/judge.py`  
  Judge caller + strict contract validation (`decision/reason/quality_score`).
- Create: `knowledge_os/db/migrations/20260504_add_knowledge_reject_log.sql`  
  Audit table for rejected candidates.
- Modify: `knowledge_os/app/long_term_memory.py`  
  Apply quality gate before insert into `knowledge_nodes`.
- Modify: `knowledge_os/app/services/knowledge_service.py`  
  Apply quality gate before insight insert.
- Create: `knowledge_os/tests/test_ingestion_quality_gate.py`  
  Unit tests for accept/reject/borderline behavior.
- Create: `knowledge_os/tests/test_ingestion_quality_integration.py`  
  Integration tests for both insertion paths.

---

### Task 1: Add Reject Audit Storage

**Files:**

- Create: `knowledge_os/db/migrations/20260504_add_knowledge_reject_log.sql`
- Test: `knowledge_os/tests/test_ingestion_quality_integration.py`

- [ ] **Step 1: Write failing integration test for reject audit write**

```python
async def test_rejected_candidate_written_to_audit(pool):
    row = await pool.fetchrow(
        "SELECT id FROM knowledge_reject_log WHERE reject_reason = $1",
        "prompt_artifact",
    )
    assert row is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest knowledge_os/tests/test_ingestion_quality_integration.py::test_rejected_candidate_written_to_audit -v`  
Expected: FAIL with `relation "knowledge_reject_log" does not exist`

- [ ] **Step 3: Add migration with table and indexes**

```sql
CREATE TABLE IF NOT EXISTS knowledge_reject_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    candidate_hash TEXT NOT NULL,
    source_type TEXT NOT NULL,
    reject_reason TEXT NOT NULL,
    gate_stage TEXT NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_krlog_reason_created
    ON knowledge_reject_log (reject_reason, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_krlog_source_created
    ON knowledge_reject_log (source_type, created_at DESC);
```

- [ ] **Step 4: Apply migration and rerun failing test**

Run: `pytest knowledge_os/tests/test_ingestion_quality_integration.py::test_rejected_candidate_written_to_audit -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add knowledge_os/db/migrations/20260504_add_knowledge_reject_log.sql knowledge_os/tests/test_ingestion_quality_integration.py
git commit -m "feat: add reject audit table for ingestion quality gate"
```

---

### Task 2: Implement Deterministic Quality Rules

**Files:**

- Create: `knowledge_os/app/ingestion/quality_gate.py`
- Test: `knowledge_os/tests/test_ingestion_quality_gate.py`

- [ ] **Step 1: Write failing unit tests for rule outcomes**

```python
def test_reject_prompt_artifact():
    gate = IngestionQualityGate()
    result = gate.evaluate("Ты - ВЕРХОВНЫЙ ДИСТИЛЛЯТОР...", source_type="agent")
    assert result.decision == "reject"
    assert result.reason == "prompt_artifact"

def test_accept_clean_knowledge():
    gate = IngestionQualityGate()
    text = "Postgres FOR UPDATE SKIP LOCKED prevents worker races and should be used for queue claiming."
    result = gate.evaluate(text, source_type="agent")
    assert result.decision == "accept"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest knowledge_os/tests/test_ingestion_quality_gate.py -v`  
Expected: FAIL with `NameError: IngestionQualityGate`

- [ ] **Step 3: Implement gate model and rules**

````python
@dataclass
class GateDecision:
    decision: str  # accept | reject | borderline
    reason: str
    quality_score: float

class IngestionQualityGate:
    PROMPT_PATTERNS = (r"role\s*:", r"tone\s*:", r"strategy\s*:", r"ты\s*-\s*", r"return json", r"```")

    def evaluate(self, text: str, source_type: str) -> GateDecision:
        cleaned = (text or "").strip()
        if len(cleaned) < 200 or len(cleaned) > 4000:
            return GateDecision("reject", "length_out_of_range", 0.0)
        if self._has_prompt_artifact(cleaned):
            return GateDecision("reject", "prompt_artifact", 0.0)
        if self._is_low_information(cleaned):
            return GateDecision("reject", "semantic_empty", 0.1)
        if self._is_borderline(cleaned):
            return GateDecision("borderline", "needs_judge", 0.5)
        return GateDecision("accept", "deterministic_pass", 0.9)
````

- [ ] **Step 4: Rerun unit tests**

Run: `pytest knowledge_os/tests/test_ingestion_quality_gate.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add knowledge_os/app/ingestion/quality_gate.py knowledge_os/tests/test_ingestion_quality_gate.py
git commit -m "feat: add deterministic ingestion quality rules"
```

---

### Task 3: Add Borderline Judge (Fail-Closed)

**Files:**

- Create: `knowledge_os/app/ingestion/judge.py`
- Modify: `knowledge_os/app/ingestion/quality_gate.py`
- Test: `knowledge_os/tests/test_ingestion_quality_gate.py`

- [ ] **Step 1: Add failing tests for borderline judge fallback**

```python
@pytest.mark.asyncio
async def test_borderline_invalid_judge_is_rejected():
    gate = IngestionQualityGate(judge=FakeJudge(invalid=True))
    decision = await gate.evaluate_async("Potentially useful but messy content...", "agent")
    assert decision.decision == "reject"
    assert decision.reason == "judge_invalid"
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest knowledge_os/tests/test_ingestion_quality_gate.py::test_borderline_invalid_judge_is_rejected -v`  
Expected: FAIL with `AttributeError` on missing `evaluate_async`

- [ ] **Step 3: Implement judge contract and async path**

```python
class IngestionJudge:
    async def evaluate(self, text: str, source_type: str) -> dict:
        # must return decision/reason/quality_score
        ...

async def evaluate_async(self, text: str, source_type: str) -> GateDecision:
    base = self.evaluate(text, source_type)
    if base.decision != "borderline":
        return base
    payload = await self.judge.evaluate(text, source_type)
    if not self._valid_judge_payload(payload):
        return GateDecision("reject", "judge_invalid", 0.0)
    return GateDecision(payload["decision"], payload["reason"], float(payload["quality_score"]))
```

- [ ] **Step 4: Rerun judge tests**

Run: `pytest knowledge_os/tests/test_ingestion_quality_gate.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add knowledge_os/app/ingestion/judge.py knowledge_os/app/ingestion/quality_gate.py knowledge_os/tests/test_ingestion_quality_gate.py
git commit -m "feat: add borderline ingestion judge with fail-closed contract"
```

---

### Task 4: Integrate Gate into Long-Term Memory Insert Path

**Files:**

- Modify: `knowledge_os/app/long_term_memory.py`
- Test: `knowledge_os/tests/test_ingestion_quality_integration.py`

- [ ] **Step 1: Write failing integration test for reject-before-insert**

```python
@pytest.mark.asyncio
async def test_ltm_rejects_prompt_artifact(pool, ltm):
    await ltm.store_memory("Ты - ВЕРХОВНЫЙ ДИСТИЛЛЯТОР...", "agent", {})
    count = await pool.fetchval("SELECT count(*) FROM knowledge_nodes WHERE content LIKE 'Ты - ВЕРХОВНЫЙ%'")
    assert count == 0
```

- [ ] **Step 2: Run test to verify fail**

Run: `pytest knowledge_os/tests/test_ingestion_quality_integration.py::test_ltm_rejects_prompt_artifact -v`  
Expected: FAIL (`count == 1`)

- [ ] **Step 3: Add gate check before insert**

```python
from app.ingestion.quality_gate import IngestionQualityGate

gate = IngestionQualityGate()
decision = await gate.evaluate_async(content, source_type=source)
if decision.decision != "accept":
    await gate.log_reject(conn, content=content, source_type=source, reason=decision.reason, gate_stage="ltm")
    logger.warning(f"[LTM] Rejected candidate: {decision.reason}")
    return None
```

- [ ] **Step 4: Rerun integration test**

Run: `pytest knowledge_os/tests/test_ingestion_quality_integration.py::test_ltm_rejects_prompt_artifact -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add knowledge_os/app/long_term_memory.py knowledge_os/tests/test_ingestion_quality_integration.py
git commit -m "feat: enforce ingestion quality gate in long-term memory path"
```

---

### Task 5: Integrate Gate into Knowledge Service Insight Path

**Files:**

- Modify: `knowledge_os/app/services/knowledge_service.py`
- Test: `knowledge_os/tests/test_ingestion_quality_integration.py`

- [ ] **Step 1: Add failing test for insight reject path**

```python
@pytest.mark.asyncio
async def test_save_insight_rejects_service_noise(pool, service):
    await service.save_insight("Role: Victoria\nTone: Professional", "Victoria", {})
    count = await pool.fetchval("SELECT count(*) FROM knowledge_nodes WHERE content LIKE 'Role: Victoria%'")
    assert count == 0
```

- [ ] **Step 2: Run test to verify failure**

Run: `pytest knowledge_os/tests/test_ingestion_quality_integration.py::test_save_insight_rejects_service_noise -v`  
Expected: FAIL (`count == 1`)

- [ ] **Step 3: Add gate decision before embedding generation**

```python
gate = IngestionQualityGate()
decision = await gate.evaluate_async(content, source_type=f"insight:{expert_name}")
if decision.decision != "accept":
    async with pool.acquire() as conn:
        await gate.log_reject(conn, content, f"insight:{expert_name}", decision.reason, "knowledge_service")
    return
```

- [ ] **Step 4: Rerun integration test**

Run: `pytest knowledge_os/tests/test_ingestion_quality_integration.py::test_save_insight_rejects_service_noise -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add knowledge_os/app/services/knowledge_service.py knowledge_os/tests/test_ingestion_quality_integration.py
git commit -m "feat: enforce ingestion quality gate in insight save path"
```

---

### Task 6: Add Metrics + Shadow/Enforce Toggle

**Files:**

- Modify: `knowledge_os/app/ingestion/quality_gate.py`
- Modify: `knowledge_os/app/long_term_memory.py`
- Modify: `knowledge_os/app/services/knowledge_service.py`
- Test: `knowledge_os/tests/test_ingestion_quality_gate.py`

- [ ] **Step 1: Add failing test for shadow mode behavior**

```python
@pytest.mark.asyncio
async def test_shadow_mode_does_not_block_insert():
    gate = IngestionQualityGate(shadow_mode=True)
    decision = await gate.evaluate_async("Role: Victoria...", "agent")
    assert decision.decision == "reject"
    assert gate.should_block(decision) is False
```

- [ ] **Step 2: Run test to verify fail**

Run: `pytest knowledge_os/tests/test_ingestion_quality_gate.py::test_shadow_mode_does_not_block_insert -v`  
Expected: FAIL (missing shadow mode handling)

- [ ] **Step 3: Implement toggles and counters**

```python
self.shadow_mode = os.getenv("INGESTION_GATE_SHADOW_MODE", "true").lower() in ("1", "true", "yes")
self.enforce_percent = int(os.getenv("INGESTION_GATE_ENFORCE_PERCENT", "0"))

def should_block(self, decision: GateDecision) -> bool:
    if self.shadow_mode:
        return False
    if decision.decision == "accept":
        return False
    return random.randint(1, 100) <= self.enforce_percent
```

- [ ] **Step 4: Run full test subset**

Run: `pytest knowledge_os/tests/test_ingestion_quality_gate.py knowledge_os/tests/test_ingestion_quality_integration.py -v`  
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add knowledge_os/app/ingestion/quality_gate.py knowledge_os/app/long_term_memory.py knowledge_os/app/services/knowledge_service.py knowledge_os/tests/test_ingestion_quality_gate.py knowledge_os/tests/test_ingestion_quality_integration.py
git commit -m "feat: add shadow/enforce rollout controls for ingestion quality gate"
```

---

### Task 7: Rollout Verification on Mac Studio

**Files:**

- Modify: `docs/plans/2026-05-04-ingestion-quality-gate-design.md` (append rollout results)
- Test/Run: local docker + DB checks

- [ ] **Step 1: Run shadow mode verification**

Run:

```bash
export INGESTION_GATE_SHADOW_MODE=true
export INGESTION_GATE_ENFORCE_PERCENT=0
pytest knowledge_os/tests/test_ingestion_quality_gate.py knowledge_os/tests/test_ingestion_quality_integration.py -v
```

Expected: PASS

- [ ] **Step 2: Run 10% enforce canary**

Run:

```bash
export INGESTION_GATE_SHADOW_MODE=false
export INGESTION_GATE_ENFORCE_PERCENT=10
docker restart knowledge_os-expert-worker-heavy-3
```

Expected: worker healthy, no crash loops

- [ ] **Step 3: Validate SLO indicators**

Run:

```bash
docker exec knowledge_postgres psql -U admin -d knowledge_os -t -c "SELECT count(*) FROM knowledge_reject_log WHERE created_at > now() - interval '30 minutes';"
docker exec knowledge_postgres psql -U admin -d knowledge_os -t -c "SELECT count(*) FILTER (WHERE metadata->>'distilled'='true'), count(*) FILTER (WHERE metadata->>'distill_status'='retry'), count(*) FILTER (WHERE metadata->>'distill_status'='failed') FROM knowledge_nodes;"
```

Expected: reject logs present, worker throughput non-zero, no OOM pattern

- [ ] **Step 4: Append rollout outcomes in design doc**

```markdown
## Rollout Notes (2026-05-04)

- Shadow mode: pass/fail summary
- 10% canary: throughput delta, reject ratio, RAM impact
- Decision: proceed to 50% or rollback
```

- [ ] **Step 5: Commit**

```bash
git add docs/plans/2026-05-04-ingestion-quality-gate-design.md
git commit -m "docs: add ingestion quality gate rollout verification results"
```

---

## Plan Self-Review

- Spec coverage: all sections mapped to tasks (architecture, criteria, metrics, rollout, rollback, DoD).
- Placeholder scan: no TODO/TBD placeholders in task steps.
- Type consistency: `GateDecision` contract and judge payload kept consistent across tasks.

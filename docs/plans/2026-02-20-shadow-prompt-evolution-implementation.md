# Shadow Prompt Evolution Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement an autonomous self-improvement loop for expert system prompts using local models and A/B shadow testing.

**Architecture:** A background mirroring system in `ai_core.py` that triggers shadow generations for mutated prompts, evaluated by a local LLM judge (`qwq:32b`), with automated promotion based on win-rate.

**Tech Stack:** Python (FastAPI/asyncio), PostgreSQL (asyncpg), Ollama (Local LLMs).

---

### Task 1: Database Schema Expansion

**Files:**

- Create: `knowledge_os/db/migrations/20260220_add_expert_mutations.sql`
- Modify: `knowledge_os/app/rest_api.py`

**Step 1: Create migration SQL**
**Step 2: Add migration to REST API lifespan**
**Step 3: Run migration and verify table exists**
**Step 4: Commit**

---

### Task 2: Shadow Mirroring Logic in AI Core

**Files:**

- Modify: `knowledge_os/app/ai_core.py`
- Test: `knowledge_os/tests/test_shadow_mirror.py`

**Step 1: Write failing test for shadow trigger**
**Step 2: Implement `_trigger_shadow_execution` background task**
**Step 3: Integrate trigger into `run_smart_agent_async_impl`**
**Step 4: Verify production response is not delayed**
**Step 5: Commit**

---

### Task 3: Shadow Evaluator Service

**Files:**

- Create: `knowledge_os/app/shadow_evaluator.py`
- Test: `knowledge_os/tests/test_shadow_evaluator.py`

**Step 1: Write test for Blind Test logic**
**Step 2: Implement `ShadowEvaluator` class using `LocalAIRouter`**
**Step 3: Implement `compare_responses(query, prod, shadow)` method**
**Step 4: Verify judge verdict parsing (Win/Loss/Draw)**
**Step 5: Commit**

---

### Task 4: Automated Promotion Engine

**Files:**

- Create: `knowledge_os/app/promotion_engine.py`
- Modify: `knowledge_os/app/nightly_learner.py`

**Step 1: Implement `check_and_promote_mutations()` logic**
**Step 2: Implement Hot-Swap (Update `experts` table + increment version)**
**Step 3: Integrate into Nightly Learner cycle**
**Step 4: Write integration test for promotion**
**Step 5: Commit**

---

### Task 5: Dashboard Visualization (Canvas)

**Files:**

- Modify: `knowledge_os/dashboard/tabs/data_tab.py`

**Step 1: Replace Canvas mock with real `expert_mutations` data**
**Step 2: Implement Side-by-Side comparison view**
**Step 3: Add manual "Promote" and "Reject" buttons**
**Step 4: Verify UI updates on action**
**Step 5: Commit**

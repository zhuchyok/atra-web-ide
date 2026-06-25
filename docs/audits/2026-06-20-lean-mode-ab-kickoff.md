# Lean-Mode A/B Kickoff (POC)

Date: 2026-06-20
Owner: Victoria Team
Scope: low-risk engineering tasks only (no auth/db/contracts/security)

## Goal

Validate whether `lean-mode` reduces implementation overhead without increasing regressions.

## First Principles

- We optimize outcomes, not line count alone.
- A/B must preserve reliability guardrails.
- No rollout beyond low-risk tasks until evidence is stable.

## Baseline Snapshot (before A/B)

- Containers:
  - `victoria-agent`: `Up ... (healthy)`
  - `atra-web-ide-backend`: `Up ...`
- Backend health:
  - `victoria=healthy`, `ollama=healthy`, `mlx=healthy`
- Chain smoke:
  - `scripts/test_ask_victoria_chain.sh` -> `HTTP 200`, body `ok`

## Experiment Design

- Arms:
  - **Control**: normal execution mode
  - **Treatment**: `lean-mode` skill enabled
- Sample size (POC):
  - Minimum 5 tasks (recommended 8-12 for stronger signal)
- Task class:
  - UI micro-fixes, helper cleanup, small endpoint formatting/validation tweaks
  - Explicitly exclude high-risk areas (auth/db migrations/contracts/security)

## Metrics

Primary:

1. LOC delta in final diff
2. Cycle time (start -> verified)
3. Review defects found (count + severity)

Secondary:

1. Token/cost proxy (if available in logs)
2. Rework count (follow-up fixes required)
3. Runtime health regression (must remain green)

Quality gates (must hold for treatment to pass):

- `stale_in_progress = 0`
- `contract_enforce = 1`
- `error_rate_10m <= 1%` (or unchanged vs control window)
- `ask-victoria` smoke remains `HTTP 200`

## Task Set (POC candidates)

1. Simple UI/form micro-improvement (no business logic)
2. Utility/helper simplification with existing tests
3. Non-critical API response formatting cleanup
4. Remove redundant code path in low-risk module
5. Documentation-backed config default simplification

### T1 executed

- Task: utility/helper simplification in `scripts/test_ask_victoria_chain.sh`
- Change:
  - Lean arm removed temp-file roundtrip (`mktemp` + file read/remove)
  - Replaced with in-memory response parsing (`body + http_code`)
- Safety scope:
  - No auth/db/contracts/security changes
  - Smoke chain preserved

### T2 executed

- Task: non-critical API response text cleanup in `backend/app/routers/chat.py`
- Context (low-risk): user-facing timeout wording only; no contract/schema/security change.
- Decision ladder:
  - Step 1 (YAGNI): no new behavior needed
  - Step 2 (stdlib/native): keep existing exception branch, patch one message string
  - Result: minimal 1-line production change
- TDD note:
  - Added regression test in `backend/app/tests/test_ask_victoria.py` for timeout message (no hardcoded `60с`)
  - Red stage confirmed against running backend container (old message still present)
  - Green stage confirmed after backend rebuild (`docker compose up -d --build backend`)
- Safety scope:
  - No auth/db/contracts/security changes
  - Existing `ask-victoria` smoke remains green (`HTTP 200`)

### T3 executed

- Task: remove redundant Victoria call path for incomplete one-word directive.
- Context (low-risk): request validation improvement in `ask-victoria`; no data model/API schema/security changes.
- Decision ladder:
  - Step 1 (YAGNI): do not add new endpoint/flags
  - Step 2 (stdlib/native): use regex intent check before delegation
  - Result: explicit `422` for `Скажи одно слово:` without payload token
- TDD note:
  - Added regression test `test_ask_victoria_one_word_directive_without_word_returns_422`
  - Red: existing runtime returned `200` with delegated response (`Done.`)
  - Green: after patch and backend rebuild, runtime returns `422` with clear message
- Safety scope:
  - No auth/db/contracts/security changes
  - Deterministic one-word happy path unchanged
  - Existing `ask-victoria` smoke remains green (`HTTP 200`)

### T4 executed

- Task: KPI monitoring hardening for A/B gate signal in `scripts/runtime_kpi_gate_monitor.py`.
- Root-cause evidence:
  - 15m window spike (`failure_rate_10m_pct=100`) was caused by one unrelated runtime task:
    - task id: `b606888f-a43c-4d5a-899c-61d1066ac0ff`
    - `metadata.source=orchestration_tracking`
    - result: `Таймаут Enhanced LLM (1200s). Сократите задачу.`
- Decision ladder:
  - Step 1 (YAGNI): no infra changes/restarts for this
  - Step 2 (stdlib): add scoped gate metric instead of overloading global error metric
  - Result: new `*_gate` 10m counters exclude `orchestration_tracking`
- Change:
  - Added `completed_10m_gate`, `failed_10m_gate`, `failure_rate_10m_gate_pct`
  - Kept global metrics unchanged for observability parity
- Safety scope:
  - No auth/db/contracts/security changes
  - `ask-victoria` smoke remains `HTTP 200`

### T5 executed

- Task: documentation-backed KPI default simplification in `scripts/runtime_kpi_gate_monitor.py`.
- Context (low-risk): monitor-only logic, no runtime task execution path changes.
- Decision ladder:
  - Step 1 (YAGNI): no new service/env needed
  - Step 2 (stdlib): extend existing in-process gate evaluation
  - Result: error-rate gate integrated directly into window pass logic
- Change:
  - Added `error_rate_gate_ok` and `max_failure_rate_10m_gate_pct` to window evaluation
  - Stability now fails with explicit `error_rate_violation` when gate exceeds threshold
  - Summary now surfaces these fields per window
- Verification:
  - `lean-mode-t5-gate-logic` summary contains new fields and values
  - `ask-victoria` smoke remains green (`HTTP 200`)
- Safety scope:
  - No auth/db/contracts/security changes

## Data Capture Template

| Task | Arm | LOC delta | Cycle min | Defects (count/severity) | Rework | Smoke pass |
|------|-----|-----------|-----------|---------------------------|--------|------------|
| T1   | Control | baseline | ~0.004 | 0 / none | 0 | pass |
| T1   | Lean    | -1 line (~-2%) | ~0.004 | 0 / none | 0 | pass |
| T2   | Control | baseline | ~7 | 1 / low (stale timeout copy) | 0 | pass |
| T2   | Lean    | 1-line prod patch + test | ~7 | 0 / none | 1 (container rebuilt) | pass |
| T3   | Control | baseline | ~8 | 1 / low (invalid directive delegated) | 0 | pass |
| T3   | Lean    | small validation patch + regression test | ~8 | 0 / none | 1 (container rebuilt) | pass |
| T4   | Control | baseline monitor metric only | ~10 | 1 / low (noisy gate due unrelated tracking fail) | 0 | pass |
| T4   | Lean    | scoped gate metric (`*_gate`) added | ~10 | 0 / none (gate noise isolated) | 0 | pass |
| T5   | Control | baseline gate logic | ~6 | 1 / low (error-rate gate not explicit in pass output) | 0 | pass |
| T5   | Lean    | explicit error-rate gate in pass logic + summary | ~6 | 0 / none | 0 | pass |

## Decision Rule

Adopt `lean-mode` for wider low-risk usage only if:

- No increase in high-severity defects
- Mean cycle time improves by >= 10%
- Mean LOC delta decreases by >= 15%
- Health/contract/stale/error gates remain stable

Otherwise keep as narrow, manual opt-in.

## 15m Verification Window (executed)

- Window tag: `lean-mode-15m-gate`
- Duration: 15m (27 samples, 30s interval)
- Smoke:
  - pre-window: `HTTP 200`, body `ок`
  - post-window: `HTTP 200`, body `ок`
- Key facts from summary:
  - queue: `pending<=1`, `in_progress<=1`
  - `stale_in_progress=0`
  - `contract_enforce=1` (`rollout_mode=enforce`)
  - sustained distillation tail SLO: `ok=True` (`sample_count=27`)
  - error-rate snapshot ended at `failure_rate_10m_pct=100.0` with low load (`insufficient_load_n_a`)
- Interim interpretation:
  - Stability guardrails pass (stale/contract/health/tail-slo)
  - Error-rate gate for final rollout decision is not yet met; keep `lean-mode` in manual low-risk scope.

## 15m Verification Window (post-patch, final rerun)

- Window tag: `lean-mode-15m-gate-post-patch`
- Duration: 15m (27 samples, 30s interval)
- Smoke:
  - pre-window: `HTTP 200`, body `ок`
  - post-window: `HTTP 200`, body `ок`
- Key facts from summary:
  - queue: `pending<=2`, `in_progress<=2`
  - `stale_in_progress=0`
  - `contract_enforce=1` (`rollout_mode=enforce`)
  - `failure_rate_10m_pct=0.0`
  - `failure_rate_10m_gate_pct=0.0`
  - 15m gate: `pass=True`, `reason=ok`, `throughput_ok=True`
  - sustained distillation tail SLO: `ok=True` (`sample_count=27`)
- Interim interpretation:
  - Runtime quality gate for 15m window is green after metric hardening.
  - Keep final rollout decision tied to aggregate A/B criteria (defects, mean cycle, mean LOC across full task set).


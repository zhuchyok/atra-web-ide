# Self-Improving Loop Blueprint (Expert Mode)

Date: 2026-09-12  
Context: move from operationally stable multi-agent runtime to stable quality on complex reasoning.

## 1) Objective

Build a production cognitive loop:

`feedback -> memory curation -> policy update -> routing update -> re-eval -> guarded rollout`

without replacing core runtime components.

## 2) Current assets already in repo

- Runtime gates and health:
  - `scripts/preflight_runtime_guard.py`
  - `scripts/runtime_kpi_gate_monitor.py`
- Routing and model selection:
  - `knowledge_os/app/local_router.py`
  - `knowledge_os/app/intelligent_model_router.py`
  - `knowledge_os/app/available_models_scanner.py`
  - `knowledge_os/app/ai_core.py`
- Quality/eval:
  - `knowledge_os/app/shadow_evaluator.py`
  - `knowledge_os/app/task_result_validator.py`
  - `knowledge_os/app/model_performance_tracker.py`
  - `knowledge_os/app/canary_router.py`
  - `knowledge_os/app/quality_pipeline.py`
- Memory:
  - `knowledge_os/app/memory/memory_service.py`
  - `knowledge_os/app/memory/journal_manager.py`
  - `knowledge_os/app/knowledge_fabric.py`
  - `knowledge_os/app/lancedb_service.py`
  - `knowledge_os/app/services/knowledge_service.py`
- Policy and adaptation:
  - `knowledge_os/app/autonomous_policy_enforcer.py`
  - `knowledge_os/app/proactive_dna_refactor.py`
  - `knowledge_os/app/constitutional_court.py`
  - `knowledge_os/app/meta_architect.py`

## 3) Main gaps (root-cause view)

1. Memory is not hard-partitioned by trust/expiry, so noisy events leak into decision context.  
2. Eval is present, but there is no single acceptance gate for policy/routing updates.  
3. Router selection is mostly availability/heuristics-driven, not quality-per-latency driven by measured outcomes.  
4. Policy updates are not consistently tied to replay evidence and rollback ids.

## 4) Target architecture (minimal-change)

### A. Memory trust lanes

Introduce strict memory classes in metadata:

- `authoritative` (durable rules/runbooks),
- `episodic` (task outcome learnings),
- `transient` (short-lived runtime hints),
- `noise` (excluded from retrieval).

Required metadata keys (all classes):  
`memory_type`, `confidence`, `source`, `expires_at`, `used_in_decision`, `policy_version`.

### B. Cognitive quality gate

Add a single gate script that combines:

- preflight checks,
- KPI checks,
- reasoning eval score checks,
- routing decision quality checks.

Gate output format (JSON):
- `gate_pass`
- `operational_pass`
- `cognitive_pass`
- `reasoning_score`
- `hallucination_rate`
- `routing_win_rate`
- `recommended_action` (`rollout` / `canary_only` / `rollback`)

### C. Policy patch protocol

Any routing/prompt/policy update must carry:

- `proposal_id`,
- `hypothesis`,
- `offline_eval_delta`,
- `canary_eval_delta`,
- `rollback_id`.

No auto-apply when `offline_eval_delta <= 0`.

### D. Router decision journal

For each routed task record:
- task type,
- chosen expert/model,
- alternatives considered,
- latency,
- quality verdict (post-fact),
- regret flag (was another choice better).

Use this to train/adjust routing priors.

## 5) Phased rollout

### Phase 0 (2-3 days): Baseline and instrumentation

- Add memory-type metadata enforcement.
- Add routing decision journal table/log stream.
- Add cognitive KPI snapshot job.

Done when:
- 95%+ new memory entries have `memory_type/confidence/expires_at`,
- routing logs present for 95%+ routed tasks.

### Phase 1 (4-6 days): Unified cognitive gate

- Create `scripts/cognitive_quality_gate.py`.
- Integrate outputs from:
  - `preflight_runtime_guard.py`
  - `runtime_kpi_gate_monitor.py` (latest summary/snapshot)
  - reasoning eval runner (fixed benchmark set)
- Persist gate reports under `docs/audits/`.

Done when:
- gate runs on-demand in < 90 sec,
- gate can fail for cognitive reasons even when operational status is green.

### Phase 2 (5-7 days): Policy update with replay + canary

- Introduce policy proposal artifact (YAML/JSON).
- Run replay benchmark before apply.
- Route 10-20% traffic via canary policy.
- Auto-rollback on score or error-rate breach.

Done when:
- every applied policy has `before/after` evidence,
- rollback works in one command.

### Phase 3 (7-10 days): Self-improving loop automation

- Harvest failed/low-quality tasks nightly.
- Generate candidate policy patches.
- Run replay + gate + canary automatically.
- Auto-promote only if all gates pass.

Done when:
- >= 30% accepted improvements are auto-generated,
- no increase in operational incident rate.

## 6) KPIs (hard gates)

Operational:
- `pending`, `in_progress`, `stale_in_progress`
- `throughput_1h`, `throughput_24h`
- `failed_1h`, `failed_24h`, `error_rate`
- `contract_enforced_ratio`

Cognitive:
- `reasoning_score` (benchmark set)
- `hallucination_rate`
- `routing_win_rate`
- `decision_regret_rate`
- `memory_noise_ratio`
- `auto_improvement_share`

## 7) Pre-mortem risks and guardrails

1. **Feedback contamination** (bad outputs become policy fuel).  
   Guardrail: authoritative-only training set for policy auto-patch; noisy samples quarantined.

2. **Overfitting to benchmark** (improves score, hurts real tasks).  
   Guardrail: holdout eval set + canary with live regret tracking.

3. **Complexity creep** (too many moving parts).  
   Guardrail: no new orchestration service; build as scripts/jobs over existing modules.

## 8) First implementation tasks (ready to execute)

1. Implement `scripts/cognitive_quality_gate.py` (single-shot snapshot gate).  
2. Add memory-type validation in memory write paths.  
3. Add routing decision log schema + writer in `local_router`/`ai_core`.  
4. Create benchmark runner for complex reasoning tasks and include in gate.

## 9) Definition of Done (program level)

- System passes both operational and cognitive gates for 7 consecutive daily runs.
- New policy/routing updates are impossible without replay evidence.
- Reasoning quality trend is positive while queue/error SLO remains stable.


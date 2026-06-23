# Multiagent 100 Rollout Audit (Phase 0 + Phase 2)

Date: 2026-06-13  
Scope: Baseline freeze, canary enablement, post-change verification  
Operator: Codex agent

## Step 0 - Baseline Freeze (before config changes)

- Health:
  - Open WebUI: `{"status":true}` latency ~0.015s
  - Victoria: `{"status":"ok","agent":"Виктория"}` latency ~0.748s
  - Proxy: `victoria_reachable=true` latency ~0.197s
  - Backend: `dependencies.victoria=healthy`, `ollama=healthy`, `mlx=healthy`
- Proxy summary baseline:
  - `discuss`: success=56, error=2, total=58, avg latency=5.641s
  - `victoria-wisdom-v3.5`: success=58, error=0, total=58, avg latency=5.1623s
- Queue baseline (tasks):
  - pending=1, in_progress=0, processing=0, running=0, failed=7, completed=2684
- Stale in_progress (>45 min): 0
- Completed in last 10m: 0
- Failed in last 60m: 1

## Step 1 - Canary Flags Enablement

File changed: `knowledge_os/docker-compose.agents.yml`

Enabled in `victoria-agent`:

- `ORCHESTRATION_V2_ENABLED: "true"`
- `ORCHESTRATION_V2_PERCENTAGE: "10"`
- `EXECUTE_ASSIGNMENTS_IN_RUN: "true"`
- `PREFER_EXPERTS_FIRST: "true"`

Enabled in `knowledge_os_orchestrator`:

- `ORCHESTRATOR_CONTRACT_ROLLOUT_MODE: "auto"`
- `ORCHESTRATOR_CONTRACT_CANARY_PERCENT: "20"`
- `ORCHESTRATOR_ROLLOUT_KPI_WINDOW_MIN: "10"`

Validation:

- `docker compose ... config` succeeded (syntax OK).
- Recreated services:
  - `victoria-agent`
  - `knowledge_os_orchestrator`

## Step 2 - Post-change Verification

Runtime env verification:

- Victoria container env: `true 10 true true`
- Orchestrator env: `auto 20 10`

Health after rollout:

- Open WebUI healthy
- Victoria healthy (latency ~0.002s on sampled check)
- Proxy healthy (`victoria_reachable=true`)
- Backend healthy (mlx briefly degraded during warmup, recovered to healthy on recheck)

Functional canary (proxy path):

- 20 requests mixed (`victoria-wisdom-v3.5` + `discuss`)
- Result: `ok=20/20`, `error_rate=0.0`, average latency=4.4s
- Output guard preserved (`<think>` not leaked in tested responses)

Foundation checks:

- Experts in DB: 85
- HNSW index: `knowledge_nodes_embedding_hnsw_idx` present

Operational logs:

- Victoria: no ERROR/Exception lines in canary window check
- Orchestrator:
  - rollout logs visible
  - effective mode observed as `enforce` with canary=20 (auto mode switched based on internal rollout logic and KPI gate)

Queue after rollout:

- pending=0, in_progress=1, processing=0, running=0, failed=7, completed=2684
- Stale in_progress (>45 min): 0
- Old pending/in_progress (>2h): 0

## Step 3 - Async/Blackboard Hardening (partial close)

Issue detected during diagnostics: Redis stream had accumulated many orphan consumer groups.

Before hardening:

- stream `stream:event_bus_stream` length: 7104
- group count: 4072
- total pending: 4
- max pending per group: 2
- max lag observed: 7078

Change applied:

- File: `knowledge_os/app/event_bus_redis_bridge.py`
- Added safe stale-group cleanup at startup:
  - considers only `group_*`
  - never touches current active group
  - only removes groups with `pending=0`
  - requires all consumers idle above threshold (`REDIS_BRIDGE_STALE_GROUP_IDLE_MS`, default 6h)
  - capped by `REDIS_BRIDGE_STALE_GROUP_PRUNE_LIMIT` (default 200 per start)

Verification:

- Python compile check passed (`py_compile`)
- Orchestrator logs confirm cleanup on startup:
  - `removed stale groups: 200`
  - new active group created successfully
- Post-restart health:
  - Victoria healthy
  - Proxy healthy
  - Backend healthy (Victoria/Ollama/MLX healthy)
- Post-hardening short e2e:
  - 12 mixed requests via proxy
  - `ok=12/12`, `error_rate=0.0`, avg latency=5.123s

After hardening:

- group count: 3873 (reduced by ~199 after one cleanup cycle)
- total pending: 4
- max pending per group: 2
- nonzero-lag groups: 214

## Decision and Rollback Status

- Decision: keep canary flags enabled at current percentages.
- Rollback: not required (no regressions detected in phase 0/2 checks).

## Step 4 - Trust Gates (Adversarial + Contract + HITL)

Contract gate status:

- Orchestrator rollout remains active with auto mode and observed runtime enforcement logs:
  - `mode=enforce canary=20`
- Contract envelope and metadata continue to flow through worker completion audit trail.

HITL enablement:

- Enabled in worker services (`expert-worker-heavy`, `expert-worker-anna`, `expert-worker-victoria`, dynamic slots):
  - `HITL_ENFORCE_HIGH_RISK_TASKS: "true"`
  - `HITL_HIGH_RISK_LEVELS: "critical"`
  - `HITL_APPROVAL_TIMEOUT_SEC: "180"`
- Runtime env verified in active workers: `true critical 180`

HITL bug fix:

- File: `knowledge_os/app/human_approval.py`
- Fixed `wait_for_approval()` to await Future directly (removed invalid `__await__()` usage causing `TypeError`).
- Added guards to avoid `set_result()` on already-resolved futures.
- Compile check passed.

Trust gate validation:

- Adversarial gate (synthetic deterministic probe with stubbed `ai_core`) returned:
  - `survived=true`
  - `verification_reason=critic_json_ok`
- HITL runtime probe:
  - approval request created successfully
  - timeout path returns `approved=false` without exceptions after fix

Post-step health/e2e:

- Services healthy (Victoria, proxy, backend; backend MLX occasionally warmup-degraded then recovers)
- 8 mixed proxy requests: `ok=8/8`, `error_rate=0.0`, avg latency=12.187s

## Next Gates

1. Phase 7: 24h sustained gate + 7d stability evidence collection in `docs/audits`.
2. Optional continuation: run additional controlled restart cycles to gradually prune more stale Redis groups without risky bulk-delete.
3. Optional cleanup: align residual non-gate runtime errors (`ExtendedThinkingEngine.think`, mutation engine local var) to further reduce noisy error budget.

## Phase 7 Kickoff

Artifacts produced:

- `docs/audits/2026-06-13-multiagent100-kickoff.jsonl`
- `docs/audits/2026-06-13-multiagent100-kickoff-summary.md`

Kickoff snapshot outcome:

- samples: 5 (about 5 minutes)
- stability metrics: clean (`pending=0`, `stale_in_progress=0`, `failed_10m=0`)
- contract flags: `contract_rollout_mode=enforce`, `contract_enforce=1`
- sustained tail SLO: not yet passable due `insufficient_samples` (expected for short kickoff)

Long run started:

- 24h monitor launched with tag `multiagent100-24h-live`
- This gate requires wall-clock runtime and cannot be truthfully marked complete in the same execution session.

## Phase 7 - Pending Plateau RCA and Net-Drain Fix (2026-06-15)

Observed plateau:

- Pending queue stuck around `21` with frequent status churn and no durable drain.
- Breakdown by `target_expert + assignee` showed concentration on non-live identities (`Юлия`, `Светлана`, `Леонид`, `Василий`, `Александр`, `Алекс`, `Людмила`) plus heavy share on `Анна/Роман`.

Root cause (routing/dispatch interaction):

- Runtime reconcile for non-live assignees used `updated_at` grace window.
- `updated_at` was refreshed by orchestrator cycles, so non-live pending tasks were repeatedly considered "fresh" and avoided reopen.
- Result: repeated dispatch/status activity without true queue reduction.

Changes applied:

- File: `knowledge_os/app/enhanced_orchestrator.py`
- In `dispatch_pending_assignments()`, removed `updated_at = NOW()` from dispatch metadata updates.
- In `reconcile_nonlive_assignments()`, changed pending reopen staleness check from `updated_at` to `created_at` grace window.

Verification evidence:

- Orchestrator logs:
  - `Reopened tasks from non-live experts=... pending=7 in_progress=0`
  - subsequent assignment cycle: `phase=2 ... result=6 assigned, 1 failed`
- Assignee distribution shifted from non-live names to live workers only.
- Pending trend during observation window:
  - `21 -> 20 -> 19`
  - current pending assignees: `Роман=8`, `Анна=7`, `Виктория=4`

Status:

- Net-drain behavior achieved (initial).
- Continue sustained monitoring to confirm drift below gate threshold with no rebound.

## Dynamic Worker Reliability Fix (2026-06-15)

Issue:

- Dynamic spawn from `knowledge_os_orchestrator` intermittently failed (`rc=1`) and target experts were not becoming live.
- Reproduction from inside orchestrator showed Docker mount denial on dynamic service bind mounts (`/app/data`, `/app/knowledge_os`).

Fixes:

- File: `knowledge_os/docker-compose.agents.yml`
  - Removed host bind mounts from `expert-worker-dynamic-1/2` (`../data:/app/data`, `../knowledge_os:/app/knowledge_os`).
  - Kept `redis_data` volume and existing runtime env/profile setup.
- File: `knowledge_os/app/enhanced_orchestrator.py`
  - Hardened `_spawn_dynamic_worker()`:
    - logs both compose `stdout` and `stderr` on non-zero return.
    - does not fail immediately on non-zero return; still validates live heartbeat during warmup window.
    - emits dedicated metric result `success_after_nonzero_rc` when worker becomes live despite non-zero compose return.

Verification:

- `docker compose ... config` passed after compose changes.
- Spawn command from inside `knowledge_os_orchestrator` for `expert-worker-dynamic-1` returned `RC=0` and container started.
- Runtime registry confirmed live dynamic heartbeats for target experts (e.g., `Леонид`, `Светлана`) after spawn.

Monitoring hardening:

- File: `scripts/runtime_kpi_gate_monitor.py`
- Added automatic dynamic-routing alerts to each sample + summary:
  - `dynamic_mounts_denied_count`
  - `dynamic_no_slot_available_count`
  - `dynamic_failed_nonzero_rc_count`
  - `dynamic_alert_count`
  - `dynamic_slot_running / dynamic_slot_count`
- Gate stability now includes `dynamic_alert_ok` (fails if dynamic alert count > 0 in window).
- Smoke test artifact:
  - `docs/audits/2026-06-15-dynamic-alert-smoke.jsonl`
  - `docs/audits/2026-06-15-dynamic-alert-smoke-summary.md`

## Phase 7 - Sustained Gate Restart (R3, dynamic-alert aware)

- Previous long run (`multiagent100-24h-r2`) was stopped and replaced to ensure a clean 24h window on the updated monitor logic (with dynamic worker alert signals included in stability gate).
- New sustained run started:
  - tag: `multiagent100-24h-r3-dynalerts`
  - artifacts:
    - `docs/audits/2026-06-15-multiagent100-24h-r3-dynalerts.jsonl`
    - `docs/audits/2026-06-15-multiagent100-24h-r3-dynalerts-summary.md`
- Kickoff snapshot:
  - `pending=15`, `in_progress=0`, `stale_in_progress=0`
  - `dynamic_alert_count=0`
  - `dynamic_slot_running=1/1`

## Mini Verification Run (2026-06-17, /expert follow-up)

- Started additional short gate run for fast operational verdict without waiting for a new 24h wall-clock window.
- Run params:
  - tag: `multiagent100-mini-verify`
  - duration: `2h`
  - interval: `300s`
- Artifacts:
  - `docs/audits/2026-06-16-multiagent100-mini-verify.jsonl`
  - `docs/audits/2026-06-16-multiagent100-mini-verify-summary.md`

## RCA + Targeted Drain Fix (2026-06-18)

Root causes identified:

- Repeated `Victoria Enhanced` background soft-timeouts (`1200s`) on operational file-audit tasks.
- These tasks are deterministic by nature but still routed through expensive enhanced path.
- Result was slow churn (pending/in_progress aging) instead of fast closure.

Fixes applied:

- File: `knowledge_os/app/task_rule_executor.py`
  - Added deterministic file-audit handler for tasks like `проверь файл ...`.
  - Supports two checks in first N lines:
    - hardcoded secrets
    - runtime `pip install` usage.
  - Returns strict output format (`ОК` or `ПРОБЛЕМА + цитата`) without LLM.
- File: `knowledge_os/app/enhanced_orchestrator.py`
  - Extended Phase 2.5 rule fallback selection:
    - configurable `ORCHESTRATOR_RULE_FALLBACK_MIN_ATTEMPTS`
    - optional immediate routing for file-audit tasks via `ORCHESTRATOR_RULE_FALLBACK_FOR_FILE_AUDIT` (default `true`).
  - Increased fallback batch limit from 20 to 50 for burst drain.

Post-fix verification:

- Pending trend after orchestrator restart: `1 -> 0` and stayed at `0` during observation window.
- Current queue snapshot:
  - `pending=0`, `in_progress=1`, `stale_in_progress=0`
  - `completed_10m=4`, `failed_10m=0`
- Recent completed outputs show deterministic `ОК` results for targeted file-audit tasks.

# Agent Teams Adoption Matrix (ATRA)

Scope: safe adoption of useful patterns from `777genius/agent-teams-ai` into ATRA without replacing ATRA orchestration core.

## Decision Principles

- **First Principles:** do not replace working orchestration core; improve operator visibility and control surface.
- **Five Whys:** treat UX pain as symptom, not reason to swap runtime architecture.
- **Pre-mortem:** assume integration fails due to double orchestration, hidden queue conflicts, and observability overhead.
- **KISS / Occam:** add thin adapter and UI layers only; avoid second control plane.
- **Strong Opinions, Weakly Held:** keep ATRA core as source of truth unless sustained evidence disproves this.

## Adoption Matrix

### Keep As-Is (already in ATRA)

- Blackboard auctions, self-pickup, and swarm delegation.
- Runtime task recovery (`stale in_progress`, retries, fallback staging).
- Human approvals/comments API flow.
- Open WebUI -> Victoria bridge path and project context routing.
- MLX stability invariants and incident guardrails.

### Adopt (with adaptation)

- Team map UX: "who works on what now", blockers, handoffs, task ownership.
- Task timeline UX: lifecycle, status transitions, action provenance.
- Review ergonomics: easier task-level review surfaces in operator UI.
- Better per-task observability panels (logs, decisions, retries, elapsed time).

### Do Not Adopt Directly

- Any second orchestration engine controlling task lifecycle.
- Parallel queue ownership that can mutate task state outside ATRA contracts.
- Runtime/provider abstraction that bypasses existing policy and safety gates.

### Sandbox First (required before rollout)

- Adapter-only integration path (read-only from ATRA core, controlled writes via existing APIs).
- Feature flags for each adopted capability.
- Isolated smoke and sustained verification windows.

## Execution Plan

### Phase 1: Inventory and Interface Freeze

- Lock ATRA source-of-truth surfaces:
  - tasks state transitions,
  - assignment and handoff contracts,
  - approval/rejection lifecycle.
- Define adapter contract for UI-only enhancements.
- Prohibit direct DB writes from new UI modules.

Ready criteria:

- interface spec approved,
- no runtime behavior changes merged.

### Phase 2: Operator UX in Read-Only Mode

- Implement team map and task timeline as read-only dashboards.
- Add per-task observability panes (status path, retries, recent actions, key logs).
- Validate no side effects on orchestration loop.

Ready criteria:

- queue metrics unchanged vs baseline,
- no new stale tasks introduced,
- no added error bursts.

### Phase 3: Controlled Write Actions

- Enable scoped actions via existing APIs only:
  - comment,
  - approve/reject,
  - safe retry/requeue under policy.
- Keep feature flags per action.

Ready criteria:

- contract checks pass,
- action audit trail complete,
- rollback tested.

### Phase 4: Sustained Gate and Rollout

- Run 15-30m smoke gate then 24h sustained gate.
- Roll out progressively (canary -> wider exposure) after sustained pass.

Ready criteria:

- all KPI gates pass in sustained window.

## KPI Gates

Mandatory checks:

- `pending` / `in_progress` trend stays within baseline envelope.
- `stale_in_progress` does not increase.
- `completed_10m` does not regress under comparable load.
- error rate does not increase (`failed / (completed + failed)` in rolling 60m).
- critical container health remains stable.
- no contract violations in task/approval flows.

## Rollback Policy

Immediate rollback triggers:

- growing `stale_in_progress` trend,
- queue ownership conflicts or task state flapping,
- orchestration latency spike with degraded throughput,
- any security or policy bypass,
- repeated incidents requiring manual queue surgery.

Rollback actions:

- disable relevant feature flags,
- return to read-only mode,
- restore previous UI bundle,
- run post-rollback smoke (health + queue + approval path).

## Pre-mortem (Top 3 Failure Modes)

- Double control plane causes conflicting task transitions.
- UI observability layer increases load and worsens latency.
- Partial integration bypasses approval/contract enforcement.

Mitigations:

- strict API-only writes,
- rate-limited telemetry collection,
- contract tests as hard gate in rollout pipeline.

## Verification Checklist

- Health endpoints:
  - Open WebUI,
  - Victoria,
  - REST API,
  - dashboard.
- Queue integrity:
  - `pending/in_progress`,
  - `stale_in_progress`,
  - retry behavior.
- Throughput and error envelope:
  - `completed_10m`,
  - 60m error rate.
- Approval/comment lifecycle:
  - create,
  - transition,
  - audit visibility.

## Ownership (RACI)

- Team Lead (A): rollout decisions and rollback authority.
- Backend + DB (R): adapter contracts and state safety.
- DevOps + Monitor (R): runtime gates and incident response.
- QA (R): smoke/sustained verification evidence.
- Security (C): policy and boundary checks.

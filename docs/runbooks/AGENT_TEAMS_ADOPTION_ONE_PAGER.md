# Agent Teams Adoption One-Pager (ATRA)

Purpose: start adoption safely without touching ATRA orchestration core behavior.

Linked standard:

- `docs/runbooks/AGENT_TEAMS_ADOPTION_MATRIX.md`

## Day-0 Startup Checklist

- Confirm source-of-truth remains ATRA (`tasks`, orchestrator state machine, approvals).
- Enable read-only mode for new operator UI surfaces.
- Ensure all write actions go only through existing ATRA APIs.
- Verify feature flags exist for every adopted capability.
- Capture baseline metrics before rollout.

## Baseline Snapshot (before any rollout)

- Queue: `pending`, `in_progress`, `stale_in_progress`.
- Throughput: `completed_10m`.
- Reliability: 60m error rate (`failed / (completed + failed)`).
- Health: Open WebUI, Victoria, REST API, dashboard, orchestrator, DB.
- Policy: approval and comment flow passes.

## Rollout Sequence

1. **Read-only UX phase**

- Team map, timeline, and observability panes only.
- No DB writes, no orchestration mutations.

2. **Controlled actions phase**

- Enable only comment/approve/reject/retry via existing APIs.
- Keep each action behind separate flag.

3. **Canary phase**

- 15-30m smoke gate.
- If pass, run 24h sustained gate.

4. **Progressive exposure**

- Expand only after sustained pass.

## Hard Gates (must pass)

- `pending/in_progress` trend does not worsen vs baseline.
- `stale_in_progress` stays flat or improves.
- `completed_10m` does not regress under comparable load.
- 60m error rate does not increase.
- No contract violations in task and approval lifecycle.
- Critical container health remains stable.

## Immediate Rollback Triggers

- Task state flapping or queue ownership conflict.
- Growth in stale `in_progress`.
- Throughput drop with latency increase.
- Security/policy bypass or audit gap.
- Repeated manual queue surgery needed.

## Rollback Procedure

- Disable relevant feature flags.
- Return to read-only mode.
- Restore previous UI bundle.
- Re-run smoke checks (health + queue + approvals).
- Record incident and update matrix mitigations.

## Ownership

- Team Lead: go/no-go and rollback authority.
- Backend + DB: contract safety and data integrity.
- DevOps + Monitor: runtime health and alerting.
- QA: smoke and sustained verification evidence.
- Security: boundary and policy checks.

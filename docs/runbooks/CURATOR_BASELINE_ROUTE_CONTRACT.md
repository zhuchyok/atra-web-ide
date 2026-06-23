# Curator Baseline And Route Contract

Date: 2026-06-09  
Scope: `scripts/curator_send_tasks_to_victoria.py` async polling path.

## Baseline Incident Profile

Observed before hardening:

- Intermittent `Read timed out` on `GET /run/status/{task_id}` even when containers were up.
- False-negative health checks (`/health` timeout) caused curator aborts before task send.
- Wasteful escalation for hard server caps (`Victoria Enhanced не уложилась в 1200s`), increasing runtime without improving success.

Latest acceptance reference:

- Report: `docs/curator_reports/curator_2026-06-08_19-32-47.json`
- `tasks_count=2`, `success_count=2`, `error_rate_pct=0.0`
- `timeout_like_errors=0`, `stale_like_errors=0`, `quality_gate_failed=0`

## Expected Route Contract

### 1) Input normalization

- Task file/objective list MUST be normalized via `_normalize_tasks_atomic`.
- Duplicate and near-empty items MUST be dropped.

### 2) Async execution path

- Curator MUST send `POST /run?async_mode=true`.
- Polling MUST use bounded adaptive interval (`min -> backoff -> max`) with jitter.
- 404 status responses MUST use bounded retry (`STATUS_404_MAX_RETRIES`).

### 3) Timeout semantics

- `timeout_like` errors are eligible for escalation only if transient.
- `hard server timeout` (`enhanced_solve_timeout`, `enhanced_llm_timeout`, explicit `не уложилась`) MUST be fail-fast (no max-wait escalation).

### 4) Health gate

- Pre-flight health check MUST retry (`HEALTH_RETRIES`) with configurable timeout.
- Single probe failure MUST NOT abort run.

### 5) Report invariants

- Every run MUST produce JSON report with `summary` keys:
  - `error_rate_pct`
  - `throughput_tasks_per_min`
  - `timeout_like_errors`
  - `quality_gate_failed`
  - `stale_like_errors`

## Rollback Guardrails

If regression appears:

1. Revert only `scripts/curator_send_tasks_to_victoria.py` to previous commit.
2. Keep existing env knobs and lower risk by setting:
   - `CURATOR_POLL_INTERVAL_MAX_SEC=10`
   - `CURATOR_POLL_BACKOFF_FACTOR=1.0`
   - `CURATOR_POLL_JITTER_RATIO=0.0`
3. Re-run quick canary and one atomic canary before wider rollout.

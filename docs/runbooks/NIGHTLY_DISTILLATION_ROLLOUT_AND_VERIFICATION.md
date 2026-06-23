# Nightly Distillation Rollout and Verification

This runbook standardizes shadow -> enforce rollout for distillation-tail control.

## 1) Rollout stages

### Stage A: Shadow (observe only)

- Keep runtime monitor running and collect baseline.
- Do not enforce promotion/rollback from tail SLO yet.
- Capture:
  - `eligible_now` series
  - queue: `pending`, `in_progress`
  - `stale_in_progress_45m`
  - `failure_rate_10m_pct`
  - container health + contract enforce state

### Stage B: Enforce (guardrails on)

- Enable adaptive nightly mode controls:
  - `NIGHTLY_DISTILL_FORCE_MODE=auto`
  - `NIGHTLY_DISTILL_TURBO_ENTER_WATERMARK`
  - `NIGHTLY_DISTILL_TURBO_EXIT_WATERMARK`
  - `NIGHTLY_DISTILL_TURBO_ENTER_STREAK`
  - `NIGHTLY_DISTILL_TURBO_EXIT_STREAK`
- Enable sustained tail SLO checks in runtime monitor:
  - `--tail-slo-max-consecutive-breach`
  - `--tail-slo-max-above-target-ratio`
  - `--tail-slo-min-samples`

### Stage C: Rollback criteria

Rollback to normal mode (or disable enforce) if any of:

- sustained tail SLO `ok=false` for 2 consecutive monitor windows
- `stale_in_progress_45m > 0`
- unhealthy critical containers
- `failure_rate_10m_pct` spikes above agreed threshold

Rollback actions:

1. Set `NIGHTLY_DISTILL_FORCE_MODE=normal`.
2. Reduce distillation rounds (`NIGHTLY_DISTILL_MAX_ROUNDS`) if needed.
3. Re-run preflight guard and capture a fresh audit report.

## 2) Verification gates

## Smoke gate (15-30 minutes)

- Containers healthy for full window.
- Queue stable: no stale in-progress tasks.
- Tail trend non-worsening (`eligible_now` does not rise continuously).
- Contract enforce remains active.

## Sustained gate (24 hours)

- Runtime monitor summary exists and reports:
  - sustained tail SLO `ok=true`
  - `max_consecutive_high_watermark_breach` below threshold
  - `above_target_ratio` within threshold
- No recurring stale queue incidents.
- Error rate remains within operational budget.

## 3) Evidence outputs

- `docs/audits/<date>-runtime-gate*.jsonl`
- `docs/audits/<date>-runtime-gate*-summary.md`
- preflight JSON report with gate summary
- optional boot incident report for host stability context:
  - `docs/audits/boot_incidents/latest.json`

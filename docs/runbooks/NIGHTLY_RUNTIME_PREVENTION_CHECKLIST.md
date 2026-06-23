# Nightly Runtime Prevention Checklist

Goal: prevent repeats of auth drift, crash-loops, and silent alert loss.

## Before Nightly (T-10 min)

- Run preflight guard:
  - `python3 scripts/preflight_runtime_guard.py --strict --output docs/audits/preflight-runtime-$(date +%F-%H%M).json`
- Gate criteria (must be green):
  - `secret_drift_ok=true`
  - `syntax_ok=true`
  - `containers_ok=true`
  - `contract_enforce_ok=true`
  - `synthetic_alerts_ok=true` (Telegram or ntfy; Telegram can be false only if ntfy=true and known proxy issue is open)
  - `evolution_health_ok=true` (if `limactl` is unavailable, fallback must be detected)
  - `distillation_snapshot_ok=true`
  - `stale_in_progress_45m=0`

## During Nightly (every 30 min)

- Run sustained KPI monitor (shadow/enforce evidence):
  - `python3 scripts/runtime_kpi_gate_monitor.py --duration-hours 0.5 --interval-sec 300 --tag nightly-tail-check --distill-target 8 --distill-high-watermark 12 --distill-consecutive-breach 2`
- Queue and stale:
  - `pending/in_progress` must not grow monotonically for 2 consecutive checks.
  - `stale_in_progress_45m=0`
- Throughput and errors:
  - `completed_10m >= 1` (for active windows with real load)
  - `error_rate_10m <= 0.10`
- Distillation and mutation:
  - `campaign_done` should be monotonic non-decreasing.
  - `eligible_now` should not grow for 2 consecutive windows during active distillation.
  - sustained tail SLO: no `distillation_tail_violation` in 15m and 1h windows.
  - If `evolution_degraded_mode=true`, open infra task to restore hardware isolation (`limactl`/microVM path).
- Health:
  - `docker ps` must show critical containers `Up` and not `unhealthy`.

### Distillation control knobs (safe defaults)

- Nightly drain:
  - `NIGHTLY_DISTILL_TARGET_ELIGIBLE=5`
  - `NIGHTLY_DISTILL_MAX_ROUNDS=6`
  - `NIGHTLY_DISTILL_TURBO_HIGH_WATERMARK=12`
  - `NIGHTLY_DISTILL_TURBO_MAX_ROUNDS=10`
- Ingest backpressure (non-critical bulk knowledge only):
  - `KNOWLEDGE_INGEST_BACKPRESSURE_ENABLED=true`
  - `KNOWLEDGE_INGEST_HIGH_WATERMARK=24`
  - `KNOWLEDGE_INGEST_FORCE_ALLOW=false`

## After Nightly (T+5 min)

- Re-run preflight:
  - `python3 scripts/preflight_runtime_guard.py --output docs/audits/post-nightly-runtime-$(date +%F-%H%M).json`
- Compare pre vs post:
  - no new secret drift
  - no new syntax failures
  - no increase in stale tasks
  - no regression in `campaign_done`
  - no unexplained growth in `eligible_now`
  - alert channel still alive (at least ntfy)

## Incident Actions (fast path)

1. **SASL auth failures**
   - Check `knowledge_os/.env` `POSTGRES_PASSWORD`.
   - Check `knowledge_os/pgbouncer/userlist.txt` admin password.
   - Redeploy: `docker compose --env-file knowledge_os/.env -f knowledge_os/docker-compose.yml up -d`.

2. **Crash-loop / syntax**
   - Compile critical files:
     - `python3 -m py_compile knowledge_os/app/smart_worker_autonomous.py`
   - Fix syntax before container restart.

3. **Telegram silent / malformed**
   - Keep ntfy fallback enabled.
   - Verify env on `telegram-notifications`: `TELEGRAM_BOT_TOKEN`, `CHAT_ID`, `NTFY_URL`, `TG_PROXY`.
   - Run synthetic check from preflight script.

4. **Mutation sandbox degraded**
   - If preflight shows `evolution_degraded_mode=true`, verify logs include fallback marker and no cycle stop.
   - Prioritize restoration of `limactl`/microVM runtime for stronger isolation.
   - Keep degraded mode allowed only as temporary guardrail with explicit expiry in incident ticket.

5. **Distillation tail keeps growing**
   - Confirm runtime monitor summary in `docs/audits/*nightly-tail-check-summary.md`.
   - If tail pressure persists, first increase drain capacity (`NIGHTLY_DISTILL_TURBO_MAX_ROUNDS`), then only if needed temporarily force ingest allow/deny via:
     - Freeze bulk ingest: keep `KNOWLEDGE_INGEST_BACKPRESSURE_ENABLED=true` and lower `KNOWLEDGE_INGEST_HIGH_WATERMARK`.
     - Emergency bypass (rollback): `KNOWLEDGE_INGEST_FORCE_ALLOW=true`.
   - After stabilization, return knobs to defaults and record postmortem.

## Governance Notes (world practices)

- First Principles: solve root cause (credentials and syntax gates), not symptoms (manual restarts only).
- Five Whys: record "why chain" in incident report for every red preflight.
- Pre-mortem: before config change, list 3 failure modes and explicit rollback.
- KISS/Occam: healthchecks should rely on tools guaranteed in image (Python runtime), not optional binaries.
- Strong Opinions, Weakly Held: keep strict gates by default; relax only with measured evidence and expiry date.

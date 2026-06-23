# MLX Runtime Risk Register (Mac Studio)

Scope: local MLX serving path (`com.atra.mlx-api-server`, `com.atra.mlx-monitor`) and related Python runtime stability.

Status baseline:

- Safe default: `MLX_MAX_CONCURRENT=1`
- Speculative decoding: `MLX_SPECULATIVE_DECODING=false`
- Crash detector: `com.atra.python-crash-detector` enabled

## Risk Register

### R1: GPU/Metal abort under load

- **Signal:** new `Python*.ips` with coalition `com.atra.mlx-*` and stack containing `mlx::core::gpu::check_error`.
- **Likelihood:** medium (rises when concurrency/speculative is increased).
- **Impact:** high (process crash, request failures, instability loops).
- **Mitigation:** keep `MLX_MAX_CONCURRENT=1`, conservative preload, soak before tuning.
- **Rollback trigger:** first confirmed recurring abort in 24h window.
- **Rollback action:** force safe profile (`MLX_MAX_CONCURRENT=1`, `MLX_SPECULATIVE_DECODING=false`), restart launch agent.

### R2: Launchd/TCC path denial (`Operation not permitted`)

- **Signal:** monitor/autostart logs show `Operation not permitted` when calling scripts from `Documents`.
- **Likelihood:** medium (macOS privacy controls).
- **Impact:** high (auto-recovery path silently degrades).
- **Mitigation:** run monitor scripts from `~/Library/Application Support/Atra`.
- **Rollback trigger:** any recurrent TCC denial in monitor/error logs.
- **Rollback action:** re-bootstrap launch agents to Application Support runtime path only.

### R3: Port ownership race (`address already in use`)

- **Signal:** uvicorn bind errors on `:11435`, repeated kickstart/restart attempts.
- **Likelihood:** medium.
- **Impact:** medium/high (service unavailable despite restarts).
- **Mitigation:** single launch owner policy (`launchctl` only), avoid mixed manual + launchd starts.
- **Rollback trigger:** >=2 bind collisions in 15 minutes.
- **Rollback action:** stop rogue processes, hard restart launch agent, validate `/health`.

### R4: Latency regression due to safe mode

- **Signal:** sustained timeout growth or user-visible slowdown while crash-free.
- **Likelihood:** medium.
- **Impact:** medium (degraded UX, no data loss).
- **Mitigation:** controlled canary of speculative mode after clean soak window.
- **Rollback trigger:** timeouts/error budget breach during canary.
- **Rollback action:** revert canary flags immediately, continue safe profile.

### R5: Alert blind spot (crash happened, no notification)

- **Signal:** new MLX coalition `.ips` exists but no detector report/notification.
- **Likelihood:** low/medium.
- **Impact:** high (late incident response).
- **Mitigation:** detector stateful scans every 60s + local report persistence.
- **Rollback trigger:** any missed incident in audit sample.
- **Rollback action:** reinstall detector agent, reset detector state carefully, validate with forced latest scan.

## Change Policy (Strong Opinions, Weakly Held)

- Default posture: **stability first**.
- Any performance tuning above safe defaults must pass:
  - 24h soak without new MLX-coalition crash reports,
  - health endpoint stability,
  - no restart-loop symptoms.
- If facts contradict assumptions, immediately return to safe profile and reopen RCA.

## Verification Checklist

- `launchctl print gui/$(id -u)/com.atra.mlx-api-server` shows running.
- `launchctl print gui/$(id -u)/com.atra.mlx-monitor` shows running.
- `launchctl print gui/$(id -u)/com.atra.python-crash-detector` shows periodic successful runs.
- `curl http://localhost:11435/health` returns healthy.
- no new `Python*.ips` with `com.atra.mlx-*` in target window.

## Incident Ownership Matrix (RACI)

Scope: MLX runtime incidents (crash, restart loop, health degradation, detector miss).

- **Victoria (Team Lead)** - **A** (Accountable): incident command, prioritization, final decision on rollback/forward.
- **Elena (Monitor)** - **R** (Responsible): first response, alert triage, crash evidence collection.
- **Sergey (DevOps)** - **R** (Responsible): runtime recovery (`launchd`, process ownership, restart policy).
- **Igor (Backend)** - **R/C**: app-level bug fix when root cause is in service code path.
- **Roman (DB)** - **C**: queue/DB-related bottleneck checks affecting throughput and stale work.
- **Olga (Performance)** - **C**: concurrency/latency pressure analysis and safe tuning guidance.
- **Anna (QA)** - **C/R**: post-incident verification and regression gate before declaring stable.
- **Alexey (Security)** - **C**: suspicious access patterns, tampering, credential/exposure checks.

RACI legend: **R** = Responsible, **A** = Accountable, **C** = Consulted.

## Escalation SLO (5/15/30)

- **T+5 min (Detect & Triage):**
  - incident acknowledged;
  - owner assigned (Elena -> Sergey/Victoria);
  - first evidence snapshot collected (`.ips`, launchctl status, `/health`).
- **T+15 min (Mitigate):**
  - safe profile enforced if instability persists;
  - service reachable (`/health`), restart loop stopped.
- **T+30 min (Stabilize):**
  - error rate returns to baseline trend;
  - no new recurring abort signatures;
  - decision logged: continue observe vs full rollback.

## Anti-Forget Checklist (Do Not Skip)

- Confirm incident ticket/note has owner and UTC timestamps.
- Attach crash signature and coalition details from latest `.ips`.
- Record exact config at incident time (`MLX_MAX_CONCURRENT`, `MLX_SPECULATIVE_DECODING`).
- Record command/evidence for each action taken (restart, rollback, verification).
- Run post-incident verification checklist before "resolved" status.
- If root cause is unclear, mark as provisional fix and schedule RCA follow-up.

## Incident Report Template (1-Page)

Use this template for every MLX runtime incident.

```markdown
# MLX Incident Report

## 1) Incident Header

- Incident ID:
- Start time (UTC):
- End time (UTC):
- Duration:
- Severity (SEV-1/2/3):
- Incident Commander (A):
- Responders (R):

## 2) Symptoms and Detection

- Primary symptom (crash/restart-loop/latency/degraded health):
- Detection source (crash detector/monitor/manual):
- First alert timestamp (UTC):
- Affected services (`mlx-api-server`, `mlx-monitor`, other):

## 3) Facts Snapshot (No assumptions)

- `launchctl` status summary:
- `/health` summary (`active_requests`, status):
- Latest `Python*.ips` coalition/signature:
- Runtime flags at incident time:
  - `MLX_MAX_CONCURRENT=`
  - `MLX_SPECULATIVE_DECODING=`

## 4) Five Whys (Root Cause Track)

1. Why did impact happen?
2. Why was this condition present?
3. Why was it not prevented?
4. Why was it not detected earlier?
5. Why did safeguards not fully contain it?

## 5) Mitigation and Rollback

- Immediate actions taken (with UTC timestamps):
- Was safe profile enforced? (yes/no)
- Rollback decision and trigger:
- Recovery confirmation:

## 6) Validation (Quality Gate)

- Queue: `pending=`, `in_progress=`
- Throughput (req/min or jobs/min):
- Stale-task count:
- Contract enforce checks:
- Container/agent health status:
- Error rate trend:

## 7) Pre-mortem Follow-up (3 future failure modes)

- FM1:
- FM2:
- FM3:

## 8) Action Items

- [ ] Owner / deadline / change
- [ ] Owner / deadline / change
- [ ] Owner / deadline / change
```

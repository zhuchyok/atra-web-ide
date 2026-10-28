# Harness Checklist (12 Components)

Date: 2026-10-28  
Scope: ATRA runtime harness around Victoria/experts (orchestration, memory, tools, safety, reliability).  
Method: code + live runtime signals (queue, disk, watchdog, task metadata).

## Current runtime snapshot

- Queue: `in_progress=3`, `pending=0`, `queued=0` (operational tail, no pending backlog).
- Disk: ~`296 GiB` free on `/` (~`4%` capacity shown by APFS mount view, container free ~12.9%).
- Disk root-cause already confirmed: Cursor state DB growth (`state.vscdb` ~73 GiB).

## 12 components status

1. **Orchestration loop** — **OK / Medium Risk**

- Evidence: central task orchestration + dispatch/requeue logic in `knowledge_os/app/enhanced_orchestrator.py`.
- Risk: high policy complexity in metadata-driven transitions can drift without periodic audits.

2. **Tools layer** — **OK**

- Evidence: dedicated worker streams and overflow routing in `knowledge_os/app/expert_stream_routing.py`; launchd/script tooling operational.
- Risk: low; main failure mode is wrong stream targeting (already guarded by overflow routing).

3. **Memory architecture** — **At Risk (High)**

- Evidence: multi-layer memory present (`semantic_cache`, knowledge context, crystals), but operationally `state.vscdb` growth shows memory/state pressure in the IDE layer.
- Risk: context/memory bloat causes latency variance and disk churn.

4. **Context management** — **Improving / Medium Risk**

- Evidence: operational-query gating and selective crystal injection in `knowledge_os/app/ai_pipeline.py`; deep context retrieval path in `ai_core.py`.
- Risk: long-tail prompts still degrade under heavy context payloads.

5. **Prompt construction** — **OK**

- Evidence: staged prompt preparation pipeline in `knowledge_os/app/ai_pipeline.py` (threat checks, anti-hallucination, optional memory crystals, enrichment).

6. **Output parsing** — **OK (recently hardened)**

- Evidence: regression tests for truncation repair and parse fallback in `knowledge_os/tests/test_react_json_truncation_guards.py`.
- Risk: low after recent JSON truncation guards.

7. **State management** — **Improving / Medium Risk**

- Evidence: persistent task metadata contract + dispatch attempt counters in `enhanced_orchestrator.py`; alert-state dedup in `scripts/launchd_watchdog.py`.
- Risk: metadata schema growth may need periodic cleanup/normalization.

8. **Error handling / retries** — **OK**

- Evidence: adaptive timeouts, exponential backoff, requeue on stub/no-text in `knowledge_os/app/expert_worker.py`; DB connect retries in responders/watchdogs.
- Risk: moderate only during heavy concurrent outages (expected retry storms).

9. **Guardrails & safety** — **OK**

- Evidence: security responder dedup/rate-limit + consolidated task strategy in `scripts/security_incident_responder.py`; watchdog guardrails in `scripts/launchd_watchdog.py`.

10. **Verification loops** — **OK / Medium Risk**

- Evidence: judge-gate path in `expert_worker.py`, watchdog canaries (hands/brain/encode) in `launchd_watchdog.py`.
- Risk: judge quality depends on runtime capacity and can go fail-open by design.

11. **Subagent orchestration** — **OK**

- Evidence: overflow/dedicated stream partitioning + worker specialization (`expert_stream_routing.py`, worker pool topology).
- Risk: low-medium under saturation; mostly capacity-bound, not logic-bound.

12. **Operational observability** — **Improving**

- Evidence: launchd watchdog state, canaries, deduped incident tasks, cursor DB growth monitor + safe cleanup in `scripts/launchd_watchdog.py`.
- Remaining gap: daily growth report for top disk consumers is not yet automated.

## Prioritized next actions

1. Add daily top-growers report (`state.vscdb`, Docker.raw physical usage, ollama blobs, repo backups) with deltas/24h.
2. Add hard threshold for Cursor growth trend alert (already tracked) + explicit escalation when growth > X GiB/day for 2 consecutive windows.
3. Add monthly metadata hygiene job for tasks table fields that accumulate transient retry/dispatch state.
4. Keep launchd watchdog disk threshold env-tunable; review after 7-day trend.

## Verdict

Harness is functional and resilient for current load, with the main residual risk concentrated in memory/state growth (especially Cursor-side state DB), not in core model routing or worker execution logic.

## AI-Native Map: 10 concrete changes (priority)

1. **Disk top-growers loop (24h deltas)** — **DONE**

- Implemented in `scripts/launchd_watchdog.py` (`_disk_growth_watch`).
- Output: `logs/disk_growth_report.log`.

2. **Cursor state DB growth guard + soft cleanup** — **DONE**

- Implemented in `scripts/launchd_watchdog.py` (`_cursor_size_watch`).
- Cleans old Cursor logs/snapshots and alerts on DB size/growth thresholds.

3. **Security incident consolidation without hourly task spam** — **DONE**

- Implemented in `scripts/security_incident_responder.py`.
- Behavior: update open consolidated task (`updated_open`) instead of creating duplicates.

4. **Launchd watchdog dedup and duplicate-task prevention** — **DONE**

- Implemented in `scripts/launchd_watchdog.py` (`problem_key`, open-task check in `create_task`).

5. **Watchdog scripts fail-soft instead of log-storm** — **DONE**

- Implemented in `scripts/docker_task_watchdog.sh` (PATH guard, docker availability checks, safe skip).

6. **DB flaps hardening for operational daemons** — **DONE**

- Implemented retries/backoff in responders/watchdogs (`security_incident_responder.py`, `launchd_watchdog.py`).

7. **Queue hygiene for stale synthetic tails** — **DONE**

- Implemented in `scripts/launchd_watchdog.py` (`_auto_close_stale_internal_tails`) with source/age policy.

8. **Prompt/context noise gating for operational tasks** — **DONE (phase 1)**

- Expanded env-driven operational categories/markers in `knowledge_os/app/ai_pipeline.py`.
- Effect: memory crystals are skipped more reliably for incident/monitoring-like prompts.

9. **Verification loop strengthening (judge + deterministic checks)** — **PARTIAL**

- Judge gate exists in `knowledge_os/app/expert_worker.py`.
- Next: enforce compact deterministic post-check set for key task classes before completion.

10. **Metadata lifecycle hygiene (monthly compaction/audit)** — **DONE (baseline)**

- Implemented in `scripts/launchd_watchdog.py` (`_metadata_hygiene`).
- First run compacted transient metadata on terminal tasks (thousands of rows).

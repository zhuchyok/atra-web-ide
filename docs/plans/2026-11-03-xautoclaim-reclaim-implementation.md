# XAUTOCLAIM reclaim Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Idle PEL messages from a dead consumer are claimed and processed; they are not ACK-failed in the same loop. Live long tasks stay in PEL until result, then ACK.

**Architecture:** Pure `stream_reclaim.classify_pending` decides zombie / reclaim / keep. `expert_worker` already calls `xautoclaim`; stop STALE-DROP of reclaim+inflight IDs. ACK after `process_task`, with an in-flight set so `xreadgroup("0")` does not double-run. Heartbeat hash `runtime:expert_heartbeats` protects live consumers.

**Tech Stack:** Python 3, Redis streams, pytest. No new orchestrator.

## Global Constraints

- Не заменять expert streams. Не ставить CrewAI/LangGraph.
- Не поднимать TTC 420. Не трогать pin ctx / pool / mem Анны.
- Коммит только если пользователь попросил.
- XAUTOCLAIM уже есть (`redis_manager.autoclaim_tasks`). Не дублировать вызов без нужды.
- TDD: красный тест → код → зелёный.

---

## File map

- Create: `knowledge_os/app/stream_reclaim.py`
- Create: `knowledge_os/tests/test_stream_reclaim.py`
- Modify: `knowledge_os/app/expert_worker.py` (classify before STALE-DROP; inflight; xack after process)
- Modify: `docs/MASTER_REFERENCE.md` + `docs/CHANGES_FROM_OTHER_CHATS.md` § v150.81

---

### Task 1: classify pending

- [x] Tests: live consumer idle 10min → keep; dead/missing + idle 6min → reclaim; deliveries>10 → zombie; inflight id → keep even if idle.
- [x] `live_consumers_from_hash` reads `{consumer, ts}` JSON; ttl 90s.
- [x] pytest green.

### Task 2: wire worker

- [x] After `xpending_range`, classify with heartbeats + `_inflight_msg_ids`.
- [x] Phase 1 zombies unchanged (ack + DB failed).
- [x] Phase 2/3b reclaim only `classes["reclaim"]`.
- [x] STALE-DROP only zombies already handled — do not ack reclaim/keep/inflight.
- [x] `_run_task`: add inflight, `process_task`, `finally` xack + discard inflight. No early-xack before process.
- [x] `pending_mine` skip inflight ids.

### Task 3: bible + verify

- [x] § v150.81
- [x] pytest `test_stream_reclaim.py`
- [x] Restart expert workers (knowledge_os mount, no hot-reload)

---

## Pre-mortem

1. Delayed xack + 5min autoclaim duplicates long tasks. Heartbeat-live consumer → keep, not reclaim.
2. Empty heartbeat hash. Idle-only reclaim (same as today), no protect.
3. STALE-DROP still fails claimed ids. Tests lock protect/inflight ≠ drop.

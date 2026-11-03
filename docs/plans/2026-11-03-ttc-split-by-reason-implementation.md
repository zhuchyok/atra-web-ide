# TTC split by handoff_reason Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Rolling TTC p95 stays one number for alert 420, and `/metrics` also shows p95 per `handoff_reason`.

**Architecture:** Redis list stores JSON `{d,r}` instead of a bare float. Parser accepts old bare floats as `unknown`. Small module `async_ttc.py` owns encode/parse/group. Victoria server only calls it. Alert expr unchanged.

**Tech Stack:** Python 3, Redis list `victoria:async_ttc_samples`, Prometheus gauges, pytest.

## Global Constraints

- Не поднимать TTC 420. Не фильтровать `timeout_*` из overall p95.
- Не ставить OpenTelemetry SDK / llm-otel-kit / CrewAI.
- Мозг 11434 qwen38 16384; руки 11437 phi 8192 + nomic.
- Коммит только если пользователь попросил.
- TDD: красный тест → код → зелёный.

---

## File map

- Create: `src/agents/bridge/async_ttc.py`
- Create: `knowledge_os/tests/test_async_ttc_samples.py`
- Modify: `src/agents/bridge/victoria_server.py` (`_record_async_ttc`, `_push_ttc_sample`, `_async_sla_snapshot`, `/metrics`)
- Modify: `src/agents/bridge/task_detector.py` `format_live_fact_answer`
- Modify: `knowledge_os/tests/test_fact_seeking_route.py`
- Modify: `docs/MASTER_REFERENCE.md` + `docs/CHANGES_FROM_OTHER_CHATS.md` § v150.80

---

### Task 1: encode/parse/group

**Files:** `src/agents/bridge/async_ttc.py`, `knowledge_os/tests/test_async_ttc_samples.py`

- [x] Failing tests: bare `"12.5"` → (12.5, `"unknown"`); JSON `{"d":12.5,"r":"timeout_watchdog"}`; extra `num_ctx` analog — reason cannot be empty; group p95.
- [x] Implement `encode_ttc_sample`, `parse_ttc_sample`, `ttc_by_reason`, `sanitize_reason`.
- [x] pytest green.

### Task 2: Redis + snapshot

- [x] `_async_ttc_samples` becomes `list[tuple[float,str]]`.
- [x] `_push_ttc_sample(duration, reason)`.
- [x] Snapshot: overall durations + `by_reason`.
- [x] `/metrics`: unlabeled p95 unchanged; add `victoria_async_ttc_p95_by_reason_seconds{handoff_reason="..."}` and `victoria_async_ttc_samples_by_reason`.

### Task 3: live-fact line

- [x] `format_live_fact_answer` appends `by_reason=timeout_watchdog:p95=480/n=3` when present.
- [x] Existing `p50=11.5 p95=27.3 samples=4 inflight_max=0.0 inflight=0` still exact if no by_reason.

### Task 4: bible + verify

- [x] § v150.80
- [x] pytest listed files
- [x] curl `/metrics` after victoria-agent restart (if mounted)

---

## Pre-mortem

1. Old Redis floats ignored → empty p95. Parser must accept bare float.
2. Reason with spaces/quotes breaks Prometheus. `sanitize_reason`: `[a-zA-Z0-9_:-]`, else `unknown`.
3. Cardinality explosion. Cap 16 distinct reasons in one snapshot; rest `other`.

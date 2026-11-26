# Implementation plan: Wave 2 MCP approve + real FS

Date: 2026-11-22  
Depends on: Wave 1 closed (sync_safe explain ~2s)

## Goal

Stop lying that `victoria_execute_plan` wrote files. Real workspace-scoped FS; mutate only with explicit approve.

## Steps

1. Local FS helper: resolve path under `workspace_path`, refuse escape.
2. `victoria_execute_plan(..., approve_writes: bool = False)`:
   - `read_file` → real read (cap bytes)
   - `edit` / `run` → if not approve_writes: status `needs_approve` + preview; if approve: write/run with command allowlist
3. Unit tests for sandbox + approve gate
4. Doc one-liner in roadmap Wave 2 evidence

## Out of scope

- Full MCP CallMcpTool bridge to user-filesystem
- SSE progress
- Raising TTC / day 120B

## Done when

- Fake `[Изменён файл]` gone for edit without approve ✅ (`needs_approve`)
- Read returns real content snippet ✅
- pytest green ✅ (`test_wave2_execute_plan_local.py` 4/4); OWUI still ENABLE_OLLAMA_API=false

## Landed

- `src/agents/bridge/execution_plan_local.py`
- `victoria_execute_plan(..., approve_writes=False)` wired to local executor

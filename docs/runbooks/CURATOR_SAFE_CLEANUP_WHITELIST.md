# Curator Safe Cleanup Whitelist

Date: 2026-06-10  
Mode: Safety-first (no automatic deletion).

## Goal

Avoid removing anything important while cleaning a dirty tree.  
This runbook defines what is explicitly in-scope for the curator hardening task and what must be reviewed manually.

## Hard Rule

- Do not delete files automatically.
- Do not use broad cleanup commands (`git clean`, mass deletes).
- Only review files with an explicit whitelist decision.

## Keep (in-scope, required)

- `scripts/curator_send_tasks_to_victoria.py`
- `tests/test_curator_task_loading_and_quality_gate.py`
- `docs/runbooks/CURATOR_BASELINE_ROUTE_CONTRACT.md`
- `docs/curator_reports/FINDINGS_2026-06-09_curator_hardening.md`

## Keep as operational fixtures (optional, safe to archive later)

- `scripts/curator_tasks_dashboard_overview_atomic.txt`
- `scripts/curator_tasks_dashboard_reaudit_one_tab.txt`
- `scripts/curator_tasks_dashboard_reaudit_split_by_tabs.txt`
- `scripts/curator_tasks_dashboard_reaudit_split_retry_30m.txt`
- `scripts/curator_tasks_dashboard_full_reaudit.txt`
- `scripts/curator_tasks_dashboard_full_reaudit_retry_strict.txt`
- `scripts/curator_tasks_dashboard_finish_full_single_goal.txt`

## Manual review required (out-of-scope for automatic cleanup)

- Any file outside the two groups above.
- Large generated or unrelated changes in `.cursor/rules/`, `knowledge_os/`, `backend/`, `docs/audits/`, and other broad areas.

## Safe Procedure

1. Verify health and queue before any cleanup decision.
2. Freeze whitelist files listed above.
3. For every non-whitelist file: require explicit owner decision (`keep`, `archive`, `revert`).
4. Re-run quick canary after any manual cleanup batch.

## Stop Conditions

- Unknown file ownership.
- Missing test evidence.
- Any regression in queue (`pending/in_progress`) or health checks.

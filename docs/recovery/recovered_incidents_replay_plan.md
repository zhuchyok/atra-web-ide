# Recovered Incidents Replay Plan

## Goal

Replay validated high-confidence historical incidents into `knowledge_nodes` with:

- strict source attribution;
- idempotent insertion (no duplicate replay);
- rollback-safe artifacts per run.

## Input and Scope

- Source file: `docs/recovery/recovered_incidents_validated.jsonl`
- Baseline filter: `confidence >= high`
- Replay unit: one `knowledge_nodes` row per validated incident

## Safety Controls

1. **Idempotency by source hash**
   - For each record, `recovery_source_hash = sha256(ts|incident_class|severity|summary|evidence_ref)`.
   - Before insert, script checks existing `knowledge_nodes.metadata.recovery_source_hash`.
   - Existing records are skipped.

2. **Source attribution in metadata**
   - `type = recovery_incident`
   - `source = recovered_incidents_validated`
   - `recovery_run_id`, `recovery_source_hash`, `incident_*`, `evidence_ref`, `summary`

3. **Rollback artifacts**
   - `docs/recovery/replay_runs/<run_id>_inserted.jsonl`
   - `docs/recovery/replay_runs/<run_id>_failed.jsonl`
   - `docs/recovery/replay_runs/<run_id>_rollback.sql`

## Execution Procedure

1. Dry-run:
   - `python3 scripts/replay_recovered_incidents.py`
2. Apply:
   - `python3 scripts/replay_recovered_incidents.py --apply`
3. Validate:
   - verify inserted count and failed count from output JSON;
   - verify rows in DB by `metadata->>'type' = 'recovery_incident'`;
   - spot-check random rows against `evidence_ref`.

## Expected Outcome

- Historical high-confidence incidents become queryable through normal RAG paths.
- Replay can be re-run safely without duplicate growth.
- Any run can be reverted using generated SQL rollback file.

# Recovery Workspace

This directory tracks post-incident knowledge reconstruction after Docker volume loss.

## Files

- `LOSS_LEDGER_2026-05-10_to_2026-07-13.md`  
  Human-readable ledger: confirmed recovery scope, likely losses, recoverability limits, and acceptance criteria.

- `recovery_manifest.jsonl`  
  Machine inventory of evidence sources (local backups, audits, summaries, transcript matches).

- `loss_window_timeline.jsonl`  
  Chronological reconstruction scaffold generated from manifest sources.

## Current Scope

- Backup baseline: `knowledge_postgres_2026-05-10_03-00-00.dump`
- Incident window: 2026-05-10 -> 2026-07-13
- Gap size: ~64 days

## Next Reconstruction Steps

1. Filter timeline to `entity_type in {audit_summary, transcript_parent}` and tag high-impact incidents.
2. Build `recovered_incidents.jsonl` with explicit confidence and evidence references.
3. Replay validated records into knowledge nodes and run KPI verification.

## Key Parent Transcript Seeds

- [DB restore incident thread](e0481aed-70f6-4c97-97f1-a299e3f049c8)
- [Infra recovery notes](20dc9ec8-59e7-41d6-bcda-76b875ca6d05)
- [Backup/restore follow-up](989338fc-6492-4a33-8248-77f98e4dba78)

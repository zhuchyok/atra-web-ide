# Recovery Executive Summary

## Scope

- Loss window baseline: `2026-05-10_03-00-00.dump`
- Incident boundary: `2026-07-13` (Docker volume loss)
- Approximate gap: `64 days`

## Reconstruction Artifacts

- `recovery_manifest.jsonl`: 330 evidence records
- `loss_window_timeline.jsonl`: 330 timeline events
- `recovered_incidents_validated.jsonl`: 87 validated incident records

## Validated Incident Distribution

- By class:
- `audit_event`: 2
- `backup_restore`: 3
- `learning_pipeline`: 4
- `runtime_kpi`: 76
- `timeout_reliability`: 2

- By severity:
- `critical`: 3
- `high`: 12
- `medium`: 72

- By confidence:
- `high`: 87

## Practical Recoverability Estimate

- High-confidence operational context recovery: **85-95%**
- Medium-confidence task chronology recovery in loss window: **70-85%**
- Full byte-level historical parity: **not achievable** without missing primary state

## Next Best-of-Breed Steps

1. Enrich `recovered_incidents_validated.jsonl` with entity IDs (task_id, stream, component) where available.
2. Create `recovery_conflict_report.md` for contradictory evidence records.
3. Replay high-confidence records into knowledge nodes with source attribution tags.
4. Run spot validation (>=50 records) and publish confidence-adjusted final report.

# Irrecoverable Gaps (Current Assessment)

## Fully Irrecoverable Without Primary Data

- Exact Redis ephemeral state snapshots (pending/consumer offsets/delivery counters) for arbitrary historical timestamps in the loss window.
- DB rows that were never included in a backup and were never mirrored in audit logs or transcripts.
- Exact per-second runtime ordering of worker retries/reclaims when only aggregate KPI evidence exists.

## Partially Recoverable (Medium Confidence)

- Task-level chronology inside the 64-day gap where only transcript narrative exists.
- Intermediate mutation artifacts not persisted to git/docs but referenced in conversations.
- Fine-grained causality between transient outages and specific queue transitions.

## Recoverable (High Confidence)

- Major incidents, restore decisions, runtime policy changes, and KPI outcomes backed by audit files.
- Post-incident remediation timeline with evidence links.
- Backup lineage and restore checkpoints.

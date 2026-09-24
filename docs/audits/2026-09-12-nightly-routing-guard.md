# Nightly Routing Guard

- ts_utc: `2026-09-12T21:23:39.784794+00:00`
- mode: `apply`
- action: `canary_only`
- reason: `insufficient_events:12<100`

## Metrics
- events_total_window: `12`
- routing_win_rate: `1.0`
- decision_regret_rate: `0.0`
- latency_p95_ms: `464990.55`

## Thresholds
- min_events: `100`
- target_win_rate: `0.9`
- min_win_rate_rollback: `0.8`
- target_regret_rate: `0.15`
- max_regret_rate_rollback: `0.25`
- max_p95_ms: `20000.0`
- max_p95_ms_rollback: `35000.0`

## Apply Result
- applied: `True`
- `SET system:contract_rollout_mode shadow`
- `SET system:contract_enforce 0`
- `SET system:routing_guard:last_action canary_only`
- `SET system:routing_guard:last_reason insufficient_events:12<100`
- `SET system:routing_guard:last_ts_utc 2026-09-12T21:23:40.052755+00:00`

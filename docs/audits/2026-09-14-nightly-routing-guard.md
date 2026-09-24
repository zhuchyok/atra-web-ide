# Nightly Routing Guard

- ts_utc: `2026-09-14T05:53:17.145808+00:00`
- mode: `apply`
- action: `canary_only`
- reason: `insufficient_events:78<100`

## Metrics
- events_total_window: `78`
- routing_win_rate: `1.0`
- decision_regret_rate: `0.0`
- latency_p95_ms: `48060.46`

## Thresholds
- min_events: `100`
- target_win_rate: `0.9`
- min_win_rate_rollback: `0.8`
- target_regret_rate: `0.15`
- max_regret_rate_rollback: `0.25`
- max_p95_ms: `450000.0`
- max_p95_ms_rollback: `600000.0`

## Apply Result
- applied: `True`
- `SET system:contract_rollout_mode shadow`
- `SET system:contract_enforce 0`
- `SET system:routing_guard:last_action canary_only`
- `SET system:routing_guard:last_reason insufficient_events:78<100`
- `SET system:routing_guard:last_ts_utc 2026-09-14T05:53:17.364769+00:00`

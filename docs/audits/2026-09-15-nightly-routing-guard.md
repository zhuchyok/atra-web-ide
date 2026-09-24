# Nightly Routing Guard

- ts_utc: `2026-09-15T15:41:37.399480+00:00`
- mode: `apply`
- action: `rollout`
- reason: `ok`

## Metrics
- events_total_window: `313`
- routing_win_rate: `1.0`
- decision_regret_rate: `0.0`
- latency_p95_ms: `233273.67`

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
- `SET system:contract_rollout_mode enforce`
- `SET system:contract_enforce 1`
- `SET system:routing_guard:last_action rollout`
- `SET system:routing_guard:last_reason ok`
- `SET system:routing_guard:last_ts_utc 2026-09-15T15:41:37.711620+00:00`

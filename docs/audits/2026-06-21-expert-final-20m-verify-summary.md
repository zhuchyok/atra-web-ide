# Runtime KPI Gate Monitor

- started_at_utc: `2026-06-21T20:11:34.393575+00:00`
- last_sample_utc: `2026-06-21T20:30:20.447146+00:00`
- samples_collected: `19`

## Latest Snapshot

- pending: `0`
- in_progress: `3`
- completed_10m: `0`
- failed_10m: `3`
- failure_rate_10m_pct: `100.0`
- completed_10m_gate: `0`
- failed_10m_gate: `2`
- failure_rate_10m_gate_pct: `100.0`
- stale_in_progress: `0` (threshold `45m`)
- eligible_now: `0`
- campaign_done: `1513`
- campaign_in_progress: `0`
- contract_rollout_mode: `enforce`
- contract_enforce: `1`
- dynamic_alert_count: `0`
- dynamic_mounts_denied_count: `0`
- dynamic_no_slot_available_count: `0`
- dynamic_failed_nonzero_rc_count: `0`
- dynamic_slot_running: `0` / `0`

## Gate Results

- 15m: pass=`False` active=`False` reason=`error_rate_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`1` samples=`15` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`4` max_in_progress=`3` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`0` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0` error_rate_gate_ok=`False` max_failure_rate_10m_gate_pct=`100.00`
- 1h: pass=`False` active=`False` reason=`error_rate_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`1` samples=`19` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`4` max_in_progress=`3` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`0` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0` error_rate_gate_ok=`False` max_failure_rate_10m_gate_pct=`100.00`
- 6h: pass=`False` active=`False` reason=`error_rate_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`6` samples=`19` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`4` max_in_progress=`3` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`0` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0` error_rate_gate_ok=`False` max_failure_rate_10m_gate_pct=`100.00`
- 24h: pass=`False` active=`False` reason=`error_rate_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`24` samples=`19` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`4` max_in_progress=`3` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`0` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0` error_rate_gate_ok=`False` max_failure_rate_10m_gate_pct=`100.00`

## Sustained Distillation Tail SLO

- ok: `True`
- reason: `ok`
- sample_count: `19`
- min_samples_required: `12`
- max_consecutive_high_watermark_breach: `0` (allowed `< 3`)
- above_target_ratio: `0.0` (allowed `<= 0.35`)
- latest_eligible_now: `0`

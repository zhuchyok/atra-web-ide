# Runtime KPI Gate Monitor

- started_at_utc: `2026-06-22T21:33:54.829504+00:00`
- last_sample_utc: `2026-06-22T21:35:06.293239+00:00`
- samples_collected: `12`

## Latest Snapshot

- pending: `1`
- in_progress: `0`
- completed_10m: `4`
- failed_10m: `1`
- failure_rate_10m_pct: `20.0`
- completed_10m_gate: `4`
- failed_10m_gate: `1`
- failure_rate_10m_gate_pct: `20.0`
- stale_in_progress: `0` (threshold `45m`)
- eligible_now: `4`
- campaign_done: `1513`
- campaign_in_progress: `0`
- contract_rollout_mode: `enforce`
- contract_enforce: `1`
- dynamic_alert_count: `0`
- dynamic_mounts_denied_count: `0`
- dynamic_no_slot_available_count: `0`
- dynamic_failed_nonzero_rc_count: `0`
- dynamic_slot_running: `1` / `1`

## Gate Results

- 15m: pass=`False` active=`False` reason=`error_rate_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`1` samples=`12` completed_delta=`0` completed10m_ratio=`1.00` max_pending=`1` max_in_progress=`1` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`4` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0` error_rate_gate_ok=`False` max_failure_rate_10m_gate_pct=`20.00`
- 1h: pass=`False` active=`False` reason=`error_rate_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`3` samples=`12` completed_delta=`0` completed10m_ratio=`1.00` max_pending=`1` max_in_progress=`1` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`4` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0` error_rate_gate_ok=`False` max_failure_rate_10m_gate_pct=`20.00`
- 6h: pass=`False` active=`False` reason=`error_rate_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`18` samples=`12` completed_delta=`0` completed10m_ratio=`1.00` max_pending=`1` max_in_progress=`1` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`4` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0` error_rate_gate_ok=`False` max_failure_rate_10m_gate_pct=`20.00`
- 24h: pass=`False` active=`False` reason=`error_rate_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`72` samples=`12` completed_delta=`0` completed10m_ratio=`1.00` max_pending=`1` max_in_progress=`1` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`4` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0` error_rate_gate_ok=`False` max_failure_rate_10m_gate_pct=`20.00`

## Sustained Distillation Tail SLO

- ok: `True`
- reason: `ok`
- sample_count: `12`
- min_samples_required: `12`
- max_consecutive_high_watermark_breach: `0` (allowed `< 3`)
- above_target_ratio: `0.0` (allowed `<= 0.35`)
- latest_eligible_now: `4`

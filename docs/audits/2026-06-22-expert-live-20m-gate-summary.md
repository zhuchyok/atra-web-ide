# Runtime KPI Gate Monitor

- started_at_utc: `2026-06-22T21:28:58.173402+00:00`
- last_sample_utc: `2026-06-22T21:48:26.242486+00:00`
- samples_collected: `20`

## Latest Snapshot

- pending: `0`
- in_progress: `1`
- completed_10m: `3`
- failed_10m: `0`
- failure_rate_10m_pct: `0.0`
- completed_10m_gate: `3`
- failed_10m_gate: `0`
- failure_rate_10m_gate_pct: `0.0`
- stale_in_progress: `0` (threshold `45m`)
- eligible_now: `2`
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

- 15m: pass=`False` active=`True` reason=`distillation_tail_violation` stability_ok=`False` throughput_ok=`True` throughput_eligible=`True` min_completed_required=`1` samples=`15` completed_delta=`3` completed10m_ratio=`1.00` max_pending=`1` max_in_progress=`2` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`10` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0` error_rate_gate_ok=`False` max_failure_rate_10m_gate_pct=`33.33`
- 1h: pass=`False` active=`True` reason=`distillation_tail_violation` stability_ok=`False` throughput_ok=`True` throughput_eligible=`True` min_completed_required=`1` samples=`20` completed_delta=`5` completed10m_ratio=`1.00` max_pending=`1` max_in_progress=`3` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`10` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0` error_rate_gate_ok=`False` max_failure_rate_10m_gate_pct=`33.33`
- 6h: pass=`False` active=`True` reason=`error_rate_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`6` samples=`20` completed_delta=`5` completed10m_ratio=`1.00` max_pending=`1` max_in_progress=`3` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`10` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0` error_rate_gate_ok=`False` max_failure_rate_10m_gate_pct=`33.33`
- 24h: pass=`False` active=`True` reason=`error_rate_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`24` samples=`20` completed_delta=`5` completed10m_ratio=`1.00` max_pending=`1` max_in_progress=`3` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`10` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0` error_rate_gate_ok=`False` max_failure_rate_10m_gate_pct=`33.33`

## Sustained Distillation Tail SLO

- ok: `True`
- reason: `ok`
- sample_count: `20`
- min_samples_required: `12`
- max_consecutive_high_watermark_breach: `0` (allowed `< 3`)
- above_target_ratio: `0.15` (allowed `<= 0.35`)
- latest_eligible_now: `2`

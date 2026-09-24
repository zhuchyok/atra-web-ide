# Runtime KPI Gate Monitor

- started_at_utc: `2026-06-18T16:54:28.635048+00:00`
- last_sample_utc: `2026-06-18T17:23:32.239235+00:00`
- samples_collected: `29`

## Latest Snapshot

- pending: `1`
- in_progress: `0`
- completed_10m: `0`
- failed_10m: `0`
- failure_rate_10m_pct: `0.0`
- stale_in_progress: `0` (threshold `45m`)
- eligible_now: `24`
- campaign_done: `1706`
- campaign_in_progress: `0`
- contract_rollout_mode: `enforce`
- contract_enforce: `1`
- dynamic_alert_count: `0`
- dynamic_mounts_denied_count: `0`
- dynamic_no_slot_available_count: `0`
- dynamic_failed_nonzero_rc_count: `0`
- dynamic_slot_running: `1` / `1`

## Gate Results

- 15m: pass=`False` active=`False` reason=`distillation_tail_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`1` samples=`15` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`1` max_in_progress=`0` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`24` tail_breach_streak_max=`15` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`
- 1h: pass=`False` active=`False` reason=`distillation_tail_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`3` samples=`29` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`1` max_in_progress=`1` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`24` tail_breach_streak_max=`29` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`
- 6h: pass=`False` active=`False` reason=`distillation_tail_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`18` samples=`29` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`1` max_in_progress=`1` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`24` tail_breach_streak_max=`29` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`
- 24h: pass=`False` active=`False` reason=`distillation_tail_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`72` samples=`29` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`1` max_in_progress=`1` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`24` tail_breach_streak_max=`29` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`

## Sustained Distillation Tail SLO

- ok: `False`
- reason: `high_watermark_breach_streak`
- sample_count: `29`
- min_samples_required: `12`
- max_consecutive_high_watermark_breach: `29` (allowed `< 3`)
- above_target_ratio: `1.0` (allowed `<= 0.35`)
- latest_eligible_now: `24`

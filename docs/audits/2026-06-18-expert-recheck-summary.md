# Runtime KPI Gate Monitor

- started_at_utc: `2026-06-18T17:06:12.852982+00:00`
- last_sample_utc: `2026-06-18T17:06:20.138829+00:00`
- samples_collected: `2`

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
- 15m: pass=`False` active=`False` reason=`distillation_tail_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`1` samples=`2` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`1` max_in_progress=`0` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`24` tail_breach_streak_max=`2` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`
- 1h: pass=`False` active=`False` reason=`distillation_tail_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`3` samples=`2` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`1` max_in_progress=`0` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`24` tail_breach_streak_max=`2` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`
- 6h: pass=`False` active=`False` reason=`distillation_tail_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`18` samples=`2` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`1` max_in_progress=`0` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`24` tail_breach_streak_max=`2` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`
- 24h: pass=`False` active=`False` reason=`distillation_tail_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`72` samples=`2` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`1` max_in_progress=`0` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`24` tail_breach_streak_max=`2` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`

## Sustained Distillation Tail SLO
- ok: `False`
- reason: `insufficient_samples`
- sample_count: `2`
- min_samples_required: `12`
- max_consecutive_high_watermark_breach: `0` (allowed `< 3`)
- above_target_ratio: `0.0` (allowed `<= 0.35`)
- latest_eligible_now: `24`

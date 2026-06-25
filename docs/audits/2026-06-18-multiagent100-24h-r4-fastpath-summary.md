# Runtime KPI Gate Monitor

- started_at_utc: `2026-06-18T16:37:38.015852+00:00`
- last_sample_utc: `2026-06-19T16:33:52.948315+00:00`
- samples_collected: `285`

## Latest Snapshot
- pending: `1`
- in_progress: `0`
- completed_10m: `0`
- failed_10m: `0`
- failure_rate_10m_pct: `0.0`
- stale_in_progress: `0` (threshold `45m`)
- eligible_now: `0`
- campaign_done: `1706`
- campaign_in_progress: `0`
- contract_rollout_mode: `enforce`
- contract_enforce: `1`
- dynamic_alert_count: `0`
- dynamic_mounts_denied_count: `0`
- dynamic_no_slot_available_count: `0`
- dynamic_failed_nonzero_rc_count: `0`
- dynamic_slot_running: `0` / `0`

## Gate Results
- 15m: pass=`True` active=`False` reason=`insufficient_load_n_a` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`1` samples=`3` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`1` max_in_progress=`0` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`0` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`
- 1h: pass=`True` active=`False` reason=`insufficient_load_n_a` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`3` samples=`12` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`1` max_in_progress=`0` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`0` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`
- 6h: pass=`True` active=`True` reason=`insufficient_load_n_a` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`18` samples=`72` completed_delta=`9` completed10m_ratio=`0.22` max_pending=`2` max_in_progress=`1` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`3` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`
- 24h: pass=`False` active=`True` reason=`distillation_tail_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`72` samples=`285` completed_delta=`52` completed10m_ratio=`0.33` max_pending=`3` max_in_progress=`1` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`24` tail_breach_streak_max=`41` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`

## Sustained Distillation Tail SLO
- ok: `False`
- reason: `high_watermark_breach_streak`
- sample_count: `285`
- min_samples_required: `12`
- max_consecutive_high_watermark_breach: `41` (allowed `< 3`)
- above_target_ratio: `0.1439` (allowed `<= 0.35`)
- latest_eligible_now: `0`

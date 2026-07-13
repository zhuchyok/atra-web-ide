# Runtime KPI Gate Monitor

- started_at_utc: `2026-06-16T21:11:59.743397+00:00`
- last_sample_utc: `2026-06-16T23:08:00.378661+00:00`
- samples_collected: `24`

## Latest Snapshot

- pending: `4`
- in_progress: `0`
- completed_10m: `0`
- failed_10m: `0`
- failure_rate_10m_pct: `0.0`
- stale_in_progress: `0` (threshold `45m`)
- eligible_now: `3`
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

- 15m: pass=`True` active=`False` reason=`insufficient_load_n_a` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`1` samples=`3` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`4` max_in_progress=`0` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`3` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`
- 1h: pass=`True` active=`False` reason=`insufficient_load_n_a` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`3` samples=`12` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`4` max_in_progress=`0` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`3` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`
- 6h: pass=`True` active=`True` reason=`insufficient_load_n_a` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`18` samples=`24` completed_delta=`6` completed10m_ratio=`0.25` max_pending=`7` max_in_progress=`2` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`3` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`
- 24h: pass=`True` active=`True` reason=`insufficient_load_n_a` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`72` samples=`24` completed_delta=`6` completed10m_ratio=`0.25` max_pending=`7` max_in_progress=`2` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`3` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`

## Sustained Distillation Tail SLO

- ok: `True`
- reason: `ok`
- sample_count: `24`
- min_samples_required: `12`
- max_consecutive_high_watermark_breach: `0` (allowed `< 3`)
- above_target_ratio: `0.0` (allowed `<= 0.35`)
- latest_eligible_now: `3`

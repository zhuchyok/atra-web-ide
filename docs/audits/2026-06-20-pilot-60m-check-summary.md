# Runtime KPI Gate Monitor

- started_at_utc: `2026-06-20T19:55:21.210716+00:00`
- last_sample_utc: `2026-06-20T20:54:46.955566+00:00`
- samples_collected: `57`

## Latest Snapshot

- pending: `1`
- in_progress: `1`
- completed_10m: `2`
- failed_10m: `1`
- failure_rate_10m_pct: `33.33`
- stale_in_progress: `0` (threshold `45m`)
- eligible_now: `2`
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

- 15m: pass=`False` active=`True` reason=`threshold_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`True` min_completed_required=`1` samples=`15` completed_delta=`2` completed10m_ratio=`0.47` max_pending=`1` max_in_progress=`2` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`2` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`
- 1h: pass=`False` active=`True` reason=`threshold_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`True` min_completed_required=`3` samples=`57` completed_delta=`4` completed10m_ratio=`0.40` max_pending=`2` max_in_progress=`2` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`3` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`
- 6h: pass=`True` active=`True` reason=`insufficient_load_n_a` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`18` samples=`57` completed_delta=`4` completed10m_ratio=`0.40` max_pending=`2` max_in_progress=`2` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`3` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`
- 24h: pass=`True` active=`True` reason=`insufficient_load_n_a` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`72` samples=`57` completed_delta=`4` completed10m_ratio=`0.40` max_pending=`2` max_in_progress=`2` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`3` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`

## Sustained Distillation Tail SLO

- ok: `True`
- reason: `ok`
- sample_count: `57`
- min_samples_required: `12`
- max_consecutive_high_watermark_breach: `0` (allowed `< 3`)
- above_target_ratio: `0.0` (allowed `<= 0.35`)
- latest_eligible_now: `2`

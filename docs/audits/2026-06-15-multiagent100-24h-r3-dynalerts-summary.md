# Runtime KPI Gate Monitor

- started_at_utc: `2026-06-15T03:43:34.045673+00:00`
- last_sample_utc: `2026-06-15T19:26:10.190501+00:00`
- samples_collected: `188`

## Latest Snapshot

- pending: `21`
- in_progress: `0`
- completed_10m: `1`
- failed_10m: `0`
- failure_rate_10m_pct: `0.0`
- stale_in_progress: `0` (threshold `45m`)
- eligible_now: `6`
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

- 15m: pass=`False` active=`True` reason=`threshold_violation` stability_ok=`False` throughput_ok=`True` throughput_eligible=`True` min_completed_required=`1` samples=`3` completed_delta=`1` completed10m_ratio=`1.00` max_pending=`21` max_in_progress=`0` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`6` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`
- 1h: pass=`False` active=`True` reason=`threshold_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`True` min_completed_required=`3` samples=`12` completed_delta=`4` completed10m_ratio=`0.42` max_pending=`21` max_in_progress=`2` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`6` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`
- 6h: pass=`False` active=`True` reason=`distillation_tail_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`True` min_completed_required=`18` samples=`72` completed_delta=`19` completed10m_ratio=`0.33` max_pending=`21` max_in_progress=`2` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`21` tail_breach_streak_max=`28` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`
- 24h: pass=`False` active=`True` reason=`stability_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`72` samples=`188` completed_delta=`37` completed10m_ratio=`0.25` max_pending=`21` max_in_progress=`2` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`21` tail_breach_streak_max=`28` dynamic_alert_ok=`True` max_dynamic_alert_count=`0`

## Sustained Distillation Tail SLO

- ok: `False`
- reason: `high_watermark_breach_streak`
- sample_count: `188`
- min_samples_required: `12`
- max_consecutive_high_watermark_breach: `28` (allowed `< 3`)
- above_target_ratio: `0.3617` (allowed `<= 0.35`)
- latest_eligible_now: `6`

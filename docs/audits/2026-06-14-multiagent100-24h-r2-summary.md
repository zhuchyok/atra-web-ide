# Runtime KPI Gate Monitor

- started_at_utc: `2026-06-14T11:56:25.653052+00:00`
- last_sample_utc: `2026-06-15T03:42:57.992518+00:00`
- samples_collected: `189`

## Latest Snapshot
- pending: `15`
- in_progress: `0`
- completed_10m: `0`
- failed_10m: `0`
- failure_rate_10m_pct: `0.0`
- stale_in_progress: `0` (threshold `45m`)
- eligible_now: `6`
- campaign_done: `1706`
- campaign_in_progress: `0`
- contract_rollout_mode: `enforce`
- contract_enforce: `1`

## Gate Results
- 15m: pass=`True` active=`False` reason=`insufficient_load_n_a` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`1` samples=`3` completed_delta=`0` completed10m_ratio=`0.67` max_pending=`15` max_in_progress=`0` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`6` tail_breach_streak_max=`0`
- 1h: pass=`False` active=`True` reason=`threshold_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`True` min_completed_required=`3` samples=`12` completed_delta=`6` completed10m_ratio=`0.25` max_pending=`21` max_in_progress=`1` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`6` tail_breach_streak_max=`0`
- 6h: pass=`False` active=`True` reason=`stability_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`18` samples=`72` completed_delta=`7` completed10m_ratio=`0.07` max_pending=`23` max_in_progress=`2` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`13` tail_breach_streak_max=`6`
- 24h: pass=`False` active=`True` reason=`stability_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`72` samples=`189` completed_delta=`30` completed10m_ratio=`0.20` max_pending=`24` max_in_progress=`2` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`16` tail_breach_streak_max=`36`

## Sustained Distillation Tail SLO
- ok: `False`
- reason: `high_watermark_breach_streak`
- sample_count: `189`
- min_samples_required: `12`
- max_consecutive_high_watermark_breach: `36` (allowed `< 3`)
- above_target_ratio: `0.5291` (allowed `<= 0.35`)
- latest_eligible_now: `6`

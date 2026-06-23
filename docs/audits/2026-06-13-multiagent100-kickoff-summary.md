# Runtime KPI Gate Monitor

- started_at_utc: `2026-06-13T11:46:50.742996+00:00`
- last_sample_utc: `2026-06-13T11:52:09.720476+00:00`
- samples_collected: `5`

## Latest Snapshot

- pending: `0`
- in_progress: `1`
- completed_10m: `0`
- failed_10m: `0`
- failure_rate_10m_pct: `0.0`
- stale_in_progress: `0` (threshold `45m`)
- eligible_now: `1`
- campaign_done: `1706`
- campaign_in_progress: `0`
- contract_rollout_mode: `enforce`
- contract_enforce: `1`

## Gate Results

- 15m: pass=`True` active=`False` reason=`insufficient_load_n_a` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`1` samples=`5` completed_delta=`0` completed10m_ratio=`0.20` max_pending=`0` max_in_progress=`1` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`1` tail_breach_streak_max=`0`
- 1h: pass=`True` active=`False` reason=`insufficient_load_n_a` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`3` samples=`5` completed_delta=`0` completed10m_ratio=`0.20` max_pending=`0` max_in_progress=`1` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`1` tail_breach_streak_max=`0`
- 6h: pass=`True` active=`False` reason=`insufficient_load_n_a` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`18` samples=`5` completed_delta=`0` completed10m_ratio=`0.20` max_pending=`0` max_in_progress=`1` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`1` tail_breach_streak_max=`0`
- 24h: pass=`True` active=`False` reason=`insufficient_load_n_a` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`72` samples=`5` completed_delta=`0` completed10m_ratio=`0.20` max_pending=`0` max_in_progress=`1` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`1` tail_breach_streak_max=`0`

## Sustained Distillation Tail SLO

- ok: `False`
- reason: `insufficient_samples`
- sample_count: `5`
- min_samples_required: `12`
- max_consecutive_high_watermark_breach: `0` (allowed `< 3`)
- above_target_ratio: `0.0` (allowed `<= 0.35`)
- latest_eligible_now: `1`

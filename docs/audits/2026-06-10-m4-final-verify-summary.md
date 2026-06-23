# Runtime KPI Gate Monitor

- started_at_utc: `2026-06-10T05:34:33.765206+00:00`
- last_sample_utc: `2026-06-10T05:40:40.662121+00:00`
- samples_collected: `15`

## Latest Snapshot

- pending: `0`
- in_progress: `2`
- completed_10m: `1`
- failed_10m: `0`
- failure_rate_10m_pct: `0.0`
- stale_in_progress: `0` (threshold `45m`)
- eligible_now: `1`
- campaign_done: `1706`
- campaign_in_progress: `0`
- contract_rollout_mode: `enforce`
- contract_enforce: `1`

## Gate Results

- 15m: pass=`True` active=`False` reason=`insufficient_load_n_a` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`1` samples=`15` completed_delta=`0` completed10m_ratio=`1.00` max_pending=`2` max_in_progress=`2` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`1` tail_breach_streak_max=`0`
- 1h: pass=`True` active=`False` reason=`insufficient_load_n_a` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`3` samples=`15` completed_delta=`0` completed10m_ratio=`1.00` max_pending=`2` max_in_progress=`2` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`1` tail_breach_streak_max=`0`
- 6h: pass=`True` active=`False` reason=`insufficient_load_n_a` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`18` samples=`15` completed_delta=`0` completed10m_ratio=`1.00` max_pending=`2` max_in_progress=`2` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`1` tail_breach_streak_max=`0`
- 24h: pass=`True` active=`False` reason=`insufficient_load_n_a` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`72` samples=`15` completed_delta=`0` completed10m_ratio=`1.00` max_pending=`2` max_in_progress=`2` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`1` tail_breach_streak_max=`0`

## Sustained Distillation Tail SLO

- ok: `True`
- reason: `ok`
- sample_count: `15`
- min_samples_required: `12`
- max_consecutive_high_watermark_breach: `0` (allowed `< 3`)
- above_target_ratio: `0.0` (allowed `<= 0.35`)
- latest_eligible_now: `1`

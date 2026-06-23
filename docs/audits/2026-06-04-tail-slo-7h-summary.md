# Runtime KPI Gate Monitor

- started_at_utc: `2026-06-04T21:55:12.838558+00:00`
- last_sample_utc: `2026-06-05T04:53:18.957723+00:00`
- samples_collected: `75`

## Latest Snapshot

- pending: `0`
- in_progress: `0`
- completed_10m: `0`
- failed_10m: `0`
- failure_rate_10m_pct: `0.0`
- eligible_now: `143`
- campaign_done: `1706`
- campaign_in_progress: `0`
- contract_rollout_mode: `enforce`
- contract_enforce: `1`

## Gate Results

- 15m: pass=`False` active=`False` reason=`distillation_tail_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`1` samples=`3` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`0` max_in_progress=`0` distill_tail_ok=`False` max_eligible_now=`143` tail_breach_streak_max=`3`
- 1h: pass=`False` active=`False` reason=`distillation_tail_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`3` samples=`12` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`0` max_in_progress=`0` distill_tail_ok=`False` max_eligible_now=`143` tail_breach_streak_max=`12`
- 6h: pass=`False` active=`False` reason=`distillation_tail_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`18` samples=`72` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`0` max_in_progress=`0` distill_tail_ok=`False` max_eligible_now=`143` tail_breach_streak_max=`72`
- 24h: pass=`False` active=`False` reason=`distillation_tail_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`72` samples=`75` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`0` max_in_progress=`0` distill_tail_ok=`False` max_eligible_now=`143` tail_breach_streak_max=`75`

## Sustained Distillation Tail SLO

- ok: `False`
- reason: `high_watermark_breach_streak`
- sample_count: `75`
- min_samples_required: `12`
- max_consecutive_high_watermark_breach: `75` (allowed `< 3`)
- above_target_ratio: `1.0` (allowed `<= 0.35`)
- latest_eligible_now: `143`

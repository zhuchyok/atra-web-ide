# Runtime KPI Gate Monitor

- started_at_utc: `2026-06-13T11:53:21.199801+00:00`
- last_sample_utc: `2026-06-14T11:50:05.077818+00:00`
- samples_collected: `286`

## Latest Snapshot

- pending: `21`
- in_progress: `0`
- completed_10m: `0`
- failed_10m: `0`
- failure_rate_10m_pct: `0.0`
- stale_in_progress: `0` (threshold `45m`)
- eligible_now: `9`
- campaign_done: `1706`
- campaign_in_progress: `0`
- contract_rollout_mode: `enforce`
- contract_enforce: `1`

## Gate Results

- 15m: pass=`False` active=`False` reason=`stability_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`1` samples=`3` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`21` max_in_progress=`0` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`9` tail_breach_streak_max=`0`
- 1h: pass=`False` active=`True` reason=`stability_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`3` samples=`12` completed_delta=`1` completed10m_ratio=`0.25` max_pending=`21` max_in_progress=`1` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`9` tail_breach_streak_max=`0`
- 6h: pass=`False` active=`True` reason=`stability_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`18` samples=`72` completed_delta=`12` completed10m_ratio=`0.31` max_pending=`23` max_in_progress=`3` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`9` tail_breach_streak_max=`0`
- 24h: pass=`False` active=`True` reason=`stability_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`72` samples=`286` completed_delta=`25` completed10m_ratio=`0.14` max_pending=`23` max_in_progress=`3` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`2980` tail_breach_streak_max=`12`

## Sustained Distillation Tail SLO

- ok: `False`
- reason: `high_watermark_breach_streak`
- sample_count: `286`
- min_samples_required: `12`
- max_consecutive_high_watermark_breach: `12` (allowed `< 3`)
- above_target_ratio: `0.0839` (allowed `<= 0.35`)
- latest_eligible_now: `9`

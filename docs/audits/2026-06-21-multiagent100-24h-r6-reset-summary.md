# Runtime KPI Gate Monitor

- started_at_utc: `2026-06-21T19:41:10.641320+00:00`
- last_sample_utc: `2026-06-22T06:13:59.973594+00:00`
- samples_collected: `125`

## Latest Snapshot
- pending: `8`
- in_progress: `1`
- completed_10m: `20`
- failed_10m: `0`
- failure_rate_10m_pct: `0.0`
- completed_10m_gate: `8`
- failed_10m_gate: `0`
- failure_rate_10m_gate_pct: `0.0`
- stale_in_progress: `0` (threshold `45m`)
- eligible_now: `0`
- campaign_done: `1513`
- campaign_in_progress: `0`
- contract_rollout_mode: `enforce`
- contract_enforce: `1`
- dynamic_alert_count: `0`
- dynamic_mounts_denied_count: `0`
- dynamic_no_slot_available_count: `0`
- dynamic_failed_nonzero_rc_count: `0`
- dynamic_slot_running: `0` / `0`

## Gate Results
- 15m: pass=`False` active=`True` reason=`threshold_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`True` min_completed_required=`1` samples=`3` completed_delta=`20` completed10m_ratio=`0.33` max_pending=`8` max_in_progress=`1` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`0` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0` error_rate_gate_ok=`True` max_failure_rate_10m_gate_pct=`0.00`
- 1h: pass=`False` active=`True` reason=`threshold_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`True` min_completed_required=`3` samples=`12` completed_delta=`20` completed10m_ratio=`0.08` max_pending=`8` max_in_progress=`1` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`0` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0` error_rate_gate_ok=`True` max_failure_rate_10m_gate_pct=`0.00`
- 6h: pass=`False` active=`True` reason=`threshold_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`True` min_completed_required=`18` samples=`72` completed_delta=`20` completed10m_ratio=`0.01` max_pending=`8` max_in_progress=`1` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`0` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0` error_rate_gate_ok=`True` max_failure_rate_10m_gate_pct=`0.00`
- 24h: pass=`False` active=`True` reason=`error_rate_violation` stability_ok=`False` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`72` samples=`125` completed_delta=`20` completed10m_ratio=`0.01` max_pending=`8` max_in_progress=`3` max_stale=`0` distill_tail_ok=`True` max_eligible_now=`2` tail_breach_streak_max=`0` dynamic_alert_ok=`True` max_dynamic_alert_count=`0` error_rate_gate_ok=`False` max_failure_rate_10m_gate_pct=`100.00`

## Sustained Distillation Tail SLO
- ok: `True`
- reason: `ok`
- sample_count: `125`
- min_samples_required: `12`
- max_consecutive_high_watermark_breach: `0` (allowed `< 3`)
- above_target_ratio: `0.0` (allowed `<= 0.35`)
- latest_eligible_now: `0`

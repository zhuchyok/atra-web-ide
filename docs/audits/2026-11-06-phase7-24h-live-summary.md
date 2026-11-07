# Runtime KPI Gate Monitor

- started_at_utc: `2026-11-06T20:07:21.307686+00:00`
- last_sample_utc: `2026-11-07T05:12:10.037380+00:00`
- samples_collected: `109`

## Latest Snapshot

- pending: `0`
- in_progress: `0`
- completed_10m: `0`
- failed_10m: `0`
- failure_rate_10m_pct: `0.0`
- completed_10m_gate: `0`
- failed_10m_gate: `0`
- failure_rate_10m_gate_pct: `0.0`
- stale_in_progress: `0` (threshold `45m`)
- eligible_now: `29800`
- campaign_done: `0`
- campaign_in_progress: `0`
- contract_rollout_mode: `enforce`
- contract_enforce: `1`
- dynamic_alert_count: `0`
- dynamic_mounts_denied_count: `0`
- dynamic_no_slot_available_count: `0`
- dynamic_failed_nonzero_rc_count: `0`
- dynamic_slot_running: `0` / `0`

## Gate Results

- 15m: pass=`False` active=`False` reason=`distillation_tail_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`1` samples=`3` completed_delta=`0` completed10m_ratio=`0.00` max_pending=`0` max_in_progress=`0` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`29800` tail_breach_streak_max=`3` dynamic_alert_ok=`True` max_dynamic_alert_count=`0` error_rate_gate_ok=`True` max_failure_rate_10m_gate_pct=`0.00`
- 1h: pass=`False` active=`True` reason=`distillation_tail_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`3` samples=`12` completed_delta=`1` completed10m_ratio=`0.17` max_pending=`0` max_in_progress=`1` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`29800` tail_breach_streak_max=`12` dynamic_alert_ok=`True` max_dynamic_alert_count=`0` error_rate_gate_ok=`True` max_failure_rate_10m_gate_pct=`0.00`
- 6h: pass=`False` active=`True` reason=`distillation_tail_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`18` samples=`72` completed_delta=`2` completed10m_ratio=`0.06` max_pending=`0` max_in_progress=`1` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`29800` tail_breach_streak_max=`72` dynamic_alert_ok=`True` max_dynamic_alert_count=`0` error_rate_gate_ok=`True` max_failure_rate_10m_gate_pct=`0.00`
- 24h: pass=`False` active=`True` reason=`distillation_tail_violation` stability_ok=`True` throughput_ok=`False` throughput_eligible=`False` min_completed_required=`72` samples=`109` completed_delta=`4` completed10m_ratio=`0.10` max_pending=`0` max_in_progress=`1` max_stale=`0` distill_tail_ok=`False` max_eligible_now=`29800` tail_breach_streak_max=`109` dynamic_alert_ok=`True` max_dynamic_alert_count=`0` error_rate_gate_ok=`True` max_failure_rate_10m_gate_pct=`0.00`

## Sustained Distillation Tail SLO

- ok: `False`
- reason: `high_watermark_breach_streak`
- sample_count: `109`
- min_samples_required: `12`
- max_consecutive_high_watermark_breach: `109` (allowed `< 3`)
- above_target_ratio: `1.0` (allowed `<= 0.35`)
- latest_eligible_now: `29800`
